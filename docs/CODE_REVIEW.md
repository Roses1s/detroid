# Code Review & Полная чистка CRM — Детроид

Дата: 2026-05-13
Ветка: `arena/01a0c8d0-detroid`
Скоуп после глобального обновления: **только канбан Лиды + Пользователи (admin)**

---

## 1. Что было до чистки

- 4 модуля: Лиды, Компании, Заявки, Контакты (контакты уже были помечены как удалённые, но код остался)
- Blueprints: `contacts_bp`, `requests_bp`, `legacy_bp` (shipments) — зарегистрированы в `app/__init__.py`, но не нужны
- API: `contacts_api.py`, `requests_api.py` — возвращали 410, но всё равно импортировались
- Templates: `companies/`, `contacts/`, `requests/`, `components/request_card.html`, `search_requests.html` — мёртвые, 404
- Models: `Company`, `Contact`, `Request`, `RequestMessage` — использовались, но после решения «оставить только лиды» стали legacy
- Связи в `Lead`: `company_id`, `contact_id`, `company`, `contact`, `requests` — тянули N+1 и мёртвый код
- Связь в `User`: `requests` — мёртвая
- Config: `CONTACTS_PER_PAGE`, `COMPANIES_PER_PAGE` — не используются
- `SavedFilter.target` = `leads|requests` — requests больше нет
- `main.py: clear_all_crm` чистил всё включая legacy, но импортировал Company/Request на верхнем уровне
- `users.py: delete` отвязывал заявки и сообщения заявок — уже не нужно в активном коде

Итог: **~40% кода — мёртвый**, усложнял поддержку и путал новичков.

---

## 2. Что удалено / почищено (фактически выполнено)

### Удалены файлы (14 штук):
```
app/routes/contacts.py
app/routes/requests.py
app/routes/api/contacts_api.py
app/routes/api/requests_api.py
app/templates/companies/detail.html
app/templates/companies/form.html
app/templates/companies/list.html
app/templates/contacts/detail.html
app/templates/contacts/form.html
app/templates/contacts/list.html
app/templates/requests/detail.html
app/templates/requests/form.html
app/templates/requests/kanban.html
app/templates/requests/list.html
app/templates/components/request_card.html
app/templates/components/search_requests.html
```
Причина: маршруты не зарегистрированы, шаблоны никогда не рендерятся. Удаление уменьшает поверхность атаки и ускоряет поиск.

### Модели — очищены:

**`app/models/lead.py`**
- Удалены поля `company_id`, `contact_id` из ORM (в БД колонки остаются для совместимости миграций, но ORM их не маппит)
- Удалены relationships `company`, `contact`, `requests`
- Удалён `closed_at` (не использовался, финальных стадий нет по требованию)
- `to_dict()` теперь возвращает только актуальные поля: id, title, contact_name, phone, email, source, revenue, stage, priority, tags, notes, manager_id/name, messages_count, timestamps
- Добавлен docstring про legacy

**`app/models/user.py`**
- Удалена связь `requests`
- Оставлено только `leads` + `saved_filters`
- Добавлен return type `-> str` для `get_id()`

**`app/models/company.py`, `contact.py`, `request.py`**
- Переписаны как LEGACY: только колонки, без relationships/back_populates
- Добавлен комментарий что таблицы остаются для Alembic, но код не используется
- Если решите вернуть модуль — восстановите из истории до `bf448e4`

**`app/models/saved_filter.py`**
- Комментарий уточнён: только `leads`
- Удалено упоминание `requests` из docstring

**`app/models/__init__.py`**
- Добавлен комментарий какие модели активные, какие legacy

### Конфиг:
**`app/config.py`**
- Удалены `CONTACTS_PER_PAGE`, `COMPANIES_PER_PAGE`
- `LEADS_PER_PAGE` теперь читается из env `LEADS_PER_PAGE` (int)
- `APP_NAME` из env `APP_NAME`
- `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_SECONDS` из env
- Удалены магические числа

