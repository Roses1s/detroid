"""Дымовой тест CRM — глобальное обновление: только канбан лидов + пользователи.

Запуск:
    python scripts/smoke_test.py
"""

import os
import sys
import tempfile

_fd, _DB_PATH = tempfile.mkstemp(prefix="crm_smoke_", suffix=".db")
os.close(_fd)
os.unlink(_DB_PATH)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "smoke-test-key"
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
        print(f"      -> {extra[:500]}")


def main() -> int:
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    from flask_migrate import upgrade
    with app.app_context():
        upgrade()

    seed.seed()
    seed.seed()

    c = app.test_client()

    # guest -> login
    r = c.get("/", follow_redirects=False)
    check("guest redirect to login", r.status_code == 302 and "/auth/login" in r.headers.get("Location", ""))

    r = c.get("/auth/login")
    html_login = r.data.decode()
    check("login page renders", r.status_code == 200, html_login[:200])

    r = c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"}, follow_redirects=True)
    check("login works -> kanban", r.status_code == 200 and "Лиды" in r.data.decode(), r.data.decode()[:300])

    # dashboard now redirects to kanban
    r = c.get("/", follow_redirects=True)
    check("dashboard redirects to kanban", r.status_code == 200 and "Лиды" in r.data.decode())

    # navbar only leads + users
    html = r.data.decode()
    check("navbar only leads and users", "Лиды" in html and "Пользователи" in html, html[:500])
    check("navbar no companies/requests/reports", "Компании" not in html and "Заявки" not in html and "Отчёты" not in html, html[:500])

    # kanban
    r = c.get("/leads/")
    html = r.data.decode()
    check("kanban renders 7 cards", r.status_code == 200 and html.count('oe_kanban_card') == 7, html[:300])
    check("kanban title is Лиды", "<span class=\"o_breadcrumb__current\">Лиды</span>" in html, html[:300])
    check("kanban no request button", "+ Заявка" not in html, html[:300])

    # list
    r = c.get("/leads/list")
    check("leads list renders", r.status_code == 200 and "Лиды" in r.data.decode())

    # API leads
    r = c.get("/api/leads")
    leads = r.get_json()
    check("API leads list == 7", isinstance(leads, list) and len(leads) == 7, str(leads)[:300])
    lead_id = leads[0]["id"]

    r = c.patch(f"/api/leads/{lead_id}/stage", json={"stage": "potential"})
    check("API move stage", r.status_code == 200 and r.get_json()["stage"] == "potential")

    r = c.post("/api/leads", json={"title": "Тест API", "stage": "lead"})
    check("API quick create", r.status_code == 201, r.data.decode()[:200])

    # search
    r = c.get("/leads/")
    html = r.data.decode()
    check("search panel odoo sections", "Группировать по" in html and "Избранное" in html)

    # detail
    r = c.get(f"/leads/{lead_id}")
    html = r.data.decode()
    check("lead detail renders", r.status_code == 200 and "o_chatter" in html)
    check("detail no request button", "Создать заявку" not in html, html[:500])
    check("detail breadcrumb Лиды", "Лиды" in html and "Лиды (Компании)" not in html)

    # form
    r = c.get(f"/leads/{lead_id}/edit")
    html = r.data.decode()
    check("lead form renders without company", r.status_code == 200 and "Компания" not in html, html[:400])

    # delete via API
    new_id = c.post("/api/leads", json={"title": "На удаление"}).get_json()["id"]
    check("API delete", c.delete(f"/api/leads/{new_id}").status_code == 200)

    # chatter
    r = c.post(f"/leads/{lead_id}/notes", data={"kind": "note", "body": "Тест заметка"}, follow_redirects=True)
    check("note create via form", r.status_code == 200 and "Тест заметка" in r.data.decode())

    # users only for admin
    r = c.get("/users/")
    check("users page for admin", r.status_code == 200 and "admin@example.com" in r.data.decode())

    # create second user
    r = c.post("/users/new", data={"username": "user2", "email": "user2@example.com", "full_name": "Второй", "role": "manager", "password": "secret123"}, follow_redirects=True)
    check("admin creates user", r.status_code == 200)

    c.post("/auth/logout", follow_redirects=True)
    c.post("/auth/login", data={"email": "user2@example.com", "password": "secret123"}, follow_redirects=True)
    check("users hidden from manager", c.get("/users/").status_code == 404)

    # back to admin
    c.post("/auth/logout", follow_redirects=True)
    c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"}, follow_redirects=True)

    # health
    anon = app.test_client()
    check("health endpoint", anon.get("/health").status_code == 200)

    # 404
    r = c.get("/такой-страницы-нет")
    check("custom 404 page", r.status_code == 404 and "Такой страницы нет" in r.data.decode())

    # old modules should be 404
    check("companies 404", c.get("/companies").status_code == 404)
    check("requests 404", c.get("/requests/").status_code == 404)
    check("contacts 404 or redirect", c.get("/contacts", follow_redirects=False).status_code in (404, 302, 308, 410))
    check("reports redirects to kanban", c.get("/reports", follow_redirects=False).status_code in (301, 302))

    # other pages
    for url in ["/leads/new"]:
        check(f"GET {url} 200", c.get(url).status_code == 200)

    # registration closed
    r = c.get("/auth/register", follow_redirects=True)
    check("registration closed", r.status_code == 200 and "Регистрация закрыта" in r.data.decode())

    # API unauthorized
    r = anon.get("/api/leads")
    check("API unauthorized is JSON 401", r.status_code == 401 and r.is_json)

    failed = [n for n, ok in results if not ok]
    print(f"\nИтог: {len(results) - len(failed)}/{len(results)} прошли")
    if failed:
        print("Упали:", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if os.path.exists(_DB_PATH):
            os.unlink(_DB_PATH)
