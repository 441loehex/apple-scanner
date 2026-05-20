"""End-to-end web flow tests using FastAPI TestClient."""

from __future__ import annotations


def test_login_page_loads(test_client):
    resp = test_client.get("/login")
    assert resp.status_code == 200
    assert "Freshora" in resp.text


def test_login_correct_credentials(test_client):
    resp = test_client.post(
        "/login",
        data={"username": "freshora", "password": "test-password-123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_wrong_password(test_client):
    resp = test_client.post(
        "/login",
        data={"username": "freshora", "password": "wrong-password"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Nieprawidłowy" in resp.text


def test_root_without_auth_redirects(test_client):
    resp = test_client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers["location"]


def test_root_with_auth(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert "Freshora" in resp.text


def test_create_batch_and_redirect(auth_client):
    resp = auth_client.post(
        "/batches",
        data={
            "seller_name": "Jan Testowy",
            "variety": "Jonagold",
            "number_of_crates": "2",
            "total_weight_kg": "600",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/batches/" in resp.headers["location"]


def test_batch_detail_visible(auth_client):
    # Create a batch first
    resp = auth_client.post(
        "/batches",
        data={
            "seller_name": "Test Seller Detail",
            "variety": "Gala",
            "number_of_crates": "1",
            "total_weight_kg": "300",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Test Seller Detail" in resp.text


def test_api_varieties_returns_list(auth_client):
    resp = auth_client.get("/api/varieties")
    assert resp.status_code == 200
    data = resp.json()
    assert "varieties" in data
    assert isinstance(data["varieties"], list)
    assert len(data["varieties"]) > 0


def test_api_varieties_contains_preseeded(auth_client):
    resp = auth_client.get("/api/varieties")
    data = resp.json()
    varieties = data["varieties"]
    assert "Jonagold" in varieties or "Gala" in varieties


def test_logout_clears_session(auth_client):
    resp = auth_client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    # After logout, accessing / should redirect to login
    resp2 = auth_client.get("/", follow_redirects=False)
    assert resp2.status_code == 302
    assert "login" in resp2.headers["location"]