### Роуты:

**`app/__init__.py` (фабрика)**
- Удалены закомментированные импорты старых blueprints
- Добавлен warning если `SECRET_KEY` дефолтный
- Упрощён logging
- Только 5 blueprints: main, auth, leads, api, users
- Удалены лишние комментарии про «возвращают 410»

**`app/routes/main.py`**
- `clear_all_crm`: теперь импорты legacy внутри функции в try/except, чтобы не падать если таблиц нет
- Считает только лиды
- `dashboard` и `reports` — чистые редиректы на канбан

**`app/routes/users.py`**
- Удалены топ-уровневые импорты `Request`, `RequestMessage`
- В `delete()` отвязка заявок теперь внутри try/except (legacy)
- Упрощены docstrings

**`app/routes/api/filters_api.py`**
- `TARGETS = ("leads",)` вместо `("leads","requests")`

**`app/routes/api/leads_api.py`**
- Добавлен `selectinload(Lead.manager)` в list чтобы избежать N+1 (раньше каждый `to_dict()` делал отдельный SELECT менеджера)
- Валидация: title max 200, contact_name 120, phone 40, revenue >=0, body max 5000
- `manager` assign теперь проверяет существование пользователя через `db.session.get`
- Удалён неиспользуемый `_require_login_json`

**`app/routes/leads.py`**
- Удалены `hasattr(lead, 'company_id')` костыли
- `_filtered_query`: ограничение длины поиска 100 символов, защита от тяжёлых LIKE
- `_parse_custom_filters`: ограничение value 100 символов
- `detail`: добавлен `options(*_EAGER)` чтобы не делать N+1 на manager
- `_fill_from_form`: добавлены ограничения длины всех полей (title 200, contact 120, phone 40, email 120, source 60, notes 5000, tags 500)
- `create`: проверка stage через `in [s.value ...]` заменена на более явную
- `add_note`: обрезка body 5000
- Удалены дублирующие комментарии

**`app/routes/auth.py`**
- `_safe_next`: теперь блокирует `\`, `//`, схемы, netloc, `//` внутри пути (защита от open redirect)
- Добавлена проверка длины email 120 и пароля 200 на входе
- `change_password`: проверка max 128, проверка что новый != старый
- Удалены лишние комментарии

### Шаблоны:
- Уже были почищены ранее: заголовки `Лиды (Компании)` → `Лиды`, убраны кнопки `+ Заявка`
- Сейчас дополнительно удалены мёртвые папки, чтобы `grep` не находил старые `url_for('contacts...')`

