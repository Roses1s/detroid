# Образ Flask-приложения.
# Собирается из КОРНЯ проекта: docker compose build
# (контекст — корень, чтобы были видны wsgi.py и папка app/).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# Системные пакеты для сборки psycopg2 и healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копируем весь проект (wsgi.py + папка app/)
COPY wsgi.py ./wsgi.py
COPY app/ ./app/

EXPOSE 5000

# Команда переопределена в docker-compose.yml (миграции + seed + gunicorn).
# Дефолт на случай запуска образа напрямую:
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "wsgi:app"]
