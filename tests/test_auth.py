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

    home = client.get("/")
    assert b"maximum 50 MB and 100 rows" in home.data
    assert b'data-max-charts="8"' in home.data

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
