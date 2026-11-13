from app.calendar_service import CalendarService
from app.db import init_db, save_game
from app.steam_client import _detect_release_category, _extract_reviews, _extract_tags

def test_detect_release_category():
    # 1. Juego DLC
    cat, is_ea = _detect_release_category({"name": "Expansion Pack"}, is_dlc=True)
    assert cat == "DLC"
    assert is_ea is False

    # 2. Juego con Tag 493 (Early Access oficial de Steam) que debuta por primera vez (como Blind Descent) -> FIRST_RELEASE, is_ea=True
    item_ea_first = {
        "name": "Blind Descent",
        "tags": [{"tagid": 493, "name": "Early Access"}],
        "release": {"is_coming_soon": True}
    }
    cat, is_ea = _detect_release_category(item_ea_first, is_dlc=False)
    assert cat == "FIRST_RELEASE"
    assert is_ea is True

    # 3. Juego con fecha oficial de graduación 1.0 de Valve (release_from_early_access_date, como 9 Kings o MycoRelic)
    item_ea_graduating = {
        "name": "9 Kings",
        "tags": [{"tagid": 493, "name": "Early Access"}],
        "release": {"release_from_early_access_date": 1794470400, "is_early_access": True}
    }
    cat, is_ea = _detect_release_category(item_ea_graduating, is_dlc=False)
    assert cat == "RELEASE_1_0"
    assert is_ea is True

    # 4. Juego con mención explícita de 1.0 en nombre o mensaje de fecha
    item_10 = {
        "name": "Roguelike Alpha 1.0 Launch",
        "release": {"custom_release_date_message": "1.0 Full Release"}
    }
    cat, is_ea = _detect_release_category(item_10, is_dlc=False)
    assert cat == "RELEASE_1_0"
    assert is_ea is True

    # 5. Primer lanzamiento estándar (sin rastro de Early Access)
    item_first = {
        "name": "Brand New Game",
        "tags": [{"tagid": 19, "name": "Action"}]
    }
    cat, is_ea = _detect_release_category(item_first, is_dlc=False)
    assert cat == "FIRST_RELEASE"
    assert is_ea is False

def test_extract_reviews():
    # 1. Reseñas desde summary_filtered
    item_with_reviews = {
        "reviews": {
            "summary_filtered": {
                "review_score_label": "Muy positivas",
                "percent_positive": 91,
                "review_count": 1450
            }
        }
    }
    label, pct, count = _extract_reviews(item_with_reviews)
    assert label == "Muy positivas"
    assert pct == 91
    assert count == 1450

    # 2. Reseñas con score numérico de Steam
    item_numeric_score = {
        "reviews": {
            "review_score": 8,
            "percent_positive": 88,
            "review_count": 520
        }
    }
    label, pct, count = _extract_reviews(item_numeric_score)
    assert label == "Muy positivas"
    assert pct == 88
    assert count == 520

    # 3. Sin reseñas (juego sin lanzar)
    item_no_reviews = {}
    label, pct, count = _extract_reviews(item_no_reviews)
    assert label is None
    assert pct is None
    assert count is None

def test_extract_store_tags():
    fake_tag_map = {
        1695: "Mundo abierto",
        1662: "Supervivencia",
        122: "Rol",
        19: "Acción",
        493: "Acceso anticipado"
    }

    # 1. Objeto con tagids de Steam Store (traduce y preserva orden de relevancia comunitaria)
    item_store = {
        "tags": [
            {"tagid": 1695, "weight": 1000},
            {"tagid": 1662, "weight": 800},
            {"tagid": 493, "weight": 500},
            {"tagid": 122, "weight": 400}
        ]
    }
    tags = _extract_tags(item_store, is_dlc=False, is_ea=True, tag_map=fake_tag_map)
    assert tags == ["Mundo abierto", "Supervivencia", "Rol"]

    # 2. Objeto con nombres directos en español
    item_named = {
        "tags": [
            {"name": "Estrategia"},
            {"name": "Roguelike"}
        ]
    }
    tags_named = _extract_tags(item_named, tag_map=fake_tag_map)
    assert tags_named == ["Estrategia", "Roguelike"]

    # 3. DLC con tags propios
    item_dlc = {
        "tags": [
            {"tagid": 19, "weight": 200}
        ]
    }
    tags_dlc = _extract_tags(item_dlc, is_dlc=True, tag_map=fake_tag_map)
    assert "Acción" in tags_dlc

