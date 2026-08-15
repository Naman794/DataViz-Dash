from flask import redirect

import dataviz.auth as auth_module
from tests.test_routes import upload_dataset


def csrf_token(client):
    client.get("/account")
    with client.session_transaction() as session:
        return session["csrf_token"]


def register(client, email="person@example.com", password="long-test-password"):
    return client.post(
        "/account/register",
        data={
            "csrf_token": csrf_token(client),
            "email": email,
            "password": password,
            "password_confirmation": password,
        },
    )


def login(client, email="person@example.com", password="long-test-password"):
    return client.post(
        "/account/login",
        data={
            "csrf_token": csrf_token(client),
            "email": email,
            "password": password,
        },
    )


def logout(client):
    return client.post(
        "/account/logout", data={"csrf_token": csrf_token(client)}
    )


def test_register_claims_anonymous_workspace_and_login_restores_it(app):
    client = app.test_client()
    dataset = upload_dataset(client)

    response = register(client)
    assert response.status_code == 302
    assert client.get(f"/api/datasets/{dataset['id']}").status_code == 200

    account = client.get("/account")
    assert b"person@example.com" in account.data
    assert b"1 / 1" in account.data

    assert logout(client).status_code == 302
    assert client.get(f"/api/datasets/{dataset['id']}").status_code == 404

    assert login(client).status_code == 302
    assert client.get(f"/api/datasets/{dataset['id']}").status_code == 200


def test_invalid_csrf_and_password_are_rejected(client):
    response = client.post(
        "/account/register",
        data={
            "csrf_token": "invalid",
            "email": "person@example.com",
            "password": "long-test-password",
            "password_confirmation": "long-test-password",
        },
    )
    assert response.status_code == 302

    response = client.post(
        "/account/register",
        data={
            "csrf_token": csrf_token(client),
            "email": "person@example.com",
            "password": "short",
            "password_confirmation": "short",
        },
    )
    assert response.status_code == 302
    assert b"Password must contain 10 to 128 characters" in client.get("/account").data


def test_manually_assigned_pro_plan_unlocks_capacity_and_export(app):
    client = app.test_client()
    assert register(client).status_code == 302
    database = app.extensions["mongo_db"]
    database.users.update_one(
        {"email": "person@example.com"}, {"$set": {"plan": "pro"}}
    )

    home = client.get("/app")
    assert b"maximum 100 MB and 100 rows" in home.data
    assert b'data-max-charts="12"' in home.data

    dataset = upload_dataset(client)
    payload = {
        "title": "Pro dashboard",
        "dataset_id": dataset["id"],
        "charts": [
            {
                "title": "Sales",
                "type": "bar",
                "x": "Region",
                "y": "Sales",
                "aggregation": "sum",
            }
        ],
    }
    dashboard = client.post("/api/dashboards", json=payload).get_json()["dashboard"]
    exported = client.get(f"/api/dashboards/{dashboard['id']}/export")

    assert exported.status_code == 200
    assert exported.mimetype == "application/json"
    assert b"Pro dashboard" in exported.data


def test_pricing_page_marks_checkout_as_unavailable(client):
    response = client.get("/pricing")
    assert response.status_code == 200
    assert b"Checkout coming soon" not in response.data
    assert b"Create a free account" in response.data


class FakeGoogleClient:
    def __init__(self, userinfo=None):
        self.userinfo = userinfo or {}
        self.redirect_uri = ""

    def authorize_redirect(self, redirect_uri):
        self.redirect_uri = redirect_uri
        return redirect("https://accounts.google.test/authorize")

    def authorize_access_token(self):
        return {"userinfo": self.userinfo}


def configure_google(app):
    app.config.update(
        GOOGLE_CLIENT_ID="google-client-id",
        GOOGLE_CLIENT_SECRET="google-client-secret",
        GOOGLE_REDIRECT_URI=(
            "https://dataviz-dash.onrender.com/account/google/callback"
        ),
    )


def test_google_login_uses_configured_callback(app, monkeypatch):
    configure_google(app)
    google = FakeGoogleClient()
    monkeypatch.setattr(auth_module.oauth, "create_client", lambda _name: google)
    client = app.test_client()

    response = client.get("/account/google")

    assert response.status_code == 302
    assert response.location == "https://accounts.google.test/authorize"
    assert google.redirect_uri == (
        "https://dataviz-dash.onrender.com/account/google/callback"
    )


def test_google_callback_creates_account_and_claims_workspace(app, monkeypatch):
    configure_google(app)
    google = FakeGoogleClient(
        {
            "sub": "google-user-123",
            "email": "google@example.com",
            "email_verified": True,
        }
    )
    monkeypatch.setattr(auth_module.oauth, "create_client", lambda _name: google)
    client = app.test_client()
    dataset = upload_dataset(client)

    response = client.get("/account/google/callback")

    assert response.status_code == 302
    assert response.location == "/app"
    user = app.extensions["mongo_db"].users.find_one(
        {"email": "google@example.com"}
    )
    assert user["google_subject"] == "google-user-123"
    assert client.get(f"/api/datasets/{dataset['id']}").status_code == 200
    assert b"google@example.com" in client.get("/account").data


def test_google_callback_links_existing_verified_email(app, monkeypatch):
    client = app.test_client()
    assert register(client, "linked@example.com").status_code == 302
    assert logout(client).status_code == 302
    configure_google(app)
    google = FakeGoogleClient(
        {
            "sub": "google-linked-456",
            "email": "linked@example.com",
            "email_verified": True,
        }
    )
    monkeypatch.setattr(auth_module.oauth, "create_client", lambda _name: google)

    response = client.get("/account/google/callback")

    assert response.status_code == 302
    database = app.extensions["mongo_db"]
    assert database.users.count_documents({"email": "linked@example.com"}) == 1
    assert database.users.find_one(
        {"email": "linked@example.com"}
    )["google_subject"] == "google-linked-456"


def test_google_callback_rejects_unverified_email(app, monkeypatch):
    configure_google(app)
    google = FakeGoogleClient(
        {
            "sub": "google-user-unverified",
            "email": "unverified@example.com",
            "email_verified": False,
        }
    )
    monkeypatch.setattr(auth_module.oauth, "create_client", lambda _name: google)
    client = app.test_client()

    response = client.get("/account/google/callback", follow_redirects=True)

    assert response.status_code == 200
    assert b"Google did not return a verified email address" in response.data
    assert app.extensions["mongo_db"].users.count_documents({}) == 0
