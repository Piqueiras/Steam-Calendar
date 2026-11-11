import datetime
import json
from typing import List, Dict, Any, Optional
from icalendar import Calendar, Event, vText, vDate
from app.db import (
    get_cached_games,
    save_games_batch,
    get_user_wishlist_appids,
    get_user_library_games
)
from app.steam_client import SteamClient

DAY_NAMES_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def format_day_header(dt: datetime.date, today: datetime.date) -> str:
    """Devuelve un encabezado legible como 'Hoy', 'Mañana' o 'Viernes, 14 de Noviembre'."""
    delta = (dt - today).days
    if delta == 0:
        return "Hoy"
    elif delta == 1:
        return "Mañana"
    elif delta == -1:
        return "Ayer"
    
    day_name = DAY_NAMES_ES[dt.weekday()]
    month_name = MONTH_NAMES_ES[dt.month - 1]
    return f"{day_name}, {dt.day} de {month_name}"

class CalendarService:
    def __init__(self, api_key: Optional[str] = None):
        self.steam_client = SteamClient(api_key=api_key)

    def sync_upcoming_games(self) -> List[Dict[str, Any]]:
        """Sincroniza y guarda los lanzamientos populares de Steam en SQLite."""
        games = self.steam_client.fetch_popular_upcoming(count=100)
        if games:
            save_games_batch(games)
        return games

    def get_personal_calendar(self, steam_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Organiza los lanzamientos en la estructura del Steam Personal Calendar:
        - timeline_days: Lista de días con sus respectivos juegos (Rolling Day-by-Day).
        - fuzzy_tray: Juegos con fechas no cerradas (Mes, Trimestre, TBA).
        - user_stats: Resumen de deseados y biblioteca.
        """
        cached_games = get_cached_games()
        if not cached_games:
            cached_games = self.sync_upcoming_games()

        wishlist_ids = set()
        library_games = []
        if steam_id:
            wishlist_ids = set(get_user_wishlist_appids(steam_id))
            library_games = get_user_library_games(steam_id)

        # Identificar nombres de juegos en biblioteca para detectar DLCs
        owned_names = [g["name"].lower() for g in library_games]

        today = datetime.date.today()
        
        # Estructuras para agrupar
        days_map: Dict[str, List[Dict[str, Any]]] = {}
        fuzzy_list: List[Dict[str, Any]] = []

        for g in cached_games:
            game_item = dict(g)
            appid = game_item["appid"]
            name_lower = game_item["name"].lower()

            # Añadir marcas de personalización
            is_wishlisted = appid in wishlist_ids
            is_dlc_owned = any(owned in name_lower and owned != name_lower for owned in owned_names)

            game_item["is_wishlisted"] = is_wishlisted
            game_item["is_owned_base_game"] = is_dlc_owned
            game_item["steam_store_url"] = f"https://store.steampowered.com/app/{appid}/"

            cal_date_str = game_item.get("calendar_date")
            precision = game_item.get("precision", "TBA")

            if precision == "EXACT_DAY" and cal_date_str:
                if cal_date_str not in days_map:
                    days_map[cal_date_str] = []
                days_map[cal_date_str].append(game_item)
            else:
                fuzzy_list.append(game_item)

        # Ordenar días cronológicamente
        sorted_dates = sorted(days_map.keys())
        timeline_days = []
        for d_str in sorted_dates:
            dt = datetime.date.fromisoformat(d_str)
            timeline_days.append({
                "date_iso": d_str,
                "header_label": format_day_header(dt, today),
                "weekday_name": DAY_NAMES_ES[dt.weekday()],
                "formatted_date": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1]} {dt.year}",
                "is_today": dt == today,
                "is_past": dt < today,
                "games": sorted(days_map[d_str], key=lambda x: (not x["is_wishlisted"], x["name"]))
            })

        # Ordenar fechas difusas (Meses y Trimestres primero, TBA al final)
        fuzzy_priority = {"MONTH": 1, "QUARTER": 2, "YEAR": 3, "TBA": 4}
        sorted_fuzzy = sorted(fuzzy_list, key=lambda x: (
            fuzzy_priority.get(x.get("precision"), 5),
            not x["is_wishlisted"],
            x.get("display_badge", "")
        ))

        return {
            "today_iso": today.isoformat(),
            "timeline_days": timeline_days,
            "fuzzy_tray": sorted_fuzzy,
            "stats": {
                "total_exact_days": len(timeline_days),
                "total_exact_games": sum(len(d["games"]) for d in timeline_days),
                "total_fuzzy_games": len(sorted_fuzzy),
                "wishlist_count": len(wishlist_ids),
                "library_count": len(library_games)
            }
        }

    def export_ical_feed(self, steam_id: Optional[str] = None, wishlist_only: bool = False) -> str:
        """Genera un feed iCalendar (.ics) estándar RFC 5545 para suscripción externa."""
        cal_data = self.get_personal_calendar(steam_id=steam_id)
        
        cal = Calendar()
        cal.add("prodid", "-//Steam Personal Calendar//ES")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", "Lanzamientos de Steam")
        cal.add("x-wr-caldesc", "Calendario de próximos lanzamientos de juegos en Steam")

        for day in cal_data["timeline_days"]:
            dt = datetime.date.fromisoformat(day["date_iso"])
            for g in day["games"]:
                if wishlist_only and not g.get("is_wishlisted"):
                    continue

                event = Event()
                prefix = "⭐ " if g.get("is_wishlisted") else ""
                event.add("summary", f"{prefix}{g['name']}")
                event.add("dtstart", vDate(dt))
                event.add("dtend", vDate(dt + datetime.timedelta(days=1)))
                
                desc_lines = [
                    f"Juego: {g['name']}",
                    f"Fecha de lanzamiento: {day['formatted_date']}",
                    f"Precio estimado: {g.get('price_str') or 'Por confirmar'}",
                    f"Enlace de Steam: {g['steam_store_url']}"
                ]
                if g.get("is_wishlisted"):
                    desc_lines.append("Estado: ¡En tu lista de deseados de Steam!")
                if g.get("is_owned_base_game"):
                    desc_lines.append("Nota: ¡Posees el juego base en tu biblioteca!")

                event.add("description", "\n".join(desc_lines))
                event.add("url", g["steam_store_url"])
                event.add("uid", f"steam-game-{g['appid']}@steamcalendar.local")
                cal.add_component(event)

        return cal.to_ical().decode("utf-8")
