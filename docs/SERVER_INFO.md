# Данные сервера проекта (подставлять в команды!)

> Этот файл — шпаргалка с реальными данными. Все будущие инструкции
> используют значения отсюда, а не заглушки вида `ТВОЙ_IP`.

| Параметр | Значение |
|---|---|
| IP сервера | `77.222.38.191` |
| Домен | `crmdetroid.ru` |
| Сайт | `https://crmdetroid.ru` |
| ОС | Ubuntu 24.04 LTS |
| Пользователь SSH | `root` |
| Папка проекта | `/opt/crm` |
| Ветка Git | `arena/01a0c8d0-detroid` |
| Хостер | spaceweb.ru (VPS: 2 CPU, 2 GB RAM, 15 GB NVMe) |

## Готовые команды (можно копировать как есть)

```bash
# Подключиться к серверу (дома)
ssh root@77.222.38.191

# Сбросить отпечаток сервера (если переустанавливалась ОС)
ssh-keygen -R 77.222.38.191

# Проверить DNS дома
nslookup crmdetroid.ru
# Ожидается: Address: 77.222.38.191

# Обновить сайт на сервере (деплой)
cd /opt/crm && sudo bash scripts/deploy.sh

# Статус и логи на сервере
cd /opt/crm && docker compose ps
cd /opt/crm && docker compose logs -f --tail=100 app

# Финальная проверка ЭТАПА 0 (на сервере)
cd /opt/crm && echo "== версии ==" && docker --version && docker compose version && git --version && echo "== файрвол ==" && ufw status | head -8 && echo "== контейнеры ==" && docker compose ps && echo "== сайт локально ==" && curl -s -o /dev/null -w "%{http_code}\n" http://localhost/auth/login && curl -sk -o /dev/null -w "https: %{http_code}\n" https://localhost/auth/login
```

## Доступы

- Демо-админ CRM: `admin@example.com` (пароль меняем — см. задачу ЭТАПА 5 / отдельный шаг)
- Пароль базы PostgreSQL: сгенерирован скриптом `gen_env.sh`, хранится в `/opt/crm/.env` на сервере
  (копия показана при генерации — сохранена у владельца)
