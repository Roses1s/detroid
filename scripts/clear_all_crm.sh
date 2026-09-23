#!/usr/bin/env bash
# Глобальная очистка CRM — удалить ВСЕ карточки (лиды, компании, заявки, логи)
# Доступно всем пользователям через UI, но этот скрипт — для сервера/админа
# Запуск: sudo bash scripts/clear_all_crm.sh  (из /opt/crm) или docker compose exec app python -m app.seed clear
set -euo pipefail
cd "$(dirname "$0")/.."
echo "=== Очистка CRM: удаляю все лиды, компании, заявки, логи ==="
echo "Контакты уже убраны из логики CRM"
docker compose exec -T app python -m app.seed clear
echo "Готово. Проверь / и /leads/ — должно быть пусто."
docker compose ps