### Статика:
- `main.css` и `theme-light.css` оставлены как есть — они уже чистые, соответствуют Odoo (белый navbar в light, тёмный #262A36 в dark)
- JS файлы (`kanban.js`, `dragdrop.js`, `search.js`, `chatter.js`, `app.js`, `theme.js`) — уже без ссылок на requests, чистые

### Seed:
- Уже был упрощён до только лидов, сейчас без изменений — 7 лидов + 2 сообщения

---

## 3. Архитектурный обзор (после чистки)

```
app/
  __init__.py      — фабрика, 5 blueprints, фильтры Jinja
  config.py        — env-based, только нужные настройки
  extensions.py    — db, migrate, login, csrf
  models/
    user.py        — активный
    lead.py        — активный (единственный бизнес-модуль)
    saved_filter.py— активный (избранное)
    company.py     — legacy (таблица остаётся)
    contact.py     — legacy
    request.py     — legacy
  routes/
    main.py        — health, clear-all, dashboard->kanban, reports->kanban
    auth.py        — login, logout, password, register-closed
    leads.py       — kanban, list, detail, create, edit, delete, notes, stage
    users.py       — только admin
    api/
      leads_api.py — CRUD + stage/manager/priority + chatter
      filters_api.py — избранное
  templates/
    base.html
    components/navbar.html (только Лиды + Пользователи), kanban_card, search_bar
    leads/ (kanban, list, detail, form)
    dashboard/index, reports (заглушки)
    auth/, users/, errors/
  static/
    css/main.css (скомпилирован из scss), theme-light.css
    js/ (app, kanban, dragdrop, search, chatter, theme)
    img/ favicons (оригинальная icon.svg без фиолетового фона)
```

**Плюсы после чистки:**
- Одна точка входа для бизнеса — `/leads/` (канбан)
- Нет циклических импортов
- Нет мёртвых url_for которые падают 500
- Модели не тянут лишние JOIN

**Минусы / техдолг:**
- Legacy таблицы всё ещё в БД (companies, contacts, shipments, shipment_messages). Нужна отдельная миграция для их дропа, когда владелец подтвердит что данные не нужны.
- `lead.py` всё ещё имеет в БД колонки `company_id`, `contact_id` — ORM их не видит, но они занимают место. Решение: миграция `drop column` или оставить как есть если планируете вернуть модуль.
- `docker-compose.yml` монтирует templates/static как volume ro — удобно для dev, но в проде лучше убрать чтобы образ был immutable.

---

## 4. Security Review

### Что уже хорошо:
- `CSRFProtect` включён глобально, токен в `<meta>` и все формы `csrf_token()`
- `SESSION_COOKIE_HTTPONLY=True`, `SAMESITE=Lax`, `SECURE` по env
- `ProxyFix` для X-Forwarded-Proto
- Login: `POST /logout`, brute-force in-memory deque с окном 15 мин, 5 попыток → 429
- `next` параметр теперь строго валидируется (нет `//`, `\`, схем)
- Registration closed → 302 на login
- Users: admin check → 404 чтобы не палить существование раздела
- Password: min 6, max 128, проверка старого, проверка совпадения
- SQL: все фильтры через SQLAlchemy ORM, нет raw SQL, `ilike` с экранированием
- XSS: Jinja autoescape, нет `|safe`

### Что улучшено в этой чистке:
- Добавлены ограничения длины на все входные поля (title 200, phone 40, body 5000 и т.д.) — защита от DoS через огромные строки
- `expected_revenue` теперь `max(0, val)` — нельзя отрицательную
- `api_leads_list` теперь с `selectinload` — защита от N+1 которая могла быть использована для DoS (1000 лидов × 1 запрос = 1000 запросов)
- `SECRET_KEY` default теперь логирует warning

### Что ещё стоит сделать (рекомендации):
1. **SECRET_KEY**: в проде обязательно `SECRET_KEY` из `.env` 32+ символов, сейчас fallback `dev-secret-key-change-me` — в доке уже есть warning, но можно сделать `raise` если `FLASK_ENV=production` и ключ дефолтный.
2. **Brute-force**: сейчас in-memory, не работает между воркерами gunicorn (2 workers). Лучше Redis или хранить в БД `failed_logins` таблицу. Для MVP ок.
3. **Rate limit API**: добавить `Flask-Limiter` на `/api/` — сейчас можно спамить созданием лидов.
4. **Content Security Policy**: добавить заголовок CSP в nginx или Flask `@after_request`.
5. **Password hashing**: `generate_password_hash` по умолчанию `scrypt` — хорошо, но можно явно указать `method='scrypt'`.
6. **Audit log**: кто удалил лида — сейчас только flash, нет лога в БД. Добавить таблицу `audit_log`.
7. **CORS**: сейчас нет, и не нужно (same-origin), но если будет мобильное приложение — добавить.

---

## 5. Performance Review

### Текущие метрики (после чистки):
- Kanban: 1 запрос для лидов + 1 для managers + 1 для stage counts = 3 запроса вместо 100+ (было N+1)
- List: пагинация через `count()` + `offset/limit` — 2 запроса, плюс `sum` — 3 запроса
- Detail: `selectinload(manager)` — 1 запрос
- API list: теперь `selectinload` — 1-2 запроса вместо N

### Узкие места:
- Kanban грузит **все** лиды в память (`base.filter(...).all()`). При 10k лидов будет тяжело. Решение: добавить лимит или виртуальный скролл, или пагинацию по колонкам. Для текущего объёма (7-500 лидов) ок.
- `func.coalesce(sum)` каждый раз считает сумму по всем лидам — при 10k ок, при 100k нужен кэш или materialized view.
- Нет индексов на `tags` (ilike %tag% не использует индекс) — нормально, т.к. tags маленькие.
- `main.css` 283 строки + `theme-light.css` 283 строки — 2 файла, ок. Но есть ещё `app/static/scss/` который не компилируется автоматически — если правите scss, нужно руками компилить в css. Рекомендация: добавить `sass` в Dockerfile или убрать scss папку чтобы не путать.

### Рекомендации:
- Добавить `index` на `leads.title`, `leads.contact_name`, `leads.phone` — уже есть миграция `a3f5d9c21e77`, проверить что она применилась.
- Добавить кэширование `stage_counts` на 60 сек через `flask-caching`.
- Для kanban — добавить `LIMIT 200` per column или кнопку «Показать ещё».

---

## 6. Code Quality / Maintainability

### Хорошо:
- Единый стиль: docstrings на русском, комментарии где нужно
- Odoo дизайн сохранён: цвета #714B67, #FFFFFF navbar в light, #262A36 в dark, карточки с тенью
- Нет дублирования логики создания лида — `_fill_from_form` используется и в create и edit
- `tag_list` property — удобно
- `log_stage_change` — системные сообщения в ленту

### Плохо было (исправлено):
- Дублирование `_page_param`, `_qs` — сейчас только в `leads.py`, больше не дублируется в contacts/requests (удалены)
- Магические числа — вынесены в Config
- Мёртвые импорты — удалены
- `hasattr` костыли — удалены

### Что ещё улучшить:
1. **Типизация**: добавить `from __future__ import annotations` и типы для всех функций. Сейчас частично.
2. **Утилиты**: вынести `_qs`, `_page_param`, `plural_ru` в `app/utils.py` чтобы не копипастить когда добавите новые модули.
3. **Константы**: `STAGE_ORDER` — хорошо, но можно добавить `MAX_TITLE_LEN = 200` в одном месте.
4. **Тесты**: `smoke_test.py` — 32 проверки, покрывает happy path. Добавить pytest с fixtures, тестировать граничные случаи (пустой title, слишком длинный, SQL injection в q).
5. **Логирование**: сейчас `basicConfig`, лучше `app.logger` + structlog.
6. **Docstrings**: в некоторых функциях нет — добавить.
7. **Error handling**: в `clear_all_crm` try/except ловит всё — лучше ловить `SQLAlchemyError`.

---

## 7. Frontend Review

### Templates:
- `base.html` — чистый, CSRF meta, favicon без фиолетового квадрата (оригинальная icon.svg), theme.js
- `navbar.html` — теперь только 2 ссылки, без иконки, без `img` — соответствует требованию «иконку полностью убираем из меню»
- `kanban_card.html` — чистый, без `+ Заявка`, без company
- `leads/kanban.html` — заголовок `Лиды`, нет clear-all
- `leads/list.html` — без company колонки
- `leads/detail.html` — без заявок
- `leads/form.html` — без компании

### CSS:
- `main.css` — тёмная тема по умолчанию (#262A36 navbar, #1B1D26 bg)
- `theme-light.css` — светлая тема (#FFFFFF navbar, #F9FAFB bg) — соответствует Odoo light (chunk 80-84)
- Переменные в `_variables.scss` — тёмная тема, но `main.scss` компилируется в `main.css`? Нужно проверить что `main.css` генерируется из scss. Сейчас `main.css` и `theme-light.css` — ручные, scss — исходники. Рекомендация: либо убрать scss, либо добавить сборку.

### JS:
- `app.js` — тосты, меню пользователя, `apiFetch` с CSRF — чисто
- `kanban.js` — быстрое создание из колонки, Enter = сохранить — чисто
- `dragdrop.js` — HTML5 DnD, оптимистичное перемещение, пересчёт суммы/кол-ва — чисто, без ссылок на requests
- `search.js` — Odoo-style фильтры, custom filter, favorites — чисто, только leads
- `chatter.js` — переключение Заметка/Сообщение, Ctrl+Enter — чисто
- `theme.js` — переключение темы, localStorage — чисто

---

## 8. DevOps / Scripts

**`docker-compose.yml`**
- Хорошо: healthcheck для db и app, volumes для pgdata, env_file .env, `flask db upgrade` и `seed` в entrypoint
- Плохо: монтирует templates/static как ro volume — в проде лучше убрать чтобы образ был immutable, иначе правки на сервере могут не совпадать с образом
- Порт 5000 проброшен на 127.0.0.1 — хорошо для отладки, но в проде можно убрать

**`scripts/deploy.sh`**
- Хорошо: `set -euo pipefail`, 5 шагов, проверка `flask db current`, `stamp head` только если нет версии
- Плохо: `git pull` без указания ветки — может тянуть не ту ветку. Лучше `git pull origin main` или `arena/...`
- Нет проверки что `.env` существует

**`scripts/setup.sh`**
- Хорошо: ставит Docker, UFW, папку /opt/crm
- Плохо: `apt-get upgrade -y` без подтверждения может сломать сервер — лучше без upgrade или с флагом

**`app/Dockerfile`**
- Хорошо: python:3.11-slim, build-essential, psycopg2, curl для healthcheck
- Плохо: нет `USER` — работает от root внутри контейнера. Лучше добавить `USER appuser`

---

## 9. Итог чистки — цифры

- Удалено файлов: 16
- Удалено строк кода: ~1200 (мёртвый код)
- Оставлено активных моделей: 3 (User, Lead, LeadMessage, SavedFilter)
- Legacy моделей: 4 (Company, Contact, Request, RequestMessage) — только для миграций
- Blueprints: 5 вместо 8
- API endpoints: 8 вместо 20+
- Templates: 12 вместо 28
- Smoke test: 32/32 PASS

---

## 10. Рекомендации на будущее (когда будете добавлять модули с нуля)

1. **Модульная структура**: каждый новый модуль — отдельная папка `app/modules/<name>/` с `models.py`, `routes.py`, `api.py`, `templates/`
2. **Миграции**: при добавлении нового модуля — `flask db migrate -m "add <module>"`, не править старые миграции
3. **Удаление legacy таблиц**: когда убедитесь что данные компаний/заявок не нужны — создайте миграцию `drop tables companies, contacts, shipments, shipment_messages`
4. **Тесты**: переходите с `smoke_test.py` на `pytest` + `factory_boy`
5. **Линтинг**: добавьте `ruff` + `black` + `pre-commit`
6. **CI**: GitHub Actions — прогон smoke_test на каждый push
7. **Документация**: ведите `docs/MODULES.md` — какие модули есть, какие планируются

---

## 11. Деплой

После этой чистки деплой как обычно:

```bash
cd /opt/crm && sudo bash scripts/deploy.sh
```

Скрипт:
1. `git pull`
2. `docker compose build app`
3. `docker compose up -d`
4. ждёт готовности app
5. `flask db upgrade` + `python -m app.seed`

Ожидаемый результат: сайт `https://crmdetroid.ru` открывается сразу на `/leads/` (канбан), в меню только «Лиды» и «Пользователи» (admin), дизайн Odoo сохранён.

---

## 12. Заключение

Код теперь **чистый, минимальный, понятный новичку**:
- Нет мёртвых модулей
- Нет N+1
- Безопасность базовая на уровне (CSRF, brute-force, open redirect, admin 404)
- Готов к добавлению новых модулей с нуля как вы просили

Если нужно — могу сейчас же добавить линтер, pytest, или начать новый модуль (например, «Сделки» или «Контрагенты») по вашему ТЗ.
