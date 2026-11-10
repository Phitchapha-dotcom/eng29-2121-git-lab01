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
    assert 'value="47,000"' in body


def test_empty_field_returns_400(client):
    response = client.post("/calculate", data=dict(VALID_FORM, r1=""))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "กรุณากรอก R1" in body


def test_result_page_shows_input_summary(client):
    response = client.post("/calculate", data=VALID_FORM)
    body = response.get_data(as_text=True)
    assert "ค่าที่กรอก" in body
    assert "47000" in body
    assert "150" in body


def test_large_beta_formats(client):
    response = client.post("/calculate", data=dict(VALID_FORM, beta="10000"))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "7.5072" in body


def test_saturation_page_labels_active_region_estimate(client):
    response = client.post(
        "/calculate",
        data=dict(VALID_FORM, rc="10000", re="100", beta="300"),
    )
    body = response.get_data(as_text=True)
    assert "ประมาณ" in body
    assert "0.2" in body


def test_result_page_shows_independent_comparison(client):
    response = client.post("/calculate", data=VALID_FORM)
    body = response.get_data(as_text=True)
    assert "Independent" in body
    assert "ผ่าน" in body
    assert "µA" in body


def test_saturation_warning_is_shown(client):
    response = client.post(
        "/calculate",
        data=dict(VALID_FORM, rc="10000", re="100", beta="300"),
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Saturation" in body
    assert "คำเตือน" in body
