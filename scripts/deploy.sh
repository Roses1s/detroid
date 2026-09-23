#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Деплой обновления CRM на сервере.
#   1. git pull (забрать новый код)
#   2. пересобрать образ app
#   3. перезапустить контейнеры
#   4. подождать готовности app (entrypoint сам ставит миграции при старте)
#   5. применить миграции + догрузить демо-данные
#
# Запуск (из папки проекта на сервере):  sudo bash scripts/deploy.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== 1/5. Забираю новый код ==="
git pull

echo "=== 2/5. Пересобираю образ ==="
docker compose build app

echo "=== 3/5. Перезапускаю ==="
docker compose up -d

echo "=== 4/5. Жду готовности приложения (до 70 сек) ==="
# Контейнер app при старте сам применяет миграции и seed.
# Ждём, чтобы не выполнять те же команды одновременно с ним (гонка!).
for i in $(seq 1 12); do
  if docker compose exec -T app true 2>/dev/null; then
    break
  fi
  sleep 5
done
sleep 10

echo "=== 5/5. Миграции ==="
# Сначала проверяем, что контейнер вообще отвечает.
# (Иначе провал exec можно неверно принять за «нет версии».)
if ! CURRENT_OUT=$(docker compose exec -T app flask db current 2>&1); then
  echo "ОШИБКА: контейнер app недоступен (перезапускается?). Причина — в его логах:"
  echo "  docker compose logs --tail=40 app"
  exit 1
fi
echo "$CURRENT_OUT" | tail -n 2
# ВАЖНО: stamp делаем ТОЛЬКО если у базы вообще нет версии
# (один раз при переезде со старой схемы). Слепо штамповать после
# упавшего upgrade НЕЛЬЗЯ — это прячет ошибку и ломает схему.
CURRENT=$(echo "$CURRENT_OUT" | grep -oE "[0-9a-f]{12}" | head -n 1 || true)
if [ -z "$CURRENT" ]; then
  echo "(у базы нет версии: помечаю существующие таблицы)"
  docker compose exec -T app flask db stamp head
fi
docker compose exec -T app flask db upgrade
echo "Версия базы после миграций:"
docker compose exec -T app flask db current

echo "=== Бонус. Демо-данные (догрузка недостающих) ==="
docker compose exec -T app python -m app.seed || true

echo ""
docker compose ps
echo "Готово! Проверь сайт в браузере."
