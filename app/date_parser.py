import re
import datetime
from typing import Optional, Dict, Any, Union

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
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

STYLE_INT_MAP = {
    1: "date_full",
    2: "date_month",
    3: "date_quarter",
    4: "date_year",
    5: "text_tba",
    "1": "date_full",
    "2": "date_month",
    "3": "date_quarter",
    "4": "date_year",
    "5": "text_tba"
}

def parse_steam_date(
    raw_date: Any,
    timestamp: Optional[int] = None,
    display_type: Optional[Union[str, int]] = None
) -> Dict[str, Any]:
    """
    Normaliza una fecha de Steam a formato de calendario utilizando los metadatos oficiales de Valve:
    - display_type: 'date_full', 'date_month', 'date_quarter', 'date_year', 'text_comingsoon', 'text_tba' (o estilos numéricos 1..5)
    - timestamp: UNIX timestamp devuelto por Steam (steam_release_date o release_from_early_access_date)
    - raw_date: Cadena de texto o custom_release_date_message
    """
    # 0. Normalizar display_type si viene como entero o string numérico (de release_from_early_access_style)
    if display_type in STYLE_INT_MAP:
        display_type = STYLE_INT_MAP[display_type]
    elif display_type is not None:
        display_type = str(display_type).lower()

    # Preparar timestamp datetime si está disponible
    dt = None
    if timestamp and isinstance(timestamp, (int, float)) and timestamp > 100000000:
        try:
            dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        except (ValueError, OSError):
            dt = None

    raw_str = str(raw_date).strip() if raw_date is not None else ""
    raw_lower = raw_str.lower()

    # 1. Si Valve indica explícitamente el tipo de fecha en la API:
    if display_type:
        if display_type == "date_full" and dt:
            iso_date = dt.strftime("%Y-%m-%d")
            return {
                "raw_date_str": raw_str or iso_date,
                "calendar_date": iso_date,
                "precision": "EXACT_DAY",
                "display_badge": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1][:3]} {dt.year}"
            }

        elif display_type == "date_month":
            month_name = MONTH_NAMES_ES[dt.month - 1] if dt else (raw_str or "Mes")
            year_str = str(dt.year) if dt else ""
            return {
                "raw_date_str": raw_str or f"{month_name} {year_str}".strip(),
                "calendar_date": None,
                "precision": "MONTH",
                "display_badge": f"{month_name} {year_str}".strip()
            }

        elif display_type == "date_quarter":
            q_num = ((dt.month - 1) // 3) + 1 if dt else 1
            year_str = str(dt.year) if dt else ""
            # Si el texto ya tiene información de Q/Trimestre, preservarlo
            badge = f"Q{q_num} {year_str}".strip() if year_str else f"Q{q_num}"
            return {
                "raw_date_str": raw_str or badge,
                "calendar_date": None,
                "precision": "QUARTER",
                "display_badge": badge
            }

        elif display_type == "date_year":
            year_str = str(dt.year) if dt else raw_str
            # Extraer año si hay dígitos
            m_y = re.search(r"\b(202[4-9]|203[0-9])\b", year_str)
            if m_y:
                year_str = m_y.group(1)
            badge = f"Año {year_str}".strip() if year_str else "Año"
            return {
                "raw_date_str": raw_str or badge,
                "calendar_date": None,
                "precision": "YEAR",
                "display_badge": badge
            }

        elif display_type in ["text_comingsoon", "text_tba"]:
            return {
                "raw_date_str": raw_str or "Próximamente",
                "calendar_date": None,
                "precision": "TBA",
                "display_badge": raw_str if (raw_str and len(raw_str) <= 25) else "Por confirmar"
            }

    # 2. Análisis semántico de raw_date para detectar ventanas difusas antes de confiar ciegamente en un timestamp
    if raw_str:
        # TBA
        if any(k in raw_lower for k in [
            "coming soon", "próximamente", "proximamente", "tba", "tbd",
            "to be announced", "por confirmar", "por confirmarse", "sin confirmar"
        ]):
            return {
                "raw_date_str": raw_str,
                "calendar_date": None,
                "precision": "TBA",
                "display_badge": "Por confirmar"
            }

        # Trimestres en español y variantes (ej: "4.º trimestre del 2027", "1er trimestre de 2027", "cuarto trimestre del 2027")
        m_q_es = re.search(r"\b([1-4])\.?(?:º|er|to|do|o)?\s*trimestre\s*(?:del?|de)?\s*(\d{4})\b", raw_lower)
        if m_q_es:
            q_num = m_q_es.group(1)
            year = m_q_es.group(2)
            return {
                "raw_date_str": raw_str,
                "calendar_date": None,
                "precision": "QUARTER",
                "display_badge": f"Q{q_num} {year}"
            }

        m_q_word = re.search(r"\b(primer|segundo|tercer|cuarto)\s+trimestre\s*(?:del?|de)?\s*(\d{4})\b", raw_lower)
        if m_q_word:
            w_map = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4}
            q_num = w_map[m_q_word.group(1)]
            year = m_q_word.group(2)
            return {
                "raw_date_str": raw_str,
                "calendar_date": None,
                "precision": "QUARTER",
                "display_badge": f"Q{q_num} {year}"
            }

        # Q1/T1 en inglés o abreviado: Q1 2027, T4 2027
        m_qt = re.search(r"\b[qt]([1-4])\s*(?:de|del)?\s*(\d{4})\b", raw_lower)
        if m_qt:
            q_num = m_qt.group(1)
            year = m_qt.group(2)
            return {
                "raw_date_str": raw_str,
                "calendar_date": None,
                "precision": "QUARTER",
                "display_badge": f"Q{q_num} {year}"
            }

        # Quarter en inglés: "4th quarter 2027"
        m_q_en = re.search(r"\b([1-4])\s*(?:st|nd|rd|th)?\s*quarter\s*(?:of)?\s*(\d{4})\b", raw_lower)
        if m_q_en:
            q_num = m_q_en.group(1)
            year = m_q_en.group(2)
            return {
                "raw_date_str": raw_str,
                "calendar_date": None,
                "precision": "QUARTER",
                "display_badge": f"Q{q_num} {year}"
            }

        # Día primero: 24 Oct 2026, 15 de noviembre de 2026
        match_day_first = re.search(r"(\d{1,2})\s*(?:de|\.|\/|-|,)?\s*([a-zA-ZáéíóúÁÉÍÓÚ]{3,12})\s*(?:de|\.|\/|-|,)?\s*(\d{4})", raw_str)
        if match_day_first:
            day_str = match_day_first.group(1)
            month_word = match_day_first.group(2).lower().rstrip(".")
            year_str = match_day_first.group(3)
            month_num = MONTH_MAP.get(month_word[:3]) or MONTH_MAP.get(month_word)
            if month_num:
                try:
                    dt_exact = datetime.date(int(year_str), month_num, int(day_str))
                    return {
                        "raw_date_str": raw_str,
                        "calendar_date": dt_exact.isoformat(),
                        "precision": "EXACT_DAY",
                        "display_badge": f"{dt_exact.day} {MONTH_NAMES_ES[dt_exact.month - 1][:3]} {dt_exact.year}"
                    }
                except ValueError:
                    pass

        # Mes primero: Oct 24, 2026
        match_month_first = re.search(r"([a-zA-Z]{3,12})\s*(\d{1,2})\s*(?:st|nd|rd|th)?,?\s*(\d{4})", raw_str)
        if match_month_first:
            month_word = match_month_first.group(1).lower().rstrip(".")
            day_str = match_month_first.group(2)
            year_str = match_month_first.group(3)
            month_num = MONTH_MAP.get(month_word[:3]) or MONTH_MAP.get(month_word)
            if month_num:
                try:
                    dt_exact = datetime.date(int(year_str), month_num, int(day_str))
                    return {
                        "raw_date_str": raw_str,
                        "calendar_date": dt_exact.isoformat(),
                        "precision": "EXACT_DAY",
                        "display_badge": f"{dt_exact.day} {MONTH_NAMES_ES[dt_exact.month - 1][:3]} {dt_exact.year}"
                    }
                except ValueError:
                    pass

        # Mes y Año sin día exacto: Noviembre 2026 (sin palabras como trimestre)
        if "trimestre" not in raw_lower and "quarter" not in raw_lower:
            match_month_year = re.search(r"\b([a-zA-ZáéíóúÁÉÍÓÚ]{3,12})\s*(?:de)?\s*(\d{4})\b", raw_str)
            if match_month_year:
                month_word = match_month_year.group(1).lower().rstrip(".")
                year_str = match_month_year.group(2)
                month_num = MONTH_MAP.get(month_word[:3]) or MONTH_MAP.get(month_word)
                if month_num:
                    return {
                        "raw_date_str": raw_str,
                        "calendar_date": None,
                        "precision": "MONTH",
                        "display_badge": f"{month_word.capitalize()} {year_str}"
                    }

        # Año únicamente: "2027", "Año 2027", "Year 2027"
        match_year_only = re.search(r"^(?:año|year)?\s*(202[4-9]|203[0-9])$", raw_lower.strip())
        if match_year_only:
            year_str = match_year_only.group(1)
            return {
                "raw_date_str": raw_str,
                "calendar_date": None,
                "precision": "YEAR",
                "display_badge": f"Año {year_str}"
            }

    # 3. Si viene con un timestamp UNIX válido sin display_type explícito
    if dt:
        iso_date = dt.strftime("%Y-%m-%d")

        # Heurística de Valve: si la fecha cae en 1 de enero de un año futuro (ej: 2027-01-01) y no hay día en raw_str,
        # es el timestamp por defecto que Valve asigna cuando el desarrollador selecciona solo el AÑO.
        if dt.month == 1 and dt.day == 1 and dt.year >= 2026:
            return {
                "raw_date_str": raw_str or str(dt.year),
                "calendar_date": None,
                "precision": "YEAR",
                "display_badge": f"Año {dt.year}"
            }

        # Heurística de Valve para trimestres:
        # Steam mapea Q4 al 1 de diciembre (ej: 2027-12-01)
        if dt.month == 12 and dt.day == 1 and dt.year >= 2026:
            # Si el texto original dice "4.º trimestre", "Q4", o no tiene día confirmado
            if not raw_str or raw_str == iso_date or "trimestre" in raw_lower or "q4" in raw_lower:
                return {
                    "raw_date_str": raw_str or f"Q4 {dt.year}",
                    "calendar_date": None,
                    "precision": "QUARTER",
                    "display_badge": f"Q4 {dt.year}"
                }

        # Heurística de Valve para Q1 (1 de marzo o 1 de enero), Q2 (1 de junio), Q3 (1 de septiembre)
        if dt.day == 1 and dt.month in [3, 6, 9] and dt.year >= 2026:
            q_map = {3: 1, 6: 2, 9: 3}
            q_num = q_map[dt.month]
            if not raw_str or raw_str == iso_date or "trimestre" in raw_lower or f"q{q_num}" in raw_lower:
                return {
                    "raw_date_str": raw_str or f"Q{q_num} {dt.year}",
                    "calendar_date": None,
                    "precision": "QUARTER",
                    "display_badge": f"Q{q_num} {dt.year}"
                }

        return {
            "raw_date_str": raw_str or iso_date,
            "calendar_date": iso_date,
            "precision": "EXACT_DAY",
            "display_badge": f"{dt.day} {MONTH_NAMES_ES[dt.month - 1][:3]} {dt.year}"
        }

    # 4. Si raw_str contiene únicamente un año suelto en medio del texto:
    match_year_loose = re.search(r"\b(202[4-9]|203[0-9])\b", raw_str)
    if match_year_loose:
        year_str = match_year_loose.group(1)
        return {
            "raw_date_str": raw_str,
            "calendar_date": None,
            "precision": "YEAR",
            "display_badge": f"Año {year_str}"
        }

    # 5. Sin fecha o irreconocible -> TBA
    return {
        "raw_date_str": raw_str or "Coming Soon",
        "calendar_date": None,
        "precision": "TBA",
        "display_badge": raw_str if (raw_str and len(raw_str) <= 20) else "Por confirmar"
    }
