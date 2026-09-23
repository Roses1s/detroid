"""Демо-данные: администратор + лиды + компании + контакты + заявки.

Запуск:
    python -m app.seed            (локально, из корня проекта)
    docker compose exec app python -m app.seed   (в Docker)

Скрипт идемпотентный ПО КАЖДОЙ СУЩНОСТИ: догружает только то,
чего ещё нет. Поэтому безопасно запускать после каждого деплоя:
новые демо-данные появятся, а введённые вручную — не пострадают.

Пароль администратора берётся из переменной ADMIN_PASSWORD (.env).
Если её нет — генерируется случайный и ПЕЧАТАЕТСЯ ОДИН РАЗ: сохраните его!
(Старый публичный пароль «из репозитория» больше не используется.)
"""
import os
import secrets
import string
from datetime import date, timedelta

from . import create_app
from .extensions import db
from .models import (
    Company, Contact, Lead, LeadMessage, LeadStage, MessageKind,
    Request, RequestMessage, RequestStatus, User,
)

DEMO_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")


def _admin_password() -> str:
    """ADMIN_PASSWORD из окружения либо случайный 16-символьный."""
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
            print(f"[seed] создан пользователь {DEMO_EMAIL} (пароль взят из ADMIN_PASSWORD)")
        else:
            print(f"[seed] создан пользователь {DEMO_EMAIL}")
            print(f"[seed] СЛУЧАЙНЫЙ ПАРОЛЬ АДМИНИСТРАТОРА: {password}")
            print("[seed] ^^ Сохраните его! Второй раз он не покажется.")
    else:
        print("[seed] пользователь уже существует, пропускаю")
    return admin


def _seed_leads(admin: User) -> None:
    if Lead.query.count() > 0:
        print("[seed] лиды уже есть, пропускаю")
        return
    demo = [
        ("Перевозка Москва — Казань", "Иван Петров", "+7 (900) 111-22-33", "lead", 120000, 2, "авто,срочно"),
        ("Доставка оборудования в СПб", "Ольга Смирнова", "+7 (900) 222-33-44", "no_answer", 85000, 1, "оборудование"),
        ("Контракт: еженедельные рейсы", "Пётр Сидоров", "+7 (900) 333-44-55", "lpr", 450000, 3, "контракт,vip"),
        ("Перевозка мебели (офис)", "Анна Кузнецова", "+7 (900) 444-55-66", "gatekeeper", 60000, 0, "мебель"),
        ("Холодовая цепь: продукты", "Дмитрий Орлов", "+7 (900) 555-66-77", "potential", 210000, 2, "рефрижератор"),
        ("Экспорт в Казахстан", "Айгерим Нурланова", "+7 (900) 666-77-88", "potential", 780000, 3, "вэд,контракт"),
        ("Разовый рейс (уехали)", "Сергей Волков", "+7 (900) 777-88-99", "gone", 40000, 0, "разовый"),
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
                notes="Демо-лид. Можно редактировать и удалять.",
            )
        )
    db.session.commit()
    print("[seed] создано 7 демо-лидов")


def _seed_companies() -> None:
    if Company.query.count() > 0:
        print("[seed] компании уже есть, пропускаю")
        return
    acme = Company(name="ООО «Восток-Трейд»", phone="+7 (495) 100-20-30",
                   email="info@vostok-trade.example", address="Москва, ул. Примерная, 1")
    nord = Company(name="АО «Север-Логистик»", phone="+7 (812) 200-40-60",
                   email="sales@sever-log.example", address="Санкт-Петербург, Невский пр., 10")
    db.session.add_all([acme, nord])
    db.session.commit()
    print("[seed] созданы 2 демо-компании")


def _seed_contacts() -> None:
    if Contact.query.count() > 0:
        print("[seed] контакты уже есть, пропускаю")
        return
    acme = Company.query.filter(Company.name.ilike("%Восток%")).first()
    nord = Company.query.filter(Company.name.ilike("%Север%")).first()
    ivan = Contact(first_name="Иван", last_name="Петров",
                   phone="+7 (900) 111-22-33", email="petrov@vostok-trade.example",
                   position="Менеджер по закупкам", company=acme,
                   notes="Демо-контакт. Можно редактировать и удалять.")
    aigerim = Contact(first_name="Айгерим", last_name="Нурланова",
                      phone="+7 (900) 666-77-88", email="aigerim@sever-log.example",
                      position="Директор по логистике", company=nord,
                      notes="Демо-контакт. Можно редактировать и удалять.")
    db.session.add_all([ivan, aigerim])
    db.session.flush()
    # Привязываем пару лидов для демонстрации связей
    lead1 = Lead.query.filter_by(title="Перевозка Москва — Казань").first()
    if lead1:
        lead1.contact = ivan
        lead1.company = acme
    lead6 = Lead.query.filter_by(title="Экспорт в Казахстан").first()
    if lead6:
        lead6.contact = aigerim
        lead6.company = nord
    db.session.commit()
    print("[seed] созданы 2 демо-контакта и привязаны к лидам")


