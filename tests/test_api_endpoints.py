import json
from app.main import app
from app.db import init_db

def test_routes():
    init_db()
    client = app.test_client()

    # 1. Página principal
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b"Personal Calendar" in res_home.data

    # 2. API Calendar
    res_cal = client.get("/api/calendar")
    assert res_cal.status_code == 200
    data = json.loads(res_cal.data)
    assert "timeline_days" in data
    assert "fuzzy_tray" in data

    # 3. API Export ICS
    res_ics = client.get("/api/calendar/export.ics")
    assert res_ics.status_code == 200
    assert b"BEGIN:VCALENDAR" in res_ics.data

    # 4. API User Status
    res_status = client.get("/api/user/status")
    assert res_status.status_code == 200
    status_data = json.loads(res_status.data)
    assert "is_authenticated" in status_data
    assert "has_api_key" in status_data

    # 5. API Settings Save Key (Prueba con clave inválida)
    res_bad_key = client.post("/api/settings/api-key", json={"api_key": "123"})
    assert res_bad_key.status_code == 400

    # 6. API Settings Save Key (Prueba con clave válida de 32 caracteres)
    test_key = "12345678901234567890123456789012"
    res_good_key = client.post("/api/settings/api-key", json={"api_key": test_key})
    assert res_good_key.status_code == 200
    res_status2 = client.get("/api/user/status")
    assert json.loads(res_status2.data)["has_api_key"] is True
