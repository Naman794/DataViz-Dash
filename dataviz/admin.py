"""Protected account administration routes."""

from __future__ import annotations

from functools import wraps
from math import ceil

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import current_user, is_admin_user, valid_csrf_token
from .database import get_database
from .storage import Store

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Sign in with an administrator account to continue.", "error")
            return redirect(url_for("auth.account"))
        if not is_admin_user(user):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def repository():
    return Store(get_database())


def return_to_dashboard():
    query = request.form.get("return_query", "").strip()
    return redirect(f"{url_for('admin.dashboard')}?{query}" if query else url_for("admin.dashboard"))


def protected_admin_target(target) -> bool:
    return target is not None and is_admin_user(target)


@bp.get("")
@admin_required
def dashboard():
    search = request.args.get("q", "").strip()[:254]
    plan = request.args.get("plan", "").strip().lower()
    status = request.args.get("status", "").strip().lower()
    page = max(1, request.args.get("page", 1, type=int))
    page_size = 25
    store = repository()
    total_users = store.count_users(search, plan, status)
    page_count = max(1, ceil(total_users / page_size))
    page = min(page, page_count)
    users = store.list_users(
        search, plan, status, limit=page_size, skip=(page - 1) * page_size
    )
    for user in users:
        user["is_admin"] = is_admin_user({"email": user["email"]})
    return render_template(
        "admin.html",
        summary=store.admin_summary(),
        users=users,
        recent_activity=store.recent_activity(),
        recent_actions=store.recent_admin_actions(),
        filters={"q": search, "plan": plan, "status": status},
        pagination={"page": page, "page_count": page_count, "total": total_users},
        return_query=request.query_string.decode("utf-8"),
    )


@bp.post("/users/<user_id>/plan")
@admin_required
def update_plan(user_id):
    if not valid_csrf_token(request.form.get("csrf_token", "")):
        flash("Your form expired. Please try again.", "error")
        return return_to_dashboard()

    plan = request.form.get("plan", "").strip().lower()
    if plan not in {"free", "pro"}:
        abort(400)
    store = repository()
    target = store.get_user(user_id)
    if target is None:
        abort(404)
    previous = "pro" if target.get("plan") == "pro" else "free"
    if previous == plan:
        flash(f"{target['email']} is already on the {plan.title()} plan.", "success")
        return return_to_dashboard()

    updated = store.update_user_plan(user_id, plan)
    store.record_admin_action(
        current_user(), target, "membership.changed", previous, plan
    )
    store.record_activity(
        user_id,
        "membership.changed",
        {"from": previous, "to": plan, "source": "admin"},
    )
    flash(f"Updated {updated['email']} to the {plan.title()} plan.", "success")
    return return_to_dashboard()


@bp.post("/users/<user_id>/status")
@admin_required
def update_status(user_id):
    if not valid_csrf_token(request.form.get("csrf_token", "")):
        flash("Your form expired. Please try again.", "error")
        return return_to_dashboard()

    status = request.form.get("status", "").strip().lower()
    if status not in {"active", "suspended"}:
        abort(400)
    store = repository()
    target = store.get_user(user_id)
    if target is None:
        abort(404)
    if protected_admin_target(target):
        flash("Administrator accounts cannot be suspended from this dashboard.", "error")
        return return_to_dashboard()

    previous = "suspended" if target.get("status") == "suspended" else "active"
    if previous == status:
        flash(f"{target['email']} is already {status}.", "success")
        return return_to_dashboard()

    updated = store.update_user_status(user_id, status)
    store.record_admin_action(
        current_user(), target, "account.status_changed", previous, status
    )
    store.record_activity(
        user_id,
        "account.status_changed",
        {"from": previous, "to": status, "source": "admin"},
    )
    verb = "Suspended" if status == "suspended" else "Reactivated"
    flash(f"{verb} {updated['email']}.", "success")
    return return_to_dashboard()
