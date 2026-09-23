#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Очистка VPS от мусора ПЕРЕД установкой CRM (ЭТАП 0, шаг 2).
#
# ВНИМАНИЕ: скрипт останавливает и удаляет ВСЕ Docker-контейнеры,
# образы, volume'ы и неиспользуемые пакеты. Запускай только если
# уверен, что на сервере нет ничего нужного!
#
# Запуск:  sudo bash scripts/clean_server.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

echo "=== 1/5. Что сейчас занимает место ==="
df -h / || true
echo ""
docker system df 2>/dev/null || echo "(docker не установлен — пропускаю)"
echo ""

read -r -p "Удалить ВСЕ docker-контейнеры/образы/volume'ы и очистить мусор? [y/N] " answer
if [[ ! "$answer" =~ ^[YyДд]$ ]]; then
  echo "Отменено. Ничего не удаляю."
  exit 0
fi

echo "=== 2/5. Останавливаю контейнеры ==="
if command -v docker >/dev/null 2>&1; then
  docker stop $(docker ps -aq) 2>/dev/null || echo "(нет запущенных контейнеров)"
  echo "=== 3/5. Удаляю контейнеры, образы, сети, volume'ы ==="
  docker system prune -a --volumes -f || true
else
  echo "(docker не установлен — пропускаю)"
fi

echo "=== 4/5. Чищу пакеты и журналы ==="
apt-get autoremove -y || true
apt-get autoclean -y || true
journalctl --vacuum-time=7d || true
rm -rf /tmp/* /var/tmp/* || true

echo "=== 5/5. Итог ==="
df -h / || true
echo "Готово. Сервер чист."
