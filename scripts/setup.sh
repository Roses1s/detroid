#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Первичная настройка VPS под CRM (ЭТАП 0, шаги 3–5).
# Ubuntu 20.04 / 22.04 / 24.04.
#
# Что делает:
#   1. Обновляет систему
#   2. Ставит Docker + Docker Compose plugin + Git + UFW
#   3. Настраивает файрвол (22, 80, 443)
#   4. Создаёт папку проекта /opt/crm
#   5. Проверяет установки
#
# Запуск:  sudo bash scripts/setup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

echo "=== 1/6. Обновление системы ==="
apt-get update
apt-get upgrade -y

echo "=== 2/6. Базовые пакеты ==="
apt-get install -y ca-certificates curl gnupg git ufw

echo "=== 3/6. Docker (официальный репозиторий) ==="
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker

echo "=== 4/6. Файрвол UFW ==="
ufw allow 22/tcp    # SSH — НЕ ЗАКРЫВАТЬ, иначе потеряешь доступ!
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable
ufw status verbose || true

echo "=== 5/6. Папка проекта ==="
mkdir -p /opt/crm
echo "Папка /opt/crm готова. Клонируй туда проект:"
echo "  cd /opt/crm && git clone <URL_РЕПОЗИТОРИЯ> ."

echo "=== 6/6. Проверка ==="
docker --version
docker compose version
git --version
echo ""
echo "Готово! Дальше: настрой .env и запусти docker compose up (см. docs/ETAP0_SERVER_SETUP.md)."
