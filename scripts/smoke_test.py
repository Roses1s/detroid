"""Минимальный smoke test для пустой CRM после мягкого сброса."""

import os
import sys
import tempfile

_fd, _DB_PATH = tempfile.mkstemp(prefix="crm_smoke_", suffix=".db")
os.close(_fd)
try:
    os.unlink(_DB_PATH)
except FileNotFoundError:
    pass
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "smoke-test-key"
os.environ["ADMIN_PASSWORD"] = "admin123"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, seed  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f" [{extra}]" if extra and not cond else ""))
    if not cond and extra:
        print(f"      -> {extra[:500]}")


def main():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    from flask_migrate import upgrade
    with app.app_context():
        upgrade()

    seed.seed()

    c = app.test_client()

    r = c.get("/", follow_redirects=False)
    check("guest redirect to login", r.status_code == 302 and "/auth/login" in r.headers.get("Location", ""))

    r = c.get("/auth/login")
    check("login page renders", r.status_code == 200)

    r = c.post("/auth/login", data={"email": "admin@example.com", "password": "admin123"}, follow_redirects=True)
    check("login works", r.status_code == 200 and "CRM с нуля" in r.data.decode(), r.data.decode()[:300])

    r = c.get("/")
    html = r.data.decode()
    check("dashboard renders empty", r.status_code == 200 and "Чистая CRM" in html)
    # В navbar не должно быть ссылки /leads/, но в контенте может упоминаться "Лиды v2" как пример
    check("navbar only users", "Пользователи" in html and 'href="/leads/' not in html)

    r = c.get("/users/")
    check("users page for admin", r.status_code == 200 and "admin@example.com" in r.data.decode())

    check("health endpoint", c.get("/health").status_code == 200)

    r = c.get("/такой-страницы-нет")
    check("custom 404", r.status_code == 404)

    failed = [n for n, ok in results if not ok]
    print(f"\nИтог: {len(results)-len(failed)}/{len(results)} прошли")
    if failed:
        print("Упали:", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if os.path.exists(_DB_PATH):
            os.unlink(_DB_PATH)
