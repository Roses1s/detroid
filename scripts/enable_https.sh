#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Включение HTTPS для CRM (ЭТАП 0, шаг 6 — автоматический вариант).
#
# Режим 1 — новый БЕСПЛАТНЫЙ сертификат Let's Encrypt (рекомендуется):
#   curl -fsSL -o /tmp/enable_https.sh https://raw.githubusercontent.com/Roses1s/detroid/arena/01a0c8d0-detroid/scripts/enable_https.sh \
#     && sudo bash /tmp/enable_https.sh ТВОЙ_ДОМЕН твоя@почта.ru
#   Условие: домен уже смотрит на IP сервера (A-запись у регистратора)!
#
# Режим 2 — у тебя уже есть файлы сертификата:
#   1. Положи их на сервер: /opt/crm/nginx/ssl/fullchain.pem и privkey.pem
#      (командой scp с домашнего компьютера, см. docs/ETAP0_SERVER_SETUP.md)
#   2. sudo bash /tmp/enable_https.sh ТВОЙ_ДОМЕН --existing
#
# Что делает скрипт:
#   1. (режим 1) Проверяет DNS, останавливает nginx, ставит certbot,
#      выпускает сертификат, копирует его в nginx/ssl/
#   2. Включает HTTPS-блок и редирект HTTP→HTTPS в nginx/nginx.conf
#      (старый конфиг сохраняет в .bak — можно откатить)
#   3. Перезапускает nginx и проверяет https локально
#   4. (режим 1) Ставит автообновление сертификата в cron
# ─────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${1:-}"
MODE="${2:-}"
PROJECT_DIR="${PROJECT_DIR:-/opt/crm}"
EMAIL=""

if [ -z "$DOMAIN" ] || [ -z "$MODE" ]; then
  echo "Использование:"
  echo "  sudo bash enable_https.sh ТВОЙ_ДОМЕН твоя@почта.ru   # новый бесплатный сертификат"
  echo "  sudo bash enable_https.sh ТВОЙ_ДОМЕН --existing      # свои файлы уже лежат в nginx/ssl/"
  exit 1
fi
if [ "$MODE" != "--existing" ]; then
  EMAIL="$MODE"
fi

cd "$PROJECT_DIR"
if [ ! -f "docker-compose.yml" ]; then
  echo "ОШИБКА: нет docker-compose.yml в $PROJECT_DIR — ты в папке проекта?"
  exit 1
fi

CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
SSL_DIR="$PROJECT_DIR/nginx/ssl"
mkdir -p "$SSL_DIR"

if [ "$MODE" == "--existing" ]; then
  if [ ! -f "$SSL_DIR/fullchain.pem" ] || [ ! -f "$SSL_DIR/privkey.pem" ]; then
    echo "ОШИБКА: в $SSL_DIR нет fullchain.pem и privkey.pem"
    echo "Сначала загрузи их с домашнего компьютера:"
    echo "  scp fullchain.pem root@IP_СЕРВЕРА:$SSL_DIR/fullchain.pem"
    echo "  scp privkey.pem root@IP_СЕРВЕРА:$SSL_DIR/privkey.pem"
    exit 1
  fi
  echo "Нашёл твои сертификаты в $SSL_DIR"
else
  echo "=== 1/6. Проверка DNS: $DOMAIN должен смотреть на этот сервер ==="
  SERVER_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
  DOMAIN_IP=$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)
  echo "Публичный IP сервера: ${SERVER_IP}"
  echo "Домен $DOMAIN резолвится в: ${DOMAIN_IP:-(не резолвится)}"
  if [ -z "$DOMAIN_IP" ] || [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    echo ""
    echo "⚠️  СТОП: домен НЕ указывает на этот сервер!"
    echo "Зайди в панель регистратора домена (где покупал домен) и создай"
    echo "A-запись:  $DOMAIN  →  $SERVER_IP"
    echo "Подожди 5–30 минут (обновление DNS) и запусти скрипт снова."
    exit 1
  fi
  echo "DNS в порядке."

  echo "=== 2/6. Освобождаю порт 80 (останавливаю nginx-контейнер) ==="
  docker compose stop nginx || true

  echo "=== 3/6. Устанавливаю certbot и выпускаю сертификат ==="
  apt-get update -qq
  apt-get install -y -qq certbot
  certbot certonly --standalone -d "$DOMAIN" --agree-tos -m "$EMAIL" --no-eff-email -n

  echo "=== 4/6. Копирую сертификаты в $SSL_DIR ==="
  cp "$CERT_DIR/fullchain.pem" "$SSL_DIR/fullchain.pem"
  cp "$CERT_DIR/privkey.pem" "$SSL_DIR/privkey.pem"
  chmod 600 "$SSL_DIR/privkey.pem"
fi

echo "=== 5/6. Включаю HTTPS в nginx.conf ==="
NGINX_CONF="$PROJECT_DIR/nginx/nginx.conf"
cp "$NGINX_CONF" "$NGINX_CONF.bak.$(date +%Y%m%d-%H%M%S)"
echo "(бэкап конфига: $NGINX_CONF.bak.*)"
# 5a. Редирект HTTP→HTTPS: раскомментировать 3 строки (if / return / })
sed -i 's|^\(\s*\)# \(if ([$]host != "localhost") {\)|\1\2|' "$NGINX_CONF"
sed -i 's|^\(\s*\)# \+\(return 301 https://[$]host[$]request_uri;\)|\1\2|' "$NGINX_CONF"
sed -i 's|^\(        \)# }$|\1}|' "$NGINX_CONF"
# 5b. Раскомментировать весь HTTPS server-блок
sed -i '/^# server {/,/^# }/ s/^# \?//' "$NGINX_CONF"
# 5c. Подставить домен
sed -i "s|server_name crm.example.ru;|server_name ${DOMAIN};|" "$NGINX_CONF"
# Проверка патча
grep -q "server_name ${DOMAIN};" "$NGINX_CONF" || { echo "ОШИБКА патча nginx.conf — откати из .bak и напиши мне"; exit 1; }
grep -q "return 301 https" "$NGINX_CONF" && echo "(редирект HTTP→HTTPS включён)" || echo "(редирект уже был включён ранее)"

echo "=== 6/6. Перезапускаю nginx и проверяю ==="
docker compose up -d nginx
sleep 5
docker compose ps nginx
curl -sk -o /dev/null -w "HTTPS локально отвечает кодом: %{http_code} (нужен 200)\n" https://localhost/ || true

if [ "$MODE" != "--existing" ]; then
  echo "=== Бонус. Автообновление сертификата (cron) ==="
  CRON_LINE="0 3 * * * certbot renew --quiet --deploy-hook \"cp $CERT_DIR/fullchain.pem $SSL_DIR/fullchain.pem && cp $CERT_DIR/privkey.pem $SSL_DIR/privkey.pem && cd $PROJECT_DIR && docker compose restart nginx\""
  (crontab -l 2>/dev/null | grep -v "certbot renew" || true; echo "$CRON_LINE") | crontab -
  echo "Готово: каждую ночь в 03:00 certbot будет продлевать сертификат сам."
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo " HTTPS включён ✅  Открой дома: https://$DOMAIN"
echo " В адресной строке должен быть замочек 🔒"
echo "═══════════════════════════════════════════════════"