def test_calendar_service_timeline():
    init_db()
    service = CalendarService()
    cal_data = service.get_personal_calendar()

    assert "timeline_days" in cal_data
    assert "fuzzy_tray" in cal_data
    assert "stats" in cal_data
    assert isinstance(cal_data["timeline_days"], list)
    assert isinstance(cal_data["fuzzy_tray"], list)

    # Debe contener juegos en días exactos y en la bandeja difusa
    assert len(cal_data["timeline_days"]) > 0
    assert len(cal_data["fuzzy_tray"]) > 0

    # Comprobar estructura de día
    first_day = cal_data["timeline_days"][0]
    assert "date_iso" in first_day
    assert "header_label" in first_day
    assert "games" in first_day
    assert len(first_day["games"]) > 0

def test_export_ical_feed():
    init_db()
    service = CalendarService()
    ics_feed = service.export_ical_feed()

    assert "BEGIN:VCALENDAR" in ics_feed
    assert "END:VCALENDAR" in ics_feed
    assert "BEGIN:VEVENT" in ics_feed
    assert "SUMMARY:" in ics_feed

def test_get_game_release_info():
    from app.steam_client import SteamClient
    client = SteamClient(api_key="12345678901234567890123456789012")

    # 1. Extracción de AppID desde URL válida
    res_url = client.get_game_release_info("https://store.steampowered.com/app/1866300/Dawn_Apart/")
    assert res_url.get("appid") == 1866300 or "error" in res_url

    # 2. Manejo de entrada no válida
    res_bad = client.get_game_release_info("not_a_valid_steam_url")
    assert "error" in res_bad

def test_early_access_graduation_vs_first_release_logic():
    from app.steam_client import _detect_release_category

    # Escenario A: Juego en Early Access que tiene fecha de graduación 1.0 oficial de Valve (como Dawn Apart, 9 Kings)
    item_graduating = {
        "name": "Dawn Apart",
        "release": {
            "steam_release_date": 1752508816,
            "release_from_early_access_date": 1795075200,
            "is_early_access": True
        }
    }
    cat, is_ea = _detect_release_category(item_graduating, is_dlc=False)
    assert cat == "RELEASE_1_0"
    assert is_ea is True

    # Escenario B: Juego que debuta en Early Access por primera vez (como Blind Descent)
    item_debut = {
        "name": "Blind Descent",
        "release": {
            "steam_release_date": 1796227200,
            "is_coming_soon": True,
            "is_early_access": True
        }
    }
    cat_debut, is_ea_debut = _detect_release_category(item_debut, is_dlc=False)
    assert cat_debut == "FIRST_RELEASE"
    assert is_ea_debut is True

    # Escenario C: Juego con anuncio explícito de salida en el texto
    item_text_10 = {
        "name": "Indie Game",
        "release": {
            "custom_release_date_message": "Salida del Acceso Anticipado: 15 de Noviembre",
            "is_early_access": True
        }
    }
    cat_text, is_ea_text = _detect_release_category(item_text_10, is_dlc=False)
    assert cat_text == "RELEASE_1_0"
    assert is_ea_text is True

def test_calendar_service_with_library_owned_games():
    from app.db import save_user_library, get_cached_games
    init_db()
    service = CalendarService()
    cal_init = service.get_personal_calendar(include_past=False)
    if not cal_init["timeline_days"]:
        return
    sample_game = cal_init["timeline_days"][0]["games"][0]
    sample_appid = sample_game["appid"]

    test_steam_id = "76561198000000001"
    save_user_library(test_steam_id, [{"appid": sample_appid, "name": sample_game["name"], "playtime_forever": 120}])

    cal_data = service.get_personal_calendar(steam_id=test_steam_id, include_past=False)

    all_returned_games = [g for d in cal_data["timeline_days"] for g in d["games"]] + cal_data["fuzzy_tray"]
    matched = [g for g in all_returned_games if g["appid"] == sample_appid]
    assert len(matched) > 0
    assert matched[0]["is_owned"] is True
    assert cal_data["stats"]["library_owned_count"] >= 1

    # Comprobar exportación iCal con filtro de biblioteca
    ical_owned = service.export_ical_feed(steam_id=test_steam_id, library_only=True)
    assert "BEGIN:VCALENDAR" in ical_owned
    assert "steam-game-" + str(sample_appid) in ical_owned

