from tests.test_auth import csrf_token, login, logout, register
from tests.test_routes import upload_dataset


def test_admin_dashboard_requires_allowlisted_account(app):
    anonymous = app.test_client()
    assert anonymous.get("/admin").status_code == 302

    regular = app.test_client()
    assert register(regular).status_code == 302
    assert regular.get("/admin").status_code == 403


def test_admin_can_review_usage_and_change_membership(app):
    member = app.test_client()
    assert register(member, "member@example.com").status_code == 302
    upload_dataset(member)

    admin = app.test_client()
    assert register(admin, "admin@example.com").status_code == 302
    page = admin.get("/admin")

    assert page.status_code == 200
    assert b"Account administration" in page.data
    assert b"member@example.com" in page.data
    assert b"1 datasets" in page.data
    assert b"Dataset Uploaded" in page.data

    database = app.extensions["mongo_db"]
    member_user = database.users.find_one({"email": "member@example.com"})
    response = admin.post(
        f"/admin/users/{member_user['_id']}/plan",
        data={"csrf_token": csrf_token(admin), "plan": "pro"},
    )

    assert response.status_code == 302
    assert database.users.find_one({"_id": member_user["_id"]})["plan"] == "pro"
    audit = database.admin_audit.find_one({"target_email": "member@example.com"})
    assert audit["action"] == "membership.changed"
    assert audit["previous_value"] == "free"
    assert audit["new_value"] == "pro"


def test_admin_can_suspend_and_reactivate_a_member(app):
    member = app.test_client()
    assert register(member, "member@example.com").status_code == 302
    database = app.extensions["mongo_db"]
    member_user = database.users.find_one({"email": "member@example.com"})

    admin = app.test_client()
    assert register(admin, "admin@example.com").status_code == 302
    suspended = admin.post(
        f"/admin/users/{member_user['_id']}/status",
        data={"csrf_token": csrf_token(admin), "status": "suspended"},
    )
    assert suspended.status_code == 302
    assert database.users.find_one({"_id": member_user["_id"]})["status"] == "suspended"

    # An existing account session loses access to its persistent workspace.
    account = member.get("/account")
    assert b"Create an account" in account.data
    failed_login = login(member, "member@example.com")
    assert failed_login.status_code == 302
    assert b"account is suspended" in member.get("/account").data

    reactivated = admin.post(
        f"/admin/users/{member_user['_id']}/status",
        data={"csrf_token": csrf_token(admin), "status": "active"},
    )
    assert reactivated.status_code == 302
    assert login(member, "member@example.com").status_code == 302
    assert b"member@example.com" in member.get("/account").data


def test_admin_account_cannot_be_suspended(app):
    admin = app.test_client()
    assert register(admin, "admin@example.com").status_code == 302
    database = app.extensions["mongo_db"]
    admin_user = database.users.find_one({"email": "admin@example.com"})

    response = admin.post(
        f"/admin/users/{admin_user['_id']}/status",
        data={"csrf_token": csrf_token(admin), "status": "suspended"},
    )

    assert response.status_code == 302
    assert database.users.find_one({"_id": admin_user["_id"]})["status"] == "active"
    assert database.admin_audit.count_documents({}) == 0
    assert b"Administrator accounts cannot be suspended" in admin.get("/admin").data


def test_admin_mutations_require_csrf(app):
    member = app.test_client()
    assert register(member, "member@example.com").status_code == 302
    assert logout(member).status_code == 302
    database = app.extensions["mongo_db"]
    member_user = database.users.find_one({"email": "member@example.com"})

    admin = app.test_client()
    assert register(admin, "admin@example.com").status_code == 302
    response = admin.post(
        f"/admin/users/{member_user['_id']}/plan",
        data={"csrf_token": "invalid", "plan": "pro"},
    )

    assert response.status_code == 302
    assert database.users.find_one({"_id": member_user["_id"]})["plan"] == "free"
    assert database.admin_audit.count_documents({}) == 0


def test_admin_filters_accounts(app):
    first = app.test_client()
    second = app.test_client()
    admin = app.test_client()
    register(first, "first@example.com")
    register(second, "second@example.com")
    register(admin, "admin@example.com")

    page = admin.get("/admin?q=first%40example.com")
    account_table = page.data.split(b"Recent account activity", 1)[0]
    assert b"first@example.com" in account_table
    assert b"second@example.com" not in account_table
