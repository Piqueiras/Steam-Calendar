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

    res_ics_lib = client.get("/api/calendar/export.ics?library_only=1")
    assert res_ics_lib.status_code == 200
    assert b"BEGIN:VCALENDAR" in res_ics_lib.data

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
    # Se debe actualizar en memoria/sesión sin reescribir el archivo .env en disco
    from app.config import ENV_PATH
    env_before = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else None

    test_key = "12345678901234567890123456789012"
    res_good_key = client.post("/api/settings/api-key", json={"api_key": test_key})
    assert res_good_key.status_code == 200
    res_status2 = client.get("/api/user/status")
    assert json.loads(res_status2.data)["has_api_key"] is True

    if ENV_PATH.exists() and env_before is not None:
        assert ENV_PATH.read_text(encoding="utf-8") == env_before

    # 7. API Set Manual SteamID
    res_set_id = client.post("/api/user/set-steamid", json={"steam_id_or_url": "76561198012345678"})
    assert res_set_id.status_code == 200
    assert json.loads(res_set_id.data)["steam_id"] == "76561198012345678"

    # 8. API Set Empty SteamID
    res_set_empty = client.post("/api/user/set-steamid", json={"steam_id_or_url": ""})
    assert res_set_empty.status_code == 400

    # 9. API Search (prueba con término vacío)
    res_search_empty = client.get("/api/search?q=")
    assert res_search_empty.status_code == 200
    assert json.loads(res_search_empty.data)["results"] == []

    # 10. API Inspect Game (sin parámetro -> 400)
    res_inspect_empty = client.get("/api/game/inspect")
    assert res_inspect_empty.status_code == 400

    # 11. API Inspect Game (con URL de Steam no válida)
    res_inspect_bad = client.get("/api/game/inspect?target=not_an_app")
    assert res_inspect_bad.status_code == 200
    assert "error" in json.loads(res_inspect_bad.data)
