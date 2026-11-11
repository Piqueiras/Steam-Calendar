from app.calendar_service import CalendarService
from app.db import init_db

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
