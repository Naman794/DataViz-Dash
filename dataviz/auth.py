"""Email/password account routes for persistent workspaces."""

from __future__ import annotations

import hmac
import re
import secrets

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
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
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
        client_kwargs={"scope": "openid email profile"},
    )


def google_auth_enabled() -> bool:
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )


def google_redirect_uri() -> str:
    return current_app.config.get("GOOGLE_REDIRECT_URI") or url_for(
        "auth.google_callback", _external=True
    )



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
        "google_auth_enabled": google_auth_enabled(),
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
            "source_size_bytes": repository.total_source_bytes(user_id),
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


@bp.get("/account/google")
def google_login():
    if current_user() is not None:
        return redirect(url_for("auth.account"))
    if not google_auth_enabled():
        flash("Google sign-in is not configured yet.", "error")
        return redirect(url_for("auth.account"))

    google = oauth.create_client("google")
    if google is None:
        flash("Google sign-in is temporarily unavailable.", "error")
        return redirect(url_for("auth.account"))
    return google.authorize_redirect(google_redirect_uri())


@bp.get("/account/google/callback")
def google_callback():
    if not google_auth_enabled():
        flash("Google sign-in is not configured yet.", "error")
        return redirect(url_for("auth.account"))

    google = oauth.create_client("google")
    if google is None:
        flash("Google sign-in is temporarily unavailable.", "error")
        return redirect(url_for("auth.account"))

    try:
        token = google.authorize_access_token()
        userinfo = token.get("userinfo") or {}
    except (OAuthError, KeyError, TypeError, ValueError) as exc:
        current_app.logger.warning("Google sign-in failed: %s", exc)
        flash("Google sign-in could not be completed. Please try again.", "error")
        return redirect(url_for("auth.account"))

    email = normalize_email(str(userinfo.get("email", "")))
    subject = str(userinfo.get("sub", "")).strip()
    email_verified = userinfo.get("email_verified")
    if (
        not subject
        or len(subject) > 255
        or len(email) > 254
        or not EMAIL_PATTERN.fullmatch(email)
        or email_verified not in {True, "true", 1}
    ):
        flash("Google did not return a verified email address.", "error")
        return redirect(url_for("auth.account"))

    repository = Store(get_database())
    user = repository.get_user_by_google_subject(subject)
    created = False
    try:
        if user is None:
            user = repository.get_user_by_email(email)
            if user is not None:
                linked_subject = user.get("google_subject")
                if linked_subject and linked_subject != subject:
                    flash(
                        "That email is already linked to another Google account.",
                        "error",
                    )
                    return redirect(url_for("auth.account"))
                user = repository.link_google_identity(str(user["_id"]), subject)
            else:
                password_hash = generate_password_hash(secrets.token_urlsafe(48))
                user = repository.create_user(email, password_hash, subject)
                created = True
    except DuplicateKeyError:
        flash("That Google account is already linked to another user.", "error")
        return redirect(url_for("auth.account"))

    if user is None:
        flash("Google sign-in could not be completed. Please try again.", "error")
        return redirect(url_for("auth.account"))
    if user.get("status") == "suspended":
        flash("This account is suspended. Contact the administrator.", "error")
        return redirect(url_for("auth.account"))

    previous_owner_id = session.get("owner_id")
    establish_account_session(user, previous_owner_id)
    event_type = "account.google_registered" if created else "account.google_login"
    repository.record_login(str(user["_id"]), event_type)
    flash(
        "Account created with Google." if created else "Signed in with Google.",
        "success",
    )
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
