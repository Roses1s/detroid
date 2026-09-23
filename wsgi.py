"""Точка входа для Gunicorn и `flask run`.

Gunicorn запускается так (см. docker-compose.yml):
    gunicorn --bind 0.0.0.0:5000 'wsgi:app'
"""
from app import create_app

app = create_app()
