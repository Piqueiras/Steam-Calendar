import re
import datetime
from typing import Optional, Dict, Any

MONTH_MAP = {
    # Español
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "set": 9, "setiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
    # Inglés
    "jan": 1, "january": 1,
    "apr": 4, "april": 4,
    "aug": 8, "august": 8,
    "dec": 12, "december": 12
}

MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def parse_steam_date(
    raw_date: Any,
    timestamp: Optional[int] = None,
    display_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Normaliza una fecha de Steam a formato de calendario utilizando los metadatos oficiales de Valve:
    - display_type: 'date_full', 'date_month', 'date_quarter', 'date_year', 'text_comingsoon', 'text_tba'
    - timestamp: UNIX timestamp devuelto por Steam (steam_release_date)
    - raw_date: Cadena de texto o custom_release_date_message
    """
    # 1. Si Valve indica explícitamente el tipo de fecha en la API:
    if display_type:
        dt = None
        if timestamp and isinstance(timestamp, (int, float)) and timestamp > 100000000:
            try:
                dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
            except (ValueError, OSError):
                dt = None

        if display_type == "date_full" and dt:
            iso_date = dt.strftime("%Y-%m-%d")
            return {
                "raw_date_str": str(raw_date) if raw_date else iso_date,
                "calendar_date": iso_date,
                "precision": "EXACT_DAY",
                "display_badge": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1][:3]} {dt.year}"
            }

        elif display_type == "date_month":
            month_name = MONTH_NAMES_ES[dt.month - 1] if dt else (raw_date or "Mes")
            year_str = str(dt.year) if dt else ""
            return {
                "raw_date_str": str(raw_date) if raw_date else f"{month_name} {year_str}",
                "calendar_date": None,
                "precision": "MONTH",
                "display_badge": f"{month_name} {year_str}".strip()
            }

        elif display_type == "date_quarter":
            q_num = ((dt.month - 1) // 3) + 1 if dt else 1
            year_str = str(dt.year) if dt else ""
            return {
                "raw_date_str": str(raw_date) if raw_date else f"Q{q_num} {year_str}",
                "calendar_date": None,
                "precision": "QUARTER",
                "display_badge": f"Q{q_num} {year_str}".strip()
            }

        elif display_type == "date_year":
            year_str = str(dt.year) if dt else str(raw_date or "Año")
            return {
                "raw_date_str": str(raw_date) if raw_date else f"Año {year_str}",
                "calendar_date": None,
                "precision": "YEAR",
                "display_badge": f"Año {year_str}".strip()
            }

        elif display_type in ["text_comingsoon", "text_tba"]:
            return {
                "raw_date_str": str(raw_date or "Próximamente"),
                "calendar_date": None,
                "precision": "TBA",
                "display_badge": str(raw_date or "Por confirmar")
            }

    # 2. Si viene con un timestamp UNIX válido sin display_type
    if timestamp and isinstance(timestamp, (int, float)) and timestamp > 100000000:
        try:
            dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
            iso_date = dt.strftime("%Y-%m-%d")
            return {
                "raw_date_str": str(raw_date) if raw_date else iso_date,
                "calendar_date": iso_date,
                "precision": "EXACT_DAY",
                "display_badge": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1][:3]} {dt.year}"
            }
        except (ValueError, OSError):
            pass

    # 3. Parseo textual de cadenas si no hay timestamp
    if not raw_date or not isinstance(raw_date, str):
        return {
            "raw_date_str": "Coming Soon",
            "calendar_date": None,
            "precision": "TBA",
            "display_badge": "Por confirmar"
        }

    raw = raw_date.strip()
    raw_lower = raw.lower()

    if any(k in raw_lower for k in ["coming soon", "próximamente", "proximamente", "tba", "tbd", "to be announced", "por confirmar", "por confirmarse"]):
        return {
            "raw_date_str": raw,
            "calendar_date": None,
            "precision": "TBA",
            "display_badge": "Por confirmar"
        }

    # Comprobar Trimestres (Q1, Q2, Q3, Q4)
    quarter_match = re.search(r"\b[q|t]([1-4])\s*(\d{4})\b", raw_lower)
    if quarter_match:
        q_num = quarter_match.group(1)
        year = quarter_match.group(2)
        return {
            "raw_date_str": raw,
            "calendar_date": None,
            "precision": "QUARTER",
            "display_badge": f"Q{q_num} {year}"
        }

    # Día primero: 24 Oct 2026
    match_day_first = re.search(r"(\d{1,2})\s*(?:de|\.|\/|-|,)?\s*([a-zA-ZáéíóúÁÉÍÓÚ]{3,12})\s*(?:de|\.|\/|-|,)?\s*(\d{4})", raw)
    if match_day_first:
        day_str = match_day_first.group(1)
        month_word = match_day_first.group(2).lower().rstrip(".")
        year_str = match_day_first.group(3)
        month_num = MONTH_MAP.get(month_word[:3]) or MONTH_MAP.get(month_word)
        if month_num:
            try:
                dt = datetime.date(int(year_str), month_num, int(day_str))
                return {
                    "raw_date_str": raw,
                    "calendar_date": dt.isoformat(),
                    "precision": "EXACT_DAY",
                    "display_badge": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1][:3]} {dt.year}"
                }
            except ValueError:
                pass

    # Mes primero: Oct 24, 2026
    match_month_first = re.search(r"([a-zA-Z]{3,12})\s*(\d{1,2})\s*(?:st|nd|rd|th)?,?\s*(\d{4})", raw)
    if match_month_first:
        month_word = match_month_first.group(1).lower().rstrip(".")
        day_str = match_month_first.group(2)
        year_str = match_month_first.group(3)
        month_num = MONTH_MAP.get(month_word[:3]) or MONTH_MAP.get(month_word)
        if month_num:
            try:
                dt = datetime.date(int(year_str), month_num, int(day_str))
                return {
                    "raw_date_str": raw,
                    "calendar_date": dt.isoformat(),
                    "precision": "EXACT_DAY",
                    "display_badge": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1][:3]} {dt.year}"
                }
            except ValueError:
                pass

    # Mes y Año sin día exacto: Noviembre 2026
    match_month_year = re.search(r"\b([a-zA-ZáéíóúÁÉÍÓÚ]{3,12})\s*(?:de)?\s*(\d{4})\b", raw)
    if match_month_year:
        month_word = match_month_year.group(1).lower().rstrip(".")
        year_str = match_month_year.group(2)
        month_num = MONTH_MAP.get(month_word[:3]) or MONTH_MAP.get(month_word)
        if month_num:
            return {
                "raw_date_str": raw,
                "calendar_date": None,
                "precision": "MONTH",
                "display_badge": f"{month_word.capitalize()} {year_str}"
            }

    # Año únicamente: 2026
    match_year_only = re.search(r"\b(202[4-9]|203[0-5])\b", raw)
    if match_year_only:
        year_str = match_year_only.group(1)
        return {
            "raw_date_str": raw,
            "calendar_date": None,
            "precision": "YEAR",
            "display_badge": f"Año {year_str}"
        }

    return {
        "raw_date_str": raw,
        "calendar_date": None,
        "precision": "TBA",
        "display_badge": raw if len(raw) <= 15 else "Por confirmar"
    }
