"""Главная — пустая CRM после сброса, готова к новым модулям."""

from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    return {"status": "ok"}


@main_bp.route("/")
@login_required
def dashboard():
    return render_template("dashboard/index.html")
