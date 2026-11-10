import pytest

from app import create_app

VALID_FORM = {
    "vcc": "12",
    "r1": "47000",
    "r2": "10000",
    "rc": "2200",
    "re": "1000",
    "beta": "150",
    "vbe": "0.7",
}


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_form_page_lists_all_fields(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for name in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
        assert f'name="{name}"' in body


def test_valid_submission_shows_operating_point(client):
    response = client.post("/calculate", data=VALID_FORM)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "7.7554" in body
    assert "Active" in body


def test_invalid_submission_returns_400_and_keeps_values(client):
    response = client.post("/calculate", data=dict(VALID_FORM, r1="0"))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "มากกว่า 0" in body
    assert 'value="0"' in body


def test_missing_field_returns_400(client):
    data = {key: value for key, value in VALID_FORM.items() if key != "vcc"}
    response = client.post("/calculate", data=data)
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "กรุณากรอก VCC" in body


def test_non_numeric_value_returns_400(client):
    response = client.post("/calculate", data=dict(VALID_FORM, r1="47,000"))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "ต้องเป็นตัวเลข" in body