def test_fuzzy_tray_placement_for_years_and_quarters():
    """Verifica que juegos fechados para un Año o Trimestre se ubiquen en la bandeja lateral (fuzzy_tray) y no en la línea temporal."""
    service = CalendarService()
    cal = service.get_personal_calendar()

    timeline_dates = [d["date_iso"] for d in cal["timeline_days"]]
    # Ningún día de la línea temporal debe ser un placeholder del 1 de enero o 1 de diciembre de 2027
    assert "2027-01-01" not in timeline_dates
    assert "2027-12-01" not in timeline_dates

    # Verificar que los juegos con Año o Trimestre se ubiquen en fuzzy_tray
    fuzzy_games = cal["fuzzy_tray"]
    year_games = [g for g in fuzzy_games if g.get("precision") == "YEAR"]
    quarter_games = [g for g in fuzzy_games if g.get("precision") == "QUARTER"]

    assert len(year_games) > 0
    assert len(quarter_games) > 0
    for yg in year_games:
        assert yg["calendar_date"] is None
        assert "Año" in yg["display_badge"]
    for qg in quarter_games:
        assert qg["calendar_date"] is None
        assert "Q" in qg["display_badge"]

    # Verificar que periodos pasados no aparezcan en la bandeja de próximos lanzamientos
    past_quarter_badges = [g["display_badge"] for g in fuzzy_games if g.get("display_badge") in ["Q1 2026", "Q2 2026", "Q3 2026"]]
    assert len(past_quarter_badges) == 0, f"Ventanas pasadas encontradas en fuzzy tray: {past_quarter_badges}"

    # Verificar ordenación cronológica estricta:
    # Si existen títulos para Año 2026 y Q1 2027, Año 2026 debe figurar antes que Q1 2027
    idx_2026 = next((i for i, g in enumerate(fuzzy_games) if "2026" in str(g.get("display_badge"))), None)
    idx_q1_2027 = next((i for i, g in enumerate(fuzzy_games) if g.get("display_badge") == "Q1 2027"), None)
    idx_q4_2027 = next((i for i, g in enumerate(fuzzy_games) if g.get("display_badge") == "Q4 2027"), None)
    idx_year_2027 = next((i for i, g in enumerate(fuzzy_games) if g.get("display_badge") == "Año 2027"), None)

    if idx_2026 is not None and idx_q1_2027 is not None:
        assert idx_2026 < idx_q1_2027, "Los títulos de 2026 deben aparecer antes que los de 2027"
    if idx_q1_2027 is not None and idx_q4_2027 is not None:
        assert idx_q1_2027 < idx_q4_2027, "Q1 2027 debe aparecer antes que Q4 2027"
    if idx_q4_2027 is not None and idx_year_2027 is not None:
        assert idx_q4_2027 < idx_year_2027, "Q4 2027 debe aparecer antes que los títulos sin trimestre fijado (Año 2027)"

def test_sorting_by_followers_metric():
    """Verifica que dentro del mismo día se ordenen primero los títulos con más seguidores (los más esperados)."""
    from app.calendar_service import get_fuzzy_sort_key
    # 1. Simulación de juegos en un mismo día
    games_same_day = [
        {"appid": 1, "name": "Game Alpha (Low followers)", "follower_count": 250, "is_wishlisted": False, "is_owned": False},
        {"appid": 2, "name": "Game Beta (Huge Anticipation)", "follower_count": 150000, "is_wishlisted": False, "is_owned": False},
        {"appid": 3, "name": "Game Gamma (Medium followers)", "follower_count": 12000, "is_wishlisted": False, "is_owned": False},
        {"appid": 4, "name": "Game Personal (Wishlisted)", "follower_count": 50, "is_wishlisted": True, "is_owned": False},
    ]

    sorted_games = sorted(
        games_same_day,
        key=lambda x: (
            not (x["is_wishlisted"] or x.get("is_owned")),
            -(x.get("follower_count") or 0),
            x["name"]
        )
    )

    # El juego personal (wishlist) debe ir primero
    assert sorted_games[0]["name"] == "Game Personal (Wishlisted)"
    # Entre los no personales, el de 150k debe ir segundo, luego el de 12k, luego el de 250
    assert sorted_games[1]["name"] == "Game Beta (Huge Anticipation)"
    assert sorted_games[2]["name"] == "Game Gamma (Medium followers)"
    assert sorted_games[3]["name"] == "Game Alpha (Low followers)"

    # 2. En la bandeja difusa (fuzzy tray), dentro del mismo trimestre debe priorizar seguidores
    g_quarter_low = {"name": "Q1 Low", "precision": "QUARTER", "display_badge": "Q1 2027", "follower_count": 100, "is_wishlisted": False}
    g_quarter_high = {"name": "Q1 High", "precision": "QUARTER", "display_badge": "Q1 2027", "follower_count": 95000, "is_wishlisted": False}

    key_low = get_fuzzy_sort_key(g_quarter_low)
    key_high = get_fuzzy_sort_key(g_quarter_high)

    assert key_high < key_low, "El título con 95k seguidores debe ordenarse antes que el de 100 seguidores"

