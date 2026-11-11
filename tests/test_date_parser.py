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
