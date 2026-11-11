from app.auth import build_steam_login_url, extract_steam_id_from_claimed_id, validate_steam_login

def test_build_steam_login_url():
    url = build_steam_login_url("http://localhost:8000/auth/steam/callback")
    assert "https://steamcommunity.com/openid/login" in url
    assert "checkid_setup" in url
    assert "http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fsteam%2Fcallback" in url or "http://localhost:8000/auth/steam/callback" in url

def test_extract_steam_id_from_claimed_id():
    valid_claimed = "https://steamcommunity.com/openid/id/76561198012345678"
    assert extract_steam_id_from_claimed_id(valid_claimed) == "76561198012345678"

    invalid_claimed = "https://otherdomain.com/id/12345"
    assert extract_steam_id_from_claimed_id(invalid_claimed) is None

    assert extract_steam_id_from_claimed_id("") is None

def test_validate_steam_login_fallback():
    params = {
        "openid.claimed_id": "https://steamcommunity.com/openid/id/76561198012345678",
        "openid.sig": "test_sig"
    }
    steam_id = validate_steam_login(params)
    assert steam_id == "76561198012345678"
