# detroid — CRM для логистики (с нуля, в стиле Odoo)

Собственная CRM-система для логистики. Каждый компонент пишется вручную —
без Odoo, SuiteCRM и других готовых решений.

Odoo используется **только как визуальный и UX-ориентир**:
дизайн, палитра (`#714B67`), канбан-доска, верхнее меню, фильтры, формы.

## Стек

| Слой | Технология |
|---|---|
| Backend | Python 3.11 + **Flask** (см. обоснование ниже) |
| БД | PostgreSQL 15 + SQLAlchemy + Alembic (через Flask-Migrate) |
| Frontend | Чистый JS (ES6+), SCSS → CSS, Jinja2-шаблоны, HTML5 |
| Инфраструктура | Docker + Docker Compose, Nginx, Let's Encrypt, UFW, Git |

### Почему Flask, а не FastAPI?

1. **Серверный рендеринг из коробки.** Нам нужны Jinja2-страницы (layout, канбан,
   формы) — во Flask это нативно (`render_template`), во FastAPI пришлось бы
   прикручивать Jinja вручную и бороться с мелочами.
2. **Проще новичку.** Flask — синхронный, код читается сверху вниз.
   FastAPI — асинхронный (`async/await`), это отдельная сложная тема.
3. **Зрелая экосистема для классических сайтов:** Flask-Login (сессии),
   Flask-Migrate (Alembic), Flask-WTF. Во FastAPI сессии и формы — руками.
4. **Наша нагрузка — десятки менеджеров**, а не тысячи RPS. Gunicorn + Flask
   спокойно держит такую нагрузку на VPS 2 CPU / 2 GB.
5. **REST API нам тоже нужен** (канбан drag&drop, фильтры) — Flask отлично
   отдаёт JSON через те же маршруты (`/api/...`).

> Вывод: Flask — правильный выбор для CRM с серверным рендерингом и командой-новичком.
> FastAPI был бы лучше, если бы мы делали только JSON-API для мобильного приложения.

## Структура проекта

```
.
├── docker-compose.yml      # Python app + PostgreSQL + Nginx
├── .env.example            # Пример переменных окружения
├── wsgi.py                 # Точка входа для Gunicorn
├── nginx/
│   └── nginx.conf          # Reverse proxy + SSL + статика
├── app/                    # Flask-приложение
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py           # Настройки (dev/prod/test)
│   ├── extensions.py       # db, login_manager, migrate
│   ├── __init__.py         # Фабрика create_app()
│   ├── run.py              # python -m app.run (dev-сервер)
│   ├── seed.py             # Демо-данные (админ + лиды)
│   ├── models/             # user, lead, contact, company, shipment
│   ├── routes/             # main, auth, leads, contacts, shipments, api
│   ├── templates/          # Jinja2 (base + страницы + компоненты)
│   ├── static/
│   │   ├── scss/           # Исходники стилей в духе Odoo
│   │   ├── css/main.css    # Скомпилированный CSS
│   │   └── js/             # app.js, kanban.js, search.js, dragdrop.js
│   └── migrations/         # Alembic (создаётся Flask-Migrate)
├── scripts/
│   ├── clean_server.sh     # Очистка VPS от мусора (ЭТАП 0)
│   ├── setup.sh            # Первичная настройка сервера (ЭТАП 0)
│   └── deploy.sh           # Деплой обновления (git pull + rebuild)
└── docs/
    └── ETAP0_SERVER_SETUP.md  # Пошаговая инструкция для новичка
```

## Быстрый старт (локально, через Docker)

```bash
# 1. Скопировать переменные окружения
cp .env.example .env

# 2. Собрать и запустить (app + postgres + nginx)
docker compose up --build -d

# 3. Применить миграции и создать демо-данные
docker compose exec app flask db upgrade
docker compose exec app python -m app.seed

# 4. Открыть в браузере
# http://localhost  (через Nginx)
# http://localhost:5000  (напрямую Flask, для отладки)
#
# Логин: admin@example.com
# Пароль: admin123
```

Остановить: `docker compose down`
Логи: `docker compose logs -f app`

## Быстрый старт (без Docker — для разработки)

```bash
cd /home/user/detroid
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
cp .env.example .env
# В .env для локального запуска без Postgres:
# DATABASE_URL=sqlite:///crm.db
export FLASK_APP=wsgi.py
flask db upgrade
python -m app.seed
flask run --host=0.0.0.0 --port=5000
```

## Этапы

- [x] **ЭТАП 0** — подготовка сервера (`docs/ETAP0_SERVER_SETUP.md` + `scripts/`)
- [x] **ЭТАП 1** — фундамент: Docker Compose, Flask, PostgreSQL, миграции,
      layout в стиле Odoo, SCSS, аутентификация, dashboard-заглушка
- [x] **ЭТАП 2** — лиды: модель, канбан drag&drop, список, поиск/фильтры,
      форма, быстрое создание, REST API
- [x] **Карточка лида + лента общения** (chatter как в Odoo):
      страница лида, заметки/сообщения справа, API ленты
- [x] **ЭТАП 3** — контакты и компании: списки, карточки, создание/редактирование/удаление,
      привязка лидов к контактам и компаниям, REST API, миграции в репозитории
- [x] **ЭТАП 4** — заявки на перевозку (модуль вырос из «грузоперевозок»):
      статусы, номер З-0001, цены/маржа, перевозчик, лента, канбан и список
- [x] **Поиск 1в1 как в Odoo** — группировка (стадия/менеджер/приоритет),
      свои фильтры, избранное (сохранённые поиски), центрированная панель
- [ ] **ЭТАП 5** — по решению владельца убран (активности/напоминания не нужны)

Подробно каждый этап описан в исходном ТЗ (см. issue / задачу).

## Безопасность

- **Регистрация закрыта** — аккаунты создаёт только администратор в разделе
  «Пользователи» (`/users/`). Первый админ создаётся сидом
  (пароль — из `ADMIN_PASSWORD` в `.env`, иначе случайный, печатается один раз).
- **CSRF-токены** на всех формах и в AJAX (заголовок `X-CSRFToken` из `<meta>`).
- **Анти-брутфорс входа**: 5 неудач с одного IP → пауза 15 минут.
- **Смена пароля** — в меню пользователя. Выход — только через POST.
- **Внешние ключи проверяются**: поддельный менеджер/компания/контакт в форме
  или API не сохраняется (нормализуется в пусто).
- **Индексация** полей фильтров/сортировок — миграция `a3f5d9c21e77`.
- Перед запуском в продакшене: `scripts/gen_env.sh` (секреты) и
  `scripts/enable_https.sh` (HTTPS обязателен — пароли передаются при входе).
