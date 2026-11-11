import datetime
import json
from typing import List, Dict, Any, Optional
from icalendar import Calendar, Event, vDate
from app.db import (
    get_cached_games,
    save_games_batch,
    get_user_wishlist_appids,
    get_user_library_games,
    clear_sample_data,
    clear_all_games
)
from app.steam_client import SteamClient

DAY_NAMES_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def format_day_header(dt: datetime.date, today: datetime.date) -> str:
    """Devuelve un encabezado amigable como 'Hoy', 'Mañana' o 'Viernes, 14 de Noviembre'."""
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

    def sync_upcoming_games(self, clear_first: bool = False, max_items: int = 2500) -> List[Dict[str, Any]]:
        """Sincroniza y guarda los lanzamientos reales de Steam en SQLite."""
        if clear_first:
            clear_all_games()
        else:
            clear_sample_data()

        games = self.steam_client.fetch_popular_upcoming(max_items=max_items)
        if games:
            save_games_batch(games)
        return games

    def get_personal_calendar(self, steam_id: Optional[str] = None, include_past: bool = False) -> Dict[str, Any]:
        """
        Organiza los lanzamientos en la estructura del Steam Personal Calendar:
        - timeline_days: Lista de días con sus respectivos juegos (Rolling Day-by-Day).
        - fuzzy_tray: Juegos con fechas no cerradas (Mes, Trimestre, TBA).
        - stats: Resumen de totales.
        - include_past: Si es True, incluye las 2 semanas anteriores; si es False, solo desde hoy.
        """
        # Eliminar cualquier rastro antiguo de datos de muestra
        clear_sample_data()

        cached_games = get_cached_games()
        # Si no hay juegos reales en caché, sincronizar desde Steam
        if not cached_games:
            cached_games = self.sync_upcoming_games()

        wishlist_ids = set()
        user_owned_appids = set()
        library_games = []
        if steam_id:
            wishlist_ids = set(get_user_wishlist_appids(steam_id))
            library_games = get_user_library_games(steam_id)
            user_owned_appids = set(g["appid"] for g in library_games)

            # Sincronizar detalles tanto para deseados como para juegos comprados en la biblioteca
            user_target_appids = list(wishlist_ids.union(user_owned_appids))
            if user_target_appids:
                cached_appids_set = set(g["appid"] for g in cached_games)
                missing_appids = [aid for aid in user_target_appids if aid not in cached_appids_set]
                stale_appids = [
                    g["appid"] for g in cached_games 
                    if g["appid"] in user_target_appids and (
                        g.get("tags") in [["Juego en Seguimiento"], ["Próximo Estreno"], []]
                    )
                ][:50]
                to_fetch = list(set(missing_appids[:100] + stale_appids))
                if to_fetch:
                    synced_games = self.steam_client.fetch_wishlist_games_details(to_fetch)
                    if synced_games:
                        save_games_batch(synced_games)
                        cached_games = get_cached_games()

        today = datetime.date.today()
        days_map: Dict[str, List[Dict[str, Any]]] = {}
        fuzzy_list: List[Dict[str, Any]] = []

        for g in cached_games:
            game_item = dict(g)
            appid = game_item["appid"]

            # Comprobación de DLC oficial de Steam:
            # Solo es DLC de tu biblioteca si tiene un parent_appid y ese parent_appid está en tu biblioteca
            parent_appid = game_item.get("parent_appid")
            item_type = game_item.get("item_type", "GAME")
            is_dlc = item_type == "DLC" or bool(parent_appid)
            is_dlc_owned = bool(parent_appid and parent_appid in user_owned_appids)

            is_wishlisted = appid in wishlist_ids
            is_owned = appid in user_owned_appids

            # Normalización y detección de la categoría del lanzamiento
            rel_cat = game_item.get("release_category")
            is_ea = bool(game_item.get("is_early_access"))
            if is_dlc:
                rel_cat = "DLC"
            elif not rel_cat or rel_cat not in ["RELEASE_1_0", "FIRST_RELEASE", "DLC"]:
                tags_str = str(game_item.get("tags", [])).lower()
                name_str = str(game_item.get("name", "")).lower()
                is_ea = is_ea or "early access" in tags_str or "acceso anticipado" in tags_str
                if "1.0" in name_str or "lanzamiento 1.0" in tags_str or "full release" in name_str:
                    rel_cat = "RELEASE_1_0"
                else:
                    rel_cat = "FIRST_RELEASE"

            game_item["is_wishlisted"] = is_wishlisted
            game_item["is_owned"] = is_owned
            game_item["is_dlc"] = is_dlc
            game_item["is_owned_base_game"] = is_dlc_owned
            game_item["release_category"] = rel_cat
            game_item["is_early_access"] = is_ea
            game_item["review_score_label"] = game_item.get("review_score_label")
            game_item["review_percent"] = game_item.get("review_percent")
            game_item["review_count"] = game_item.get("review_count")
            game_item["steam_store_url"] = f"https://store.steampowered.com/app/{appid}/"

            cal_date_str = game_item.get("calendar_date")
            precision = game_item.get("precision", "TBA")

            if precision == "EXACT_DAY" and cal_date_str:
                try:
                    dt_val = datetime.date.fromisoformat(cal_date_str)
                    # Si no queremos pasados y el juego es anterior a hoy, omitirlo
                    if not include_past and dt_val < today:
                        continue

                    # Ventana válida: si include_past es True, permite lanzamientos desde hace 14 días
                    min_date = (today - datetime.timedelta(days=14)) if include_past else today
                    if dt_val >= min_date:
                        if cal_date_str not in days_map:
                            days_map[cal_date_str] = []
                        days_map[cal_date_str].append(game_item)
                    # Juegos lanzados hace más de 14 días se descartan (no saturan la bandeja)
                except ValueError:
                    fuzzy_list.append(game_item)
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
                "games": sorted(days_map[d_str], key=lambda x: (not (x["is_wishlisted"] or x.get("is_owned")), x["name"]))
            })

        # Ordenar fechas difusas
        fuzzy_priority = {"MONTH": 1, "QUARTER": 2, "YEAR": 3, "TBA": 4}
        sorted_fuzzy = sorted(fuzzy_list, key=lambda x: (
            fuzzy_priority.get(x.get("precision"), 5),
            not (x["is_wishlisted"] or x.get("is_owned")),
            x.get("display_badge", "")
        ))

        all_games = [g for d in timeline_days for g in d["games"]] + sorted_fuzzy
        total_release_1_0 = sum(1 for g in all_games if g.get("release_category") == "RELEASE_1_0")
        total_first_release = sum(1 for g in all_games if g.get("release_category") == "FIRST_RELEASE")
        total_dlc = sum(1 for g in all_games if g.get("is_owned_base_game"))
        total_library_owned = sum(1 for g in all_games if g.get("is_owned"))

        return {
            "today_iso": today.isoformat(),
            "is_authenticated": bool(steam_id),
            "timeline_days": timeline_days,
            "fuzzy_tray": sorted_fuzzy,
            "stats": {
                "total_exact_days": len(timeline_days),
                "total_exact_games": sum(len(d["games"]) for d in timeline_days),
                "total_fuzzy_games": len(sorted_fuzzy),
                "wishlist_count": len(wishlist_ids),
                "library_count": len(library_games),
                "library_owned_count": total_library_owned,
                "dlc_count": total_dlc,
                "release_1_0_count": total_release_1_0,
                "first_release_count": total_first_release
            }
        }

    def export_ical_feed(self, steam_id: Optional[str] = None, wishlist_only: bool = False, library_only: bool = False, include_past: bool = False) -> str:
        """Genera un feed iCalendar (.ics) estándar RFC 5545 para suscripción externa."""
        cal_data = self.get_personal_calendar(steam_id=steam_id, include_past=include_past)
        
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
                if library_only and not g.get("is_owned"):
                    continue

                event = Event()
                prefix = ""
                if g.get("is_wishlisted"):
                    prefix = "⭐ "
                elif g.get("is_owned"):
                    prefix = "📚 "

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
                if g.get("is_owned"):
                    desc_lines.append("Estado: ¡Comprado en tu biblioteca de Steam!")
                if g.get("is_owned_base_game"):
                    desc_lines.append("Nota: ¡Posees el juego base en tu biblioteca!")

                event.add("description", "\n".join(desc_lines))
                event.add("url", g["steam_store_url"])
                event.add("uid", f"steam-game-{g['appid']}@steamcalendar.local")
                cal.add_component(event)

        return cal.to_ical().decode("utf-8")
