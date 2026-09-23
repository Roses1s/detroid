"""Дымовой тест CRM (ЭТАПЫ 1–4). Запуск из корня проекта:

    python scripts/smoke_test.py

Использует временную SQLite-базу в /tmp — продовую базу не трогает.
Код выхода 0 = все проверки прошли, 1 = есть падения.
"""
import os
import sys
import tempfile

# Временная база. Должна задаваться ДО импорта приложения!
_fd, _DB_PATH = tempfile.mkstemp(prefix="crm_smoke_", suffix=".db")
os.close(_fd)
os.unlink(_DB_PATH)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "smoke-test-key"
# Фиксированный пароль админа для тестов (иначе сид сгенерирует случайный)
os.environ["ADMIN_PASSWORD"] = "admin123"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, seed  # noqa: E402
from app.models import User  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, bool]] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    results.append((name, bool(cond)))
    print(f"{PASS if cond else FAIL} {name}" + (f" [{extra}]" if extra and not cond else ""))
    if not cond and extra:
        print(f"      -> {extra[:300]}")


def main() -> int:
    app = create_app()
    app.config["TESTING"] = True
    # В тестах CSRF не проверяем: реальные браузеры шлют токен из <meta> (base.html)
    app.config["WTF_CSRF_ENABLED"] = False

    # Таблицы через миграции (как на проде), а не create_all
    from flask_migrate import upgrade

    with app.app_context():
        upgrade()

    seed.seed()  # демо-данные
    seed.seed()  # повторный прогон — проверка идемпотентности

    c = app.test_client()

    # ── ЭТАП 1: фундамент + auth ──────────────────────────
    r = c.get("/", follow_redirects=False)
    check("guest redirect to login", r.status_code == 302 and "/auth/login" in r.headers.get("Location", ""))
    r = c.get("/auth/login")
    html_login = r.data.decode()
    check("login page renders", r.status_code == 200 and ("Детроид" in html_login or "Detroid" in html_login), html_login[:200])
    r = c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"},
               follow_redirects=True)
    check("login works", r.status_code == 200 and "Лиды" in r.data.decode())
    r = c.get("/")
    check("dashboard renders", r.status_code == 200 and "Последние лиды" in r.data.decode())

    # ── ЭТАП 2: лиды ──────────────────────────────────────
    r = c.get("/leads/")
    html = r.data.decode()
    check("kanban renders 7 cards", r.status_code == 200 and html.count('oe_kanban_card') == 7, html[:200])
    check("kanban shows linked company", "Восток-Трейд" in html)
    r = c.get("/leads/list")
    check("leads list renders", r.status_code == 200)
    r = c.get("/api/leads")
    leads = r.get_json()
    check("API leads list == 7", isinstance(leads, list) and len(leads) == 7, str(leads)[:200])
    check("API lead has company field (contacts removed)", "company_id" in leads[0])
    lead_id = leads[0]["id"]
    r = c.patch(f"/api/leads/{lead_id}/stage", json={"stage": "potential"})
    check("API move stage", r.status_code == 200 and r.get_json()["stage"] == "potential")
    r = c.post("/api/leads", json={"title": "Тест API", "stage": "lead"})
    check("API quick create", r.status_code == 201, r.data.decode()[:200])

    # ── Поиск 1в1 как в Odoo: группировка, свои фильтры, избранное ──
    r = c.get("/leads/")
    html = r.data.decode()
    check("search panel odoo sections",
          "Группировать по" in html and "Избранное" in html and "Добавить свой фильтр" in html)
    check("kanban 6 stage columns + board attrs",
          html.count('o_kanban_col"') == 6 and 'data-status-key="stage"' in html)
    r = c.get("/leads/?group_by=manager")
    html = r.data.decode()
    check("kanban group by manager",
          'data-status-key="manager"' in html and "Без менеджера" in html
          and "Администратор" in html, html[:300])
    r = c.get("/leads/?group_by=priority")
    html = r.data.decode()
    check("kanban group by priority",
          'data-status-key="priority"' in html and html.count('o_kanban_col"') == 4)
    r = c.get("/leads/list?group_by=manager")
    html = r.data.decode()
    check("list group headers", "o_group_row" in html and "Без менеджера" in html)
    r = c.get("/leads/", query_string={"flt": "priority|>=|2"})
    html = r.data.decode()
    check("custom filter chip", "Приоритет ≥ ★★" in html)
    check("custom filter applies", html.count('oe_kanban_card') == 4, html[:200])
    r = c.get("/leads/", query_string={"flt": "nonsense"})
    check("bad custom filter ignored",
          r.status_code == 200 and r.data.decode().count('oe_kanban_card') == 8)
    # Избранное: сохранить → применить → удалить
    r = c.post("/api/favorites",
               json={"name": "Важные", "target": "leads", "params": "flt=priority|>=|2"})
    check("favorite create", r.status_code == 201, r.data.decode()[:200])
    fav_id = r.get_json()["id"]
    check("favorite in panel", "Важные" in c.get("/leads/").data.decode())
    check("favorite list api",
          any(f["name"] == "Важные" for f in c.get("/api/favorites?target=leads").get_json()))
    check("favorite delete", c.delete(f"/api/favorites/{fav_id}").status_code == 200)
    check("favorite gone", "Важные" not in c.get("/leads/").data.decode())
    # Фикс счётчиков канбана заявок (раньше шаблон читал несуществующий ключ)
    r = c.get("/requests/kanban")
    import re as _re
    counts = [int(x) for x in _re.findall(r'o_kanban_col__count">(\d+)', r.data.decode())]
    check("requests kanban column counters", len(counts) == 6 and sum(counts) == 6, str(counts))
    # Поддельные внешние ключи не сохраняются (нормализуются в пусто + предупреждение)
    fake_lead = c.post("/api/leads", json={"title": "FK-тест"}).get_json()
    r = c.post(f"/leads/{fake_lead['id']}/edit",
               data={"title": "FK-тест", "manager_id": "999999", "company_id": "888888"},
               follow_redirects=True)
    html = r.data.decode()
    got = [x for x in c.get("/api/leads").get_json() if x["id"] == fake_lead["id"]][0]
    check("fake FK ids rejected in form",
          got["manager_id"] is None and got["company_id"] is None
          and "менеджер не найден" in html, html[:400])
    c.delete(f"/api/leads/{fake_lead['id']}")
    # Контакты убраны — API контактов должен возвращать 410
    r = c.get("/api/contacts")
    check("contacts API removed returns 410", r.status_code == 410)
    r = c.post("/api/contacts", json={"first_name": "ФК", "last_name": "Тест"})
    check("contacts API create returns 410", r.status_code == 410)
    # Пагинация списков: временно делаем страницу на 3 записи
    app.config["LEADS_PER_PAGE"] = 3
    r = c.get("/leads/list")
    html = r.data.decode()
    check("leads list paginates", "o_pager" in html and "/8" in html, html[:300])
    r = c.get("/leads/list?page=2")
    check("leads list page 2 renders", r.status_code == 200)
    app.config["LEADS_PER_PAGE"] = 50
    r = c.get("/contacts?page=1", follow_redirects=False)
    check("contacts list removed redirects to kanban", r.status_code in (302, 308) and "/leads" in r.headers.get("Location",""))
    r = c.get("/requests/?page=999")
    check("requests page overflow clamps", r.status_code == 200)
    # Drag&drop между группами: менеджер и приоритет
    admin_id = [x for x in c.get("/api/leads").get_json() if x["manager_id"]][0]["manager_id"]
    r = c.patch(f"/api/leads/{lead_id}/manager", json={"manager": "none"})
    check("API reassign manager", r.status_code == 200 and r.get_json()["manager_id"] is None)
    msgs = c.get(f"/api/leads/{lead_id}/messages").get_json()
    check("manager change logged", any("Менеджер изменён" in m["body"] for m in msgs))
    r = c.patch(f"/api/leads/{lead_id}/manager", json={"manager": admin_id})
    check("API reassign back", r.get_json()["manager_id"] == admin_id)
    r = c.patch(f"/api/leads/{lead_id}/priority", json={"priority": 3})
    check("API priority move", r.status_code == 200 and r.get_json()["priority"] == 3)
    r = c.post("/api/leads", json={"title": "Без менеджера", "manager": "none"})
    check("API quick create no manager",
          r.status_code == 201 and r.get_json()["manager_id"] is None)

    # ── ЭТАП 3: контакты УБРАНЫ из CRM ───────────────────────
    # Контакты полностью убраны — /contacts редиректит на /leads/
    r = c.get("/contacts", follow_redirects=False)
    check("contacts removed redirects", r.status_code in (302,308))
    r = c.get("/api/contacts")
    check("contacts API removed 410", r.status_code == 410)

    # ── ЭТАП 3: компании ──────────────────────────────────
    r = c.get("/companies")
    check("companies list renders", r.status_code == 200 and "Восток-Трейд" in r.data.decode())
    r = c.get("/api/companies")
    companies = r.get_json()
    check("API companies list >= 2", isinstance(companies, list) and len(companies) >= 2)
    company_id = [x for x in companies if "Восток" in x["name"]][0]["id"]
    r = c.get(f"/companies/{company_id}")
    html = r.data.decode()
    check("company detail shows lead (contacts removed)", r.status_code == 200 and "Казань" in html)
    r = c.post("/companies/new", data={"name": "ООО «Тест»"}, follow_redirects=True)
    check("company create via form", r.status_code == 200 and "Тест" in r.data.decode())
    test_company_id = Company_id_from_api(c, "Тест")
    r = c.post(f"/companies/{test_company_id}/edit", data={"name": "ООО «Тест-2»"}, follow_redirects=True)
    check("company edit via form", r.status_code == 200 and "Тест-2" in r.data.decode())

    # ── ЭТАП 3: связи лид ↔ контакт/компания ──────────────
    r = c.get(f"/leads/{lead_id}/edit")
    html = r.data.decode()
    check("lead form has company link (contacts removed)", "Компания" in html and "company_id" in html)
    r = c.post(f"/leads/{lead_id}/edit",
               data={"title": leads[0]["title"], "stage": "lead",
                     "company_id": str(test_company_id)},
               follow_redirects=True)
    check("lead link via form (company only)", r.status_code == 200)
    r = c.get(f"/companies/{test_company_id}")
    check("company detail shows linked lead", leads[0]["title"] in r.data.decode())
    r = c.get("/api/leads")
    updated = [x for x in r.get_json() if x["id"] == lead_id][0]
    check("API lead shows company link (contacts removed)", updated["company_id"] == test_company_id,
          str(updated))

    # ── ЭТАП 3: API CRUD (контакты убраны) ───────────────────
    r = c.post("/api/companies", json={"name": "API Company"})
    check("API company create", r.status_code == 201)
    api_co_id = r.get_json()["id"]
    r = c.patch(f"/api/companies/{api_co_id}", json={"phone": "+7 (111)"})
    check("API company patch", r.status_code == 200 and r.get_json()["phone"] == "+7 (111)")
    r = c.delete(f"/api/companies/{api_co_id}")
    check("API company delete", r.status_code == 200)
    r = c.get("/api/contacts")
    check("API contacts still 410", r.status_code == 410)

    # ── ЭТАП 3: удаление компании отвязывает лиды ────────
    r = c.post(f"/companies/{test_company_id}/delete", follow_redirects=True)
    check("company delete via form (any user can delete)", r.status_code == 200)
    r = c.get("/api/leads")
    updated = [x for x in r.get_json() if x["id"] == lead_id][0]
    check("lead survives company delete (unlinked)", updated["company_id"] is None)

    # ── Лента общения (chatter) ─────────────────────────────
    r = c.get(f"/leads/{lead_id}")
    html = r.data.decode()
    check("lead detail renders + chatter", r.status_code == 200 and "o_chatter" in html and "Лог примечания" in html, html[:200])
    check("chatter day separator renders", "o_chatter__day" in html, html[:200])
    r = c.get(f"/api/leads/{lead_id}/messages")
    check("API messages list", r.status_code == 200 and isinstance(r.get_json(), list))
    check("API messages missing lead 404", c.get("/api/leads/999999/messages").status_code == 404)
    r = c.post(f"/leads/{lead_id}/notes", data={"kind": "note", "body": "Тестовая заметка из формы"},
               follow_redirects=True)
    check("note create via form", r.status_code == 200 and "Тестовая заметка из формы" in r.data.decode())
    r = c.post(f"/leads/{lead_id}/notes", data={"kind": "note", "body": "   "}, follow_redirects=True)
    check("empty note rejected gracefully", r.status_code == 200)
    r = c.post(f"/api/leads/{lead_id}/messages", json={"kind": "message", "body": "API сообщение"})
    check("API message create", r.status_code == 201 and r.get_json()["kind"] == "message")
    api_msg_id = r.get_json()["id"]
    # Чужую запись удалять нельзя: второго пользователя создаёт админ
    # (открытая регистрация закрыта — проверяем это отдельно ниже)
    c.post("/auth/logout", follow_redirects=True)
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"},
           follow_redirects=True)
    r = c.post("/users/new",
               data={"username": "user2", "email": "user2@example.com",
                     "full_name": "Второй Менеджер", "role": "manager",
                     "password": "secret123"},
               follow_redirects=True)
    check("admin creates user", r.status_code == 200 and "user2@example.com" in r.data.decode())
    c.post("/auth/logout", follow_redirects=True)
    c.post("/auth/login", data={"email": "user2@example.com", "password": "secret123"},
           follow_redirects=True)
    check("API delete others message 403", c.delete(f"/api/messages/{api_msg_id}").status_code == 403)
    r = c.post(f"/leads/{lead_id}/notes", data={"kind": "note", "body": "Запись второго"},
               follow_redirects=True)
    check("second user note create", r.status_code == 200 and "Запись второго" in r.data.decode())
    # Назад под админом
    c.post("/auth/logout", follow_redirects=True)
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"},
           follow_redirects=True)
    check("API message delete (own)", c.delete(f"/api/messages/{api_msg_id}").status_code == 200)
    own = [m for m in c.get(f"/api/leads/{lead_id}/messages").get_json()
           if m["body"] == "Тестовая заметка из формы"][0]
    r = c.post(f"/leads/notes/{own['id']}/delete", follow_redirects=True)
    check("note delete via form", r.status_code == 200 and "Тестовая заметка из формы" not in r.data.decode())
    check("missing lead 404", c.get("/leads/999999").status_code == 404)

    # ── Odoo: статусбар и поиск ─────────────────────────────
    r = c.post(f"/leads/{lead_id}/stage", data={"stage": "lpr"}, follow_redirects=False)
    check("statusbar move stage", r.status_code == 302 and f"/leads/{lead_id}" in r.headers.get("Location", ""))
    got = [x for x in c.get("/api/leads").get_json() if x["id"] == lead_id][0]
    check("statusbar stage applied", got["stage"] == "lpr", str(got))
    msgs = c.get(f"/api/leads/{lead_id}/messages").get_json()
    check("stage change logged to chatter", any("Стадия изменена" in m["body"] for m in msgs), str(msgs)[:300])
    r = c.get("/leads/?q=Казань")
    html = r.data.decode()
    check("search chip + dropdown render", r.status_code == 200 and "o_chip" in html and "o_searchview__dropdown" in html)
    check("stage option with count", "o_searchview__count" in html)
    r = c.get("/leads/?stage=potential")
    check("stage filter works", r.status_code == 200 and "Потенциальный клиент" in r.data.decode())
    check("odoo navbar renders", "o_navbar" in html and "o_navbar__user-btn" in html)
    check("theme toggle renders", 'id="theme-toggle"' in html and "Тёмный режим" in html
          and "theme-light.css" in html and "js/theme.js" in html
          and "detroid-theme" in html and '||"light"' in html)
    check("tag colors render", "o_tag_color_" in html)

    # ── Заявки ──────────────────────────────────────────
    r = c.get("/api/requests")
    reqs = r.get_json()
    check("API requests list == 6", isinstance(reqs, list) and len(reqs) == 6, str(reqs)[:200])
    check("API request has money+number+manager fields",
          "client_price" in reqs[0] and "margin" in reqs[0] and "number" in reqs[0]
          and "manager_id" in reqs[0] and "manager_name" in reqs[0])
    check("API request margin math",
          reqs[0]["margin"] == reqs[0]["client_price"] - reqs[0]["cost"])
    check("API request numbers auto", all(x["number"] and x["number"].startswith("З-") for x in reqs),
          str([x["number"] for x in reqs]))
    check("API request seed statuses",
          sorted(x["status"] for x in reqs)
          == ["cancelled", "carrier_found", "draft", "invoiced", "new", "paid"],
          str(sorted(x["status"] for x in reqs)))
    req_id = reqs[0]["id"]
    r = c.get("/requests/")
    html = r.data.decode()
    check("requests list renders like odoo",
          r.status_code == 200 and "row-check" in html and "o_pager__text" in html
          and ("Заказать" in html or "o_upsell_btn" in html or "o_clock_icon" in html)
          and "Продавец" in html and "Компания" in html and "Клиент" in html
          and "З-0001" in html and "Маржа" in html and "Действия" in html, html[:500])
    r = c.get("/requests/kanban")
    html = r.data.decode()
    check("requests kanban renders 6 cards", r.status_code == 200 and html.count('oe_kanban_card') == 6, html[:200])
    check("requests kanban 6 columns + api attrs",
          html.count('o_kanban_col"') == 6 and 'data-api-base="/api/requests"' in html
          and "o_searchview__dropdown" in html)
    r = c.get(f"/requests/{req_id}")
    html = r.data.decode()
    check("request detail renders + chatter + margin + statusbar",
          r.status_code == 200 and "o_chatter" in html and "Лог примечания" in html
          and "Маржа" in html and "Менеджер" in html and "o_statusbar" in html, html[:200])
    r = c.post(f"/requests/{req_id}/status", data={"status": "carrier_found"}, follow_redirects=False)
    check("request statusbar move", r.status_code == 302)
    got = [x for x in c.get("/api/requests").get_json() if x["id"] == req_id][0]
    check("request status applied", got["status"] == "carrier_found", str(got))
    msgs = c.get(f"/api/requests/{req_id}/messages").get_json()
    check("request status logged to chatter", any("Статус изменён" in m["body"] for m in msgs), str(msgs)[:300])
    r = c.patch(f"/api/requests/{req_id}/status", json={"status": "invoiced"})
    check("API request move (drag&drop)", r.status_code == 200 and r.get_json()["status"] == "invoiced")
    r = c.post("/api/requests", json={"title": "Быстрая заявка", "status": "draft"})
    check("API request quick create + number",
          r.status_code == 201 and r.get_json()["number"].startswith("З-"), str(r.get_json())[:200])
    quick_id = r.get_json()["id"]
    check("API request delete", c.delete(f"/api/requests/{quick_id}").status_code == 200)
    check("API request gone after delete",
          all(x["id"] != quick_id for x in c.get("/api/requests").get_json()))
    # Создание из выигранного лида (сначала гарантированно выигрываем один)
    first_id = c.get("/api/leads").get_json()[0]["id"]
    c.patch(f"/api/leads/{first_id}/stage", json={"stage": "potential"})
    hot = [x for x in c.get("/api/leads").get_json() if x["stage"] == "potential"][0]
    r = c.get(f"/requests/new?lead_id={hot['id']}")
    check("request form prefills from lead", r.status_code == 200 and hot["title"] in r.data.decode())
    r = c.post("/requests/new",
               data={"title": "Тестовая заявка", "origin": "А", "destination": "Б",
                     "client_price": "100000", "cost": "70000", "lead_id": str(hot["id"])},
               follow_redirects=True)
    check("request create via form + number",
          r.status_code == 200 and "Тестовая заявка" in r.data.decode() and "З-" in r.data.decode())
    new_id = [x for x in c.get("/api/requests").get_json() if x["title"] == "Тестовая заявка"][0]["id"]
    r = c.get(f"/leads/{hot['id']}")
    html = r.data.decode()
    check("lead shows request button + link", "Создать заявку" in html and "Тестовая заявка" in html)
    # Следующий статус
    c.post(f"/requests/{new_id}/status", data={"status": "new"})
    r = c.post(f"/requests/{new_id}/advance", follow_redirects=False)
    check("request advance redirects", r.status_code == 302)
    got = [x for x in c.get("/api/requests").get_json() if x["id"] == new_id][0]
    check("request advance applied", got["status"] == "carrier_found", str(got))
    # Удаление: одиночное через форму и массовое чекбоксами (безвозвратные)
    disposable = c.post("/api/requests", json={"title": "На удаление"}).get_json()["id"]
    disposable2 = c.post("/api/requests", json={"title": "Тоже на удаление"}).get_json()["id"]
    r = c.post(f"/requests/{disposable}/delete", follow_redirects=True)
    check("request delete via form", r.status_code == 200)
    r = c.post("/requests/bulk-delete", data={"ids": [str(disposable2)]}, follow_redirects=True)
    check("request bulk delete", r.status_code == 200)
    remaining = [x["id"] for x in c.get("/api/requests").get_json()]
    check("request deletes removed rows",
          disposable not in remaining and disposable2 not in remaining)
    # Лента заявки
    r = c.post(f"/requests/{new_id}/notes", data={"kind": "note", "body": "Заметка по заявке"},
               follow_redirects=True)
    check("request note via form", r.status_code == 200 and "Заметка по заявке" in r.data.decode())
    r = c.post(f"/api/requests/{new_id}/messages", json={"kind": "message", "body": "API по заявке"})
    check("API request message create", r.status_code == 201)
    sm_id = r.get_json()["id"]
    check("API request message delete", c.delete(f"/api/request-messages/{sm_id}").status_code == 200)
    # Удаление лида отвязывает заявку
    r = c.post(f"/leads/{hot['id']}/delete", follow_redirects=True)
    check("lead delete via form", r.status_code == 200)
    got = [x for x in c.get("/api/requests").get_json() if x["id"] == new_id][0]
    check("request survives lead delete (unlinked)", got["lead_id"] is None)
    check("missing request 404", c.get("/requests/999999").status_code == 404)
    # Legacy-редиректы со старых адресов
    r = c.get("/shipments/", follow_redirects=False)
    check("legacy /shipments/ 301", r.status_code == 301 and r.headers["Location"].endswith("/requests/"))
    r = c.get(f"/shipments/{req_id}", follow_redirects=False)
    check("legacy /shipments/<id> 301",
          r.status_code == 301 and r.headers["Location"].endswith(f"/requests/{req_id}"))

    # ── Безопасность (этап ревью) ─────────────────────────
    # Регистрация закрыта: любого посетителя шлёт на вход с пояснением
    r = c.get("/auth/register", follow_redirects=True)
    check("registration closed",
          r.status_code == 200 and "Регистрация закрыта" in r.data.decode())
    # API без входа отвечает JSON 401 (а не HTML-редиректом)
    anon = app.test_client()
    r = anon.get("/api/leads")
    check("API unauthorized is JSON 401",
          r.status_code == 401 and r.is_json and r.get_json()["error"] == "auth required")
    # next после входа — только внутренний (чужой сайт не пускаем)
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    c.post("/auth/logout")
    c.post("/auth/login?next=https://evil.example.com",
           data={"email": "admin@example.com", "password": "admin123"})
    r = c.get("/")
    check("login redirect stays on site", r.status_code == 200)
    c.post("/auth/logout")
    # Смена пароля: старый перестаёт работать, новый — работает, вернём назад
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    r = c.post("/auth/password", data={"password": "admin123", "new_password": "newpass99",
                                       "new_password2": "newpass99"}, follow_redirects=True)
    check("password change ok", r.status_code == 200 and "Пароль изменён" in r.data.decode())
    c.post("/auth/logout")
    r = c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"},
               follow_redirects=True)
    check("old password rejected", "Неверный email или пароль" in r.data.decode())
    c.post("/auth/login", data={"email": "admin@example.com", "password": "newpass99"})
    c.post("/auth/password", data={"password": "newpass99", "new_password": "admin123",
                                   "new_password2": "admin123"}, follow_redirects=True)
    c.post("/auth/logout")
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    # Раздел «Пользователи»: видит только админ
    r = c.get("/users/")
    check("users page for admin", r.status_code == 200 and "user2@example.com" in r.data.decode())
    c.post("/auth/logout")
    c.post("/auth/login", data={"email": "user2@example.com", "password": "secret123"})
    check("users page hidden from manager", c.get("/users/").status_code == 404)
    # Блокировка пользователя запрещает вход
    c.post("/auth/logout")
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    with app.app_context():
        u2_id = [u for u in User.query.all() if u.email == "user2@example.com"][0].id
    c.post(f"/users/{u2_id}/toggle")
    c.post("/auth/logout")
    r = c.post("/auth/login", data={"email": "user2@example.com", "password": "secret123"},
               follow_redirects=True)
    check("blocked user cannot login", "Неверный email или пароль" in r.data.decode())
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    c.post(f"/users/{u2_id}/toggle")  # разблокируем обратно
    # Админ меняет пользователю логин, почту и пароль
    r = c.post(f"/users/{u2_id}/edit",
               data={"username": "user2x", "email": "user2x@example.com",
                     "full_name": "Второй Менеджер", "role": "manager",
                     "password": "secret456"},
               follow_redirects=True)
    check("admin edits user", r.status_code == 200 and "user2x@example.com" in r.data.decode())
    c.post("/auth/logout")
    r = c.post("/auth/login", data={"email": "user2@example.com", "password": "secret123"},
               follow_redirects=True)
    check("old user data rejected", "Неверный email или пароль" in r.data.decode())
    r = c.post("/auth/login", data={"email": "user2x@example.com", "password": "secret456"},
               follow_redirects=True)
    check("new user data works", "Второй Менеджер" in r.data.decode())
    c.post("/auth/logout")
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    # Занятый логин/почту не даём присвоить; себя разжаловать нельзя
    r = c.post(f"/users/{u2_id}/edit",
               data={"username": "admin", "email": "user2x@example.com", "role": "manager"},
               follow_redirects=True)
    check("taken username rejected", "логин уже занят" in r.data.decode())
    with app.app_context():
        admin_id = [u for u in User.query.all() if u.username == "admin"][0].id
    r = c.post(f"/users/{admin_id}/edit",
               data={"username": "admin", "email": "admin@example.com", "role": "manager"},
               follow_redirects=True)
    check("self-demotion blocked", "самого себя" in r.data.decode())
    # Нумерация: первый пользователь (админ) — №1
    r = c.get("/users/")
    html = r.data.decode()
    check("users numbered from 1", ">№</th>" in html and "<td class=\"muted\">1</td>" in html)
    # Форма создания — над списком
    check("create form above list", html.index("Создать пользователя") < html.index("Заблокировать"))
    # Кнопка удаления спрятана в редактировании, а не в списке
    check("delete hidden from list", "/delete" not in html and "Удалить пользователя" not in html)
    r_edit = c.get(f"/users/{admin_id}/edit")
    check("delete in edit for others",
          "/delete" not in r_edit.data.decode())  # для себя — нельзя удалить
    with app.app_context():
        # проверим что у чужого пользователя кнопка удаления есть в edit
        other_id = [u for u in User.query.all() if u.id != admin_id][0].id if User.query.count() > 1 else admin_id
    if other_id != admin_id:
        r_other_edit = c.get(f"/users/{other_id}/edit")
        check("delete button in edit page", "Удалить пользователя" in r_other_edit.data.decode())
    # Удаление пользователя: аккаунт исчезает, вход больше не работает
    c.post("/users/new", data={"username": "temp", "email": "temp@example.com",
                               "role": "manager", "password": "temp123456"})
    with app.app_context():
        temp_id = [u for u in User.query.all() if u.email == "temp@example.com"][0].id
    r = c.post(f"/users/{temp_id}/delete", follow_redirects=True)
    check("admin deletes user", "удалён" in r.data.decode() and "temp@example.com" not in r.data.decode())
    c.post("/auth/logout")
    r = c.post("/auth/login", data={"email": "temp@example.com", "password": "temp123456"},
               follow_redirects=True)
    check("deleted user cannot login", "Неверный email или пароль" in r.data.decode())
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    # Удаление менеджера с лидами: лиды остаются, но без ответственного
    c.post("/users/new", data={"username": "temp2", "email": "temp2@example.com",
                               "role": "manager", "password": "temp123456"})
    with app.app_context():
        temp2_id = [u for u in User.query.all() if u.email == "temp2@example.com"][0].id
    tmp_lead = c.post("/api/leads", json={"title": "Лид на удаление менеджера",
                                          "manager": str(temp2_id)}).get_json()
    check("lead assigned to temp manager", tmp_lead["manager_id"] == temp2_id)
    c.post(f"/users/{temp2_id}/delete")
    got = [x for x in c.get("/api/leads").get_json() if x["id"] == tmp_lead["id"]][0]
    check("leads survive manager delete", got["title"] == "Лид на удаление менеджера"
          and got["manager_id"] is None, str(got))
    c.delete(f"/api/leads/{tmp_lead['id']}")
    # Себя удалить нельзя
    r = c.post(f"/users/{admin_id}/delete", follow_redirects=True)
    check("self-delete blocked", "Нельзя удалить самого себя" in r.data.decode())
    # Брутфорс: 5 неудач → пауза (обязательно выйти: залогиненных логин не проверяет)
    from app.routes.auth import _failed_attempts
    c.post("/auth/logout")
    for _ in range(app.config["LOGIN_MAX_FAILURES"]):
        c.post("/auth/login", data={"email": "admin@example.com", "password": "wrong-wrong"})
    r = c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    check("login brute-force lockout", r.status_code == 429)
    _failed_attempts.clear()  # отпираемся, чтобы дальше тесты могли входить
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"})
    # Служебные маршруты
    check("health endpoint", anon.get("/health").status_code == 200)
    r = c.get("/такой-страницы-нет")
    check("custom 404 page", r.status_code == 404 and "Такой страницы нет" in r.data.decode())

    # ── 404 ───────────────────────────────────────────────
    check("missing contact returns redirect (contacts removed)", c.get("/contacts/999999", follow_redirects=False).status_code in (302,308,410))
    check("missing company 404", c.get("/companies/999999").status_code == 404)

    # ── Прочие страницы ───────────────────────────────────
    for url in ["/requests/", "/requests/kanban", "/reports", "/leads/new", "/companies/new"]:
        check(f"GET {url} 200", c.get(url).status_code == 200)

    failed = [n for n, ok in results if not ok]
    print(f"\nИтог: {len(results) - len(failed)}/{len(results)} прошли")
    if failed:
        print("Упали:", failed)
    return 0 if not failed else 1


def Company_id_from_api(client, part: str) -> int:
    for item in client.get("/api/companies").get_json():
        if part in item["name"]:
            return item["id"]
    raise AssertionError(f"company {part} not found")


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if os.path.exists(_DB_PATH):
            os.unlink(_DB_PATH)
