#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Автонастройка .env (ЭТАП 0, шаг 4.3 — автоматический вариант).
#
# Что делает:
#   1. Создаёт .env из .env.example (старый .env сохраняет в backup)
#   2. Генерирует случайный SECRET_KEY (64 символа)
#   3. Генерирует случайный пароль базы (20 символов, буквы+цифры)
#   4. Записывает оба в .env (пароль — в оба места: DATABASE_URL и POSTGRES_PASSWORD)
#   5. Показывает пароль, чтобы ты его сохранил
#
# Запуск на сервере (одна команда):
#   curl -fsSL -o /tmp/gen_env.sh https://raw.githubusercontent.com/Roses1s/detroid/arena/01a0c8d0-detroid/scripts/gen_env.sh \
#     && sudo bash /tmp/gen_env.sh /opt/crm
#
# Или из папки проекта:  sudo bash scripts/gen_env.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="${1:-/opt/crm}"
cd "$PROJECT_DIR"

if [ ! -f ".env.example" ]; then
  echo "ОШИБКА: нет файла .env.example в $PROJECT_DIR"
  echo "Сначала склонируй проект (шаг 4.1):"
  echo "  cd /opt/crm && git clone -b arena/01a0c8d0-detroid https://github.com/Roses1s/detroid.git ."
  exit 1
fi

if [ -f ".env" ]; then
  BACKUP=".env.bak.$(date +%Y%m%d-%H%M%S)"
  cp .env "$BACKUP"
  echo "Старый .env сохранён в $BACKUP"
fi

cp .env.example .env

# Генерация: сначала пробуем python3 (есть в Ubuntu по умолчанию),
# запасной вариант — /dev/urandom без внешних зависимостей.
if command -v python3 >/dev/null 2>&1; then
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  DB_PASSWORD=$(python3 -c "import secrets, string; alphabet = string.ascii_letters + string.digits; print(''.join(secrets.choice(alphabet) for _ in range(20)))")
  ADMIN_PASSWORD=$(python3 -c "import secrets, string; alphabet = string.ascii_letters + string.digits; print(''.join(secrets.choice(alphabet) for _ in range(16)))")
else
  SECRET_KEY=$(od -vN32 -An -tx1 /dev/urandom | tr -d ' \n')
  DB_PASSWORD=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 || true)
  ADMIN_PASSWORD=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16 || true)
fi

# Запись в .env (пароли только из букв+цифр — безопасны для sed и URL)
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" .env
sed -i "s|crm:crm_password_change_me@|crm:${DB_PASSWORD}@|" .env
# Пользователь БД: если в .env сменили POSTGRES_USER, чиним его и в DATABASE_URL
DB_USER=$(grep -E "^POSTGRES_USER=" .env | cut -d= -f2-)
sed -i "s|^DATABASE_URL=postgresql://[^:]*:|DATABASE_URL=postgresql://${DB_USER}:|" .env
# Пароль первого администратора сайта (используется сидом при создании)
if grep -q "^ADMIN_PASSWORD=" .env; then
  sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASSWORD}|" .env
else
  echo "" >> .env
  echo "# Пароль первого администратора (создаётся сидом, если админа ещё нет)" >> .env
  echo "ADMIN_PASSWORD=${ADMIN_PASSWORD}" >> .env
fi

# Проверка: плейсхолдеров не осталось?
if grep -q "change-me\|change_me" .env; then
  echo "ОШИБКА: в .env остались незаменённые плейсхолдеры. Смотри файл: nano $PROJECT_DIR/.env"
  exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo " .env настроен автоматически ✅"
echo "═══════════════════════════════════════════════════"
echo " SECRET_KEY:        сгенерирован (64 символа)"
echo " Пароль базы:       ${DB_PASSWORD}"
echo " Пароль админа:     ${ADMIN_PASSWORD}"
echo "═══════════════════════════════════════════════════"
echo " ⚠️  СОХРАНИ оба пароля в надёжное место (менеджер"
echo "    паролей / блокнот). Пароль админа понадобится"
echo "    при первом входе на сайт."
echo ""
