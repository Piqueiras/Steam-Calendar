from app.date_parser import parse_steam_date

def test_exact_day_formats():
    # Inglés
    res1 = parse_steam_date("Oct 24, 2026")
    assert res1["precision"] == "EXACT_DAY"
    assert res1["calendar_date"] == "2026-10-24"

    res2 = parse_steam_date("28 Feb, 2027")
    assert res2["precision"] == "EXACT_DAY"
    assert res2["calendar_date"] == "2027-02-28"

    # Español
    res3 = parse_steam_date("15 de noviembre de 2026")
    assert res3["precision"] == "EXACT_DAY"
    assert res3["calendar_date"] == "2026-11-15"

    res4 = parse_steam_date("21 nov. 2026")
    assert res4["precision"] == "EXACT_DAY"
    assert res4["calendar_date"] == "2026-11-21"

def test_quarter_formats():
    res1 = parse_steam_date("Q1 2027")
    assert res1["precision"] == "QUARTER"
    assert res1["calendar_date"] is None
    assert "Q1 2027" in res1["display_badge"]

    res2 = parse_steam_date("Q4 2026")
    assert res2["precision"] == "QUARTER"
    assert res2["calendar_date"] is None

    # Formatos de trimestres en español
    res3 = parse_steam_date("4.º trimestre del 2027")
    assert res3["precision"] == "QUARTER"
    assert res3["calendar_date"] is None
    assert res3["display_badge"] == "Q4 2027"

    res4 = parse_steam_date("1.er trimestre de 2027")
    assert res4["precision"] == "QUARTER"
    assert res4["calendar_date"] is None
    assert res4["display_badge"] == "Q1 2027"

    res5 = parse_steam_date("cuarto trimestre del 2027")
    assert res5["precision"] == "QUARTER"
    assert res5["calendar_date"] is None
    assert res5["display_badge"] == "Q4 2027"

def test_year_formats_and_valve_placeholders():
    # Año sin día exacto no debe convertirse en 1 de enero
    res1 = parse_steam_date("2027")
    assert res1["precision"] == "YEAR"
    assert res1["calendar_date"] is None
    assert res1["display_badge"] == "Año 2027"

    # Con timestamp de Valve para 2027-01-01 (1798790400)
    res2 = parse_steam_date("2027", timestamp=1798790400)
    assert res2["precision"] == "YEAR"
    assert res2["calendar_date"] is None
    assert res2["display_badge"] == "Año 2027"

    # Con timestamp de Valve para 2027-12-01 (1827648000)
    res3 = parse_steam_date("4.º trimestre del 2027", timestamp=1827648000)
    assert res3["precision"] == "QUARTER"
    assert res3["calendar_date"] is None
    assert res3["display_badge"] == "Q4 2027"

    # Estilos numéricos de Valve (style 4 = Año, style 3 = Trimestre)
    res4 = parse_steam_date("", timestamp=1798790400, display_type=4)
    assert res4["precision"] == "YEAR"
    assert res4["calendar_date"] is None

    res5 = parse_steam_date("", timestamp=1827648000, display_type=3)
    assert res5["precision"] == "QUARTER"
    assert res5["calendar_date"] is None

def test_month_year_formats():
    res1 = parse_steam_date("Noviembre 2026")
    assert res1["precision"] == "MONTH"
    assert res1["calendar_date"] is None
    assert "Noviembre" in res1["display_badge"]

def test_tba_and_coming_soon():
    res1 = parse_steam_date("Coming Soon")
    assert res1["precision"] == "TBA"
    assert res1["calendar_date"] is None

    res2 = parse_steam_date("Próximamente")
    assert res2["precision"] == "TBA"
    assert res2["calendar_date"] is None

    res3 = parse_steam_date(None)
    assert res3["precision"] == "TBA"

def test_timestamp_parsing():
    # 1795000000 = aprox Noviembre 2026
    res = parse_steam_date("", timestamp=1795000000)
    assert res["precision"] == "EXACT_DAY"
    assert res["calendar_date"] is not None
