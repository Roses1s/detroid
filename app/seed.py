"""Демо-данные: администратор + лиды. Только канбан лидов — единственный модуль.

Запуск:
    python -m app.seed
    docker compose exec app python -m app.seed

Пароль берётся из ADMIN_PASSWORD (.env). Если нет — генерируется случайный и печатается один раз.
"""

import os
import secrets
import string

from . import create_app
from .extensions import db
from .models import Lead, LeadMessage, LeadStage, MessageKind, User

DEMO_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")


def _admin_password() -> str:
    env_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if env_password:
        return env_password
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _seed_admin() -> User:
    admin = User.query.filter_by(email=DEMO_EMAIL).first()
    if not admin:
        password = _admin_password()
        admin = User(
            username="admin",
            email=DEMO_EMAIL,
            full_name="Администратор",
            role="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        if os.environ.get("ADMIN_PASSWORD"):
            print(f"[seed] создан пользователь {DEMO_EMAIL} (пароль из ADMIN_PASSWORD)")
        else:
            print(f"[seed] создан пользователь {DEMO_EMAIL}")
            print(f"[seed] СЛУЧАЙНЫЙ ПАРОЛЬ АДМИНИСТРАТОРА: {password}")
            print("[seed] ^^ Сохраните его!")
    else:
        print("[seed] пользователь уже существует, пропускаю")
    return admin


def _seed_leads(admin: User) -> None:
    if Lead.query.count() > 0:
        print("[seed] лиды уже есть, пропускаю")
        return
    demo = [
        ("ООО «Восток-Трейд» — Перевозка Москва — Казань", "Иван Петров", "+7 (900) 111-22-33", "lead", 120000, 2, "авто,срочно"),
        ("АО «Север-Логистик» — Доставка оборудования в СПб", "Ольга Смирнова", "+7 (900) 222-33-44", "no_answer", 85000, 1, "оборудование"),
        ("ИП Контракт — еженедельные рейсы", "Пётр Сидоров", "+7 (900) 333-44-55", "lpr", 450000, 3, "контракт,vip"),
        ("ООО Мебель — Перевозка мебели (офис)", "Анна Кузнецова", "+7 (900) 444-55-66", "gatekeeper", 60000, 0, "мебель"),
        ("ООО Холод — Холодовая цепь: продукты", "Дмитрий Орлов", "+7 (900) 555-66-77", "potential", 210000, 2, "рефрижератор"),
        ("ТОО Казахстан — Экспорт в Казахстан", "Айгерим Нурланова", "+7 (900) 666-77-88", "potential", 780000, 3, "вэд,контракт"),
        ("ООО Разовый — Разовый рейс", "Сергей Волков", "+7 (900) 777-88-99", "gone", 40000, 0, "разовый"),
    ]
    for title, contact, phone, stage, revenue, priority, tags in demo:
        db.session.add(
            Lead(
                title=title,
                contact_name=contact,
                phone=phone,
                source="демо",
                expected_revenue=revenue,
                stage=LeadStage(stage),
                priority=priority,
                tags=tags,
                manager_id=admin.id,
                notes="Демо-лид. Модуль лидов — единственный в CRM сейчас.",
            )
        )
    db.session.commit()
    print("[seed] создано 7 демо-лидов")


def _seed_messages(admin: User) -> None:
    if LeadMessage.query.count() > 0:
        print("[seed] записи в ленте уже есть, пропускаю")
        return
    lead = Lead.query.filter(Lead.title.ilike("%Восток-Трейд%")).first()
    if not lead:
        return
    db.session.add_all([
        LeadMessage(lead=lead, author=admin, kind=MessageKind.NOTE,
                    body="Позвонил клиенту: подтвердили объём 20 паллет, ждут КП до пятницы."),
        LeadMessage(lead=lead, author=admin, kind=MessageKind.MESSAGE,
                    body="Отправил коммерческое предложение на email. Жду ответ."),
    ])
    db.session.commit()
    print("[seed] созданы 2 демо-записи в ленте лида")


def clear_all() -> None:
    app = create_app()
    with app.app_context():
        from .models import Company, SavedFilter
        from .models.lead import LeadMessage as LM
        from .models.request import Request as ReqModel, RequestMessage
        print("[clear] Удаляю все карточки CRM...")
        try:
            db.session.query(RequestMessage).delete()
        except Exception:
            pass
        try:
            db.session.query(LM).delete()
        except Exception:
            pass
        try:
            db.session.query(ReqModel).delete()
        except Exception:
            pass
        try:
            db.session.query(Lead).delete()
        except Exception:
            pass
        try:
            from .models import Contact
            db.session.query(Contact).delete()
        except Exception:
            pass
        try:
            db.session.query(Company).delete()
        except Exception:
            pass
        db.session.query(SavedFilter).delete()
        db.session.commit()
        print("[clear] Готово: все лиды удалены, остальные модули очищены.")


def seed() -> None:
    app = create_app()
    with app.app_context():
        admin = _seed_admin()
        _seed_leads(admin)
        _seed_messages(admin)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_all()
    else:
        seed()