def test_extract_price():
    """Verifica la extracción precisa de precios, descuentos y gratuidad desde respuestas de Valve."""
    from app.steam_client import _extract_price

    # 1. Juego con descuento activo de Valve (best_purchase_option)
    item_discounted = {
        "best_purchase_option": {
            "final_price_in_cents": "1499",
            "original_price_in_cents": "2999",
            "formatted_final_price": "14,99€",
            "formatted_original_price": "29,99€",
            "discount_pct": 50
        }
    }
    price, is_free, disc, orig = _extract_price(item_discounted)
    assert price == "14,99€"
    assert is_free is False
    assert disc == 50
    assert orig == "29,99€"

    # 2. Juego a precio completo sin descuento
    item_full_price = {
        "best_purchase_option": {
            "final_price_in_cents": "5999",
            "formatted_final_price": "59,99€",
            "discount_pct": 0
        }
    }
    price, is_free, disc, orig = _extract_price(item_full_price)
    assert price == "59,99€"
    assert is_free is False
    assert disc == 0
    assert orig is None

    # 3. Juego Free to Play por tag 113
    item_ftp = {
        "best_purchase_option": None,
        "tagids": [113, 20]
    }
    price, is_free, disc, orig = _extract_price(item_ftp)
    assert price == "Gratis"
    assert is_free is True
    assert disc == 0

    # 4. Próximo estreno indie sin precio fijado (sin preventa)
    item_unpriced = {
        "best_purchase_option": None,
        "tagids": [19, 492]
    }
    price, is_free, disc, orig = _extract_price(item_unpriced)
    assert price == "Por confirmar"
    assert is_free is False
    assert disc == 0

def test_no_hardcoded_games_in_app():
    import os
    import re
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
    forbidden_terms = ["1866300", "2624080", "2784470", "1209970", "dawn apart", "mycorelic", "9 kings", "blind descent"]
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read().lower()
                    for term in forbidden_terms:
                        assert term not in content, f"Término hardcodeado '{term}' encontrado en {f}"

def test_adult_content_and_dlc_filtering():
    from app.calendar_service import has_adult_tags

    # 1. Juego +18 con 'desnudos', 'contenido sexual' o 'hentai' entre sus primeras etiquetas
    assert has_adult_tags(["Contenido sexual", "Hentai", "Desnudos"]) is True
    assert has_adult_tags(["Acción", "Aventura", "Desnudos"]) is True
    assert has_adult_tags(["Novelas visuales", "Sexual Content"]) is True

    # 2. Juego convencional como The Witcher 3 (con RPG, Mundo abierto, etc. entre sus principales)
    assert has_adult_tags(["Mundo abierto", "Rol", "Buena trama", "Ambientales", "Fantasía"]) is False
    assert has_adult_tags(["Estrategia", "Simulación", "Ciencia ficción"]) is False

    # 3. Propagación de flag is_nsfw en el calendario
    service = CalendarService()
    cal = service.get_personal_calendar(include_past=True)
    all_games = [g for d in cal["timeline_days"] for g in d["games"]] + cal["fuzzy_tray"]

    for g in all_games:
        assert "is_nsfw" in g
        assert isinstance(g["is_nsfw"], bool)

    # 4. Export iCal con filtros de DLC no poseído y NSFW
    ics_filtered = service.export_ical_feed(hide_unowned_dlc=True, hide_nsfw=True)
    assert "BEGIN:VCALENDAR" in ics_filtered
