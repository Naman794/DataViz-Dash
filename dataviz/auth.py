"""Email/password account routes for persistent workspaces."""

from __future__ import annotations

import hmac
import re
import secrets

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_database
from .plans import resolve_plan
from .storage import Store

bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user():
    if "current_user" not in g:
        user_id = session.get("user_id")
        g.current_user = Store(get_database()).get_user(user_id) if user_id else None
        if g.current_user is not None and g.current_user.get("status") == "suspended":
            g.current_user = None
            session.clear()
            session["owner_id"] = secrets.token_urlsafe(24)
            session["csrf_token"] = secrets.token_urlsafe(32)
        elif user_id and g.current_user is None:
            session.pop("user_id", None)
            session["owner_id"] = secrets.token_urlsafe(24)
        elif g.current_user is not None:
            session["owner_id"] = str(g.current_user["_id"])
    return g.current_user


def is_admin_user(user=None) -> bool:
    user = current_user() if user is None else user
    if user is None:
        return False
    configured = current_app.config.get("ADMIN_EMAILS", ())
    if isinstance(configured, str):
        configured = configured.split(",")
    admin_emails = {str(email).strip().lower() for email in configured}
    return normalize_email(user.get("email", "")) in admin_emails


def csrf_token():
    return session.setdefault("csrf_token", secrets.token_urlsafe(32))


def valid_csrf_token(value: str) -> bool:
    expected = session.get("csrf_token", "")
    return bool(expected and value and hmac.compare_digest(expected, value))


def normalize_email(value: str) -> str:
    return value.strip().lower()


def establish_account_session(user, previous_owner_id: str | None = None):
    user_id = str(user["_id"])
    repository = Store(get_database())
    if previous_owner_id:
        repository.claim_workspace(previous_owner_id, user_id)
    session.clear()
    session["user_id"] = user_id
    session["owner_id"] = user_id
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True
    g.current_user = user


@bp.before_app_request
def synchronize_account_workspace():
    current_user()


@bp.app_context_processor
def inject_account_context():
    user = current_user()
    return {
        "account_user": user,
        "account_plan": resolve_plan(user),
        "account_is_admin": is_admin_user(user),
        "csrf_token": csrf_token,
    }


@bp.get("/account")
def account():
    user = current_user()
    repository = Store(get_database())
    usage = None
    if user:
        user_id = str(user["_id"])
        usage = {
            "datasets": repository.count_datasets(user_id),
            "dashboards": repository.count_dashboards(user_id),
        }
    return render_template("account.html", user=user, usage=usage)


@bp.post("/account/register")
def register():
    if not valid_csrf_token(request.form.get("csrf_token", "")):
        flash("Your form expired. Please try again.", "error")
        return redirect(url_for("auth.account"))

    email = normalize_email(request.form.get("email", ""))
    password = request.form.get("password", "")
    confirmation = request.form.get("password_confirmation", "")
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        flash("Enter a valid email address.", "error")
        return redirect(url_for("auth.account"))
    if not 10 <= len(password) <= 128:
        flash("Password must contain 10 to 128 characters.", "error")
        return redirect(url_for("auth.account"))
    if password != confirmation:
        flash("Password confirmation does not match.", "error")
        return redirect(url_for("auth.account"))

    repository = Store(get_database())
    try:
        user = repository.create_user(email, generate_password_hash(password))
    except DuplicateKeyError:
        flash("An account already exists for that email address.", "error")
        return redirect(url_for("auth.account"))

    establish_account_session(user, session.get("owner_id"))
    repository.record_login(str(user["_id"]), "account.registered")
    flash("Account created. Your workspace is now attached to this account.", "success")
    return redirect(url_for("main.index"))


@bp.post("/account/login")
def login():
    if not valid_csrf_token(request.form.get("csrf_token", "")):
        flash("Your form expired. Please try again.", "error")
        return redirect(url_for("auth.account"))

    email = normalize_email(request.form.get("email", ""))
    password = request.form.get("password", "")
    repository = Store(get_database())
    user = repository.get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Email or password is incorrect.", "error")
        return redirect(url_for("auth.account"))
    if user.get("status") == "suspended":
        flash("This account is suspended. Contact the administrator.", "error")
        return redirect(url_for("auth.account"))

    establish_account_session(user, session.get("owner_id"))
    repository.record_login(str(user["_id"]))
    flash("Signed in successfully.", "success")
    return redirect(url_for("main.index"))


@bp.post("/account/logout")
def logout():
    if not valid_csrf_token(request.form.get("csrf_token", "")):
        flash("Your form expired. Please try again.", "error")
        return redirect(url_for("auth.account"))
    user = current_user()
    if user is not None:
        Store(get_database()).record_activity(str(user["_id"]), "account.logout")
    session.clear()
    session["owner_id"] = secrets.token_urlsafe(24)
    session["csrf_token"] = secrets.token_urlsafe(32)
    flash("You have signed out.", "success")
    return redirect(url_for("main.index"))