def _seed_messages(admin: User) -> None:
    if LeadMessage.query.count() > 0:
        print("[seed] записи в ленте уже есть, пропускаю")
        return
    lead = Lead.query.filter_by(title="Перевозка Москва — Казань").first()
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


def _seed_requests(admin: User) -> None:
    if Request.query.count() > 0:
        print("[seed] заявки уже есть, пропускаю")
        return
    acme = Company.query.filter(Company.name.ilike("%Восток%")).first()
    nord = Company.query.filter(Company.name.ilike("%Север%")).first()
    ivan = Contact.query.filter_by(first_name="Иван", last_name="Петров").first()
    aigerim = Contact.query.filter_by(first_name="Айгерим", last_name="Нурланова").first()
    lead_kazan = Lead.query.filter_by(title="Перевозка Москва — Казань").first()
    lead_export = Lead.query.filter_by(title="Экспорт в Казахстан").first()
    today = date.today()
    demo = [
        Request(
            title="Паллеты Москва → Казань (20 шт)", origin="Москва", destination="Казань",
            cargo_type="Паллеты, 20 шт", weight=8500, volume=32,
            transport_type="авто", status=RequestStatus.NEW,
            load_date=today + timedelta(days=2), unload_date=today + timedelta(days=4),
            client_price=150000, cost=110000,
            carrier="ИП Дальнобойщиков", driver_name="Олег Дальнобойщиков",
            driver_phone="+7 (900) 010-20-30", vehicle_number="А123БВ 777",
            manager=admin, lead=lead_kazan, company=acme, contact=ivan,
            notes="Демо-заявка. Можно редактировать и удалять.",
        ),
        Request(
            title="Оборудование СПб → Москва", origin="Санкт-Петербург", destination="Москва",
            cargo_type="Оборудование, 2 ящика", weight=1200, volume=8,
            transport_type="авто", status=RequestStatus.CARRIER_FOUND,
            load_date=today - timedelta(days=1), unload_date=today + timedelta(days=1),
            client_price=95000, cost=70000,
            carrier="ООО «Быстрые колёса»", driver_name="Сергей Руль",
            driver_phone="+7 (900) 040-50-60", vehicle_number="М456ОР 78",
            manager=admin, lead=lead_export, company=nord, contact=aigerim,
            notes="Демо-заявка. Можно редактировать и удалять.",
        ),
        Request(
            title="Сборный груз Екатеринбург → Новосибирск", origin="Екатеринбург",
            destination="Новосибирск", cargo_type="ТНП, сборный груз",
            transport_type="авто", status=RequestStatus.DRAFT,
            client_price=0, cost=0,
            notes="Черновик: ждём подтверждение объёма от клиента.",
        ),
        Request(
            title="Продукты Казань → Уфа", origin="Казань", destination="Уфа",
            cargo_type="Продукты питания", weight=5000, volume=20,
            transport_type="авто", status=RequestStatus.PAID,
            load_date=today - timedelta(days=9), unload_date=today - timedelta(days=7),
            client_price=80000, cost=62000,
            carrier="ИП Дальнобойщиков", driver_name="Олег Дальнобойщиков",
            driver_phone="+7 (900) 010-20-30", vehicle_number="А123БВ 777",
            manager=admin, company=acme,
            notes="Оплачена, документы получены.",
        ),
        Request(
            title="Мебель Москва → Воронеж", origin="Москва", destination="Воронеж",
            cargo_type="Мебель", transport_type="авто", status=RequestStatus.CANCELLED,
            client_price=45000, cost=35000, manager=admin, company=acme,
            notes="Отменена клиентом: перенесли переезд на следующий месяц.",
        ),
        Request(
            title="ТНП Москва → СПб", origin="Москва", destination="Санкт-Петербург",
            cargo_type="ТНП, 10 паллет", weight=4000, volume=15,
            transport_type="авто", status=RequestStatus.INVOICED,
            load_date=today - timedelta(days=3), unload_date=today - timedelta(days=1),
            client_price=120000, cost=90000,
            carrier="ООО «Быстрые колёса»", driver_name="Сергей Руль",
            driver_phone="+7 (900) 040-50-60", vehicle_number="М456ОР 78",
            manager=admin, company=nord, contact=aigerim,
            notes="Счёт выставлен, ждём оплату.",
        ),
    ]
    db.session.add_all(demo)
    db.session.flush()
    for req in demo:
        req.assign_number()
    db.session.add(
        RequestMessage(request=demo[1], author=admin, kind=MessageKind.NOTE,
                       body="Водитель на связи: прошёл Тверь, идёт по графику.")
    )
    db.session.commit()
    print("[seed] созданы 6 демо-заявок и запись в ленте")


def seed() -> None:
    app = create_app()
    with app.app_context():
        # ВАЖНО: никакого db.create_all()! Таблицы создаются ТОЛЬКО миграциями.
        # create_all здесь однажды уже создал таблицу мимо миграций, и следующий
        # upgrade упал с "relation already exists" (сервер, ЭТАП 4).
        admin = _seed_admin()
        _seed_leads(admin)
        _seed_companies()
        _seed_contacts()
        _seed_messages(admin)
        _seed_requests(admin)


if __name__ == "__main__":
    seed()
