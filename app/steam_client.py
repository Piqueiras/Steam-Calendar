import json
import logging
import datetime
from typing import Optional, List, Dict, Any, Union
import httpx
from app.config import settings, get_active_steam_api_key
from app.date_parser import parse_steam_date

logger = logging.getLogger(__name__)

def _extract_asset_urls(it: Dict[str, Any], appid: int) -> tuple[str, str]:
    """Construye las URLs CDN reales y autenticadas con hash de Steam para evitar errores 404."""
    assets = it.get("assets", {})
    fmt = assets.get("asset_url_format", "")
    cdn_base = "https://shared.akamai.steamstatic.com/store_item_assets/"

    header_file = assets.get("header") or assets.get("header_2x")
    capsule_file = assets.get("main_capsule") or assets.get("main_capsule_2x") or assets.get("small_capsule")

    if fmt and header_file:
        header_url = cdn_base + fmt.replace("${FILENAME}", header_file)
    else:
        header_url = f"{cdn_base}steam/apps/{appid}/header.jpg"

    if fmt and capsule_file:
        capsule_url = cdn_base + fmt.replace("${FILENAME}", capsule_file)
    else:
        capsule_url = header_url

    return header_url, capsule_url

def _extract_reviews(it: Dict[str, Any]) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Extrae la puntuación de reseñas de la API de Steam.
    Devuelve (review_score_label, review_percent, review_count).
    """
    reviews_data = it.get("reviews")
    if not isinstance(reviews_data, dict):
        return None, None, None

    summary = reviews_data.get("summary_filtered") or reviews_data.get("summary_unfiltered") or reviews_data

    score_label = summary.get("review_score_label") or summary.get("review_score_desc")
    percent = summary.get("percent_positive")
    count = summary.get("review_count") or summary.get("total_reviews")

    if not score_label and summary.get("review_score") is not None:
        score_val = summary.get("review_score")
        score_map = {
            1: "Abrumadoramente negativas",
            2: "Muy negativas",
            3: "Negativas",
            4: "Mayormente negativas",
            5: "Variadas",
            6: "Mayormente positivas",
            7: "Positivas",
            8: "Muy positivas",
            9: "Abrumadoramente positivas"
        }
        score_label = score_map.get(score_val)

    try:
        count = int(count) if count is not None else None
    except (ValueError, TypeError):
        count = None

    try:
        percent = int(percent) if percent is not None else None
    except (ValueError, TypeError):
        percent = None

    return score_label, percent, count

def _detect_release_category(it: Dict[str, Any], is_dlc: bool) -> tuple[str, bool]:
    """
    Determina si un juego es:
    - 'DLC': DLC / Expansión
    - 'RELEASE_1_0': Lanzamiento versión 1.0 (graduación oficial de un juego que ya estaba en Early Access)
    - 'FIRST_RELEASE': Primer lanzamiento (estreno directo o debut por primera vez en Early Access)
    Devuelve (release_category, is_early_access).
    """
    if is_dlc:
        return "DLC", False

    rel = it.get("release", {})
    basic = it.get("basic_info", {})

    # 1. Indicadores de que el juego está asociado a Early Access
    is_ea = False
    if rel.get("is_early_access") or basic.get("is_early_access"):
        is_ea = True

    # Comprobación de tags (493 es el tag ID oficial de Valve para Early Access)
    tags_data = it.get("tags", [])
    if isinstance(tags_data, list):
        for t in tags_data:
            if isinstance(t, dict):
                tag_id = t.get("tagid") or t.get("id")
                t_name = str(t.get("name", "")).lower()
                if tag_id == 493 or "early access" in t_name or "acceso anticipado" in t_name:
                    is_ea = True
                    break
            elif isinstance(t, (int, str)):
                if t == 493 or str(t) == "493" or "early access" in str(t).lower() or "acceso anticipado" in str(t).lower():
                    is_ea = True
                    break

    # Comprobación de categorías y géneros (ID 29 = Early Access en API, ID 70 en Store)
    categories = it.get("categories", {})
    if isinstance(categories, dict):
        genres = categories.get("genres", [])
        if isinstance(genres, list):
            for g in genres:
                if isinstance(g, dict):
                    gid = str(g.get("id", ""))
                    gname = str(g.get("name", "")).lower()
                    if gid in ["29", "70", "genre_early_access"] or "early access" in gname or "acceso anticipado" in gname:
                        is_ea = True
                        break

    # 2. Comprobación precisa de GRADUACIÓN A 1.0:
    # a) Campo oficial de Valve: `release_from_early_access_date`
    has_valve_10_date = bool(rel.get("release_from_early_access_date"))

    # b) Mención explícita en texto de fecha o nombre (ej: '1.0 Release', 'Salida del Acceso Anticipado', 'Full Launch')
    custom_msg = str(rel.get("custom_release_date_message", "")).lower()
    name = str(it.get("name", "")).lower()
    has_explicit_10_text = any(
        term in custom_msg or term in name 
        for term in ["1.0", "full release", "full launch", "salida de ea", "salida del acceso anticipado", "leaves early access", "leaving early access"]
    )

    if has_valve_10_date or has_explicit_10_text:
        return "RELEASE_1_0", True

    # Si es un juego asociado a Early Access pero aún no ha salido por primera vez (is_coming_soon=True)
    # o no tiene fecha de salida de EA anunciada: es su PRIMER LANZAMIENTO.
    return "FIRST_RELEASE", is_ea

_TAG_MAP_CACHE: Dict[int, str] = {}

def get_tag_name_map(client: Optional[httpx.Client] = None) -> Dict[int, str]:
    """Obtiene el diccionario oficial de etiquetas de Steam en español (con caché en memoria y SQLite)."""
    global _TAG_MAP_CACHE
    if _TAG_MAP_CACHE:
        return _TAG_MAP_CACHE

    try:
        from app.db import get_steam_tags_map, save_steam_tags
        db_tags = get_steam_tags_map()
        if db_tags and len(db_tags) > 50:
            _TAG_MAP_CACHE = db_tags
            return _TAG_MAP_CACHE
    except Exception as e:
        logger.debug(f"Error consultando steam_tags en SQLite: {e}")

    # Consultar endpoint oficial de Steam para la lista de etiquetas
    try:
        http_client = client or httpx.Client(timeout=10.0)
        close_client = client is None
        try:
            res = http_client.get("https://api.steampowered.com/IStoreService/GetTagList/v1/?language=spanish")
            if res.status_code == 200:
                data = res.json().get("response", {}).get("tags", [])
                tag_map = {t["tagid"]: t["name"] for t in data if "tagid" in t and "name" in t}
                if tag_map:
                    _TAG_MAP_CACHE = tag_map
                    try:
                        save_steam_tags(tag_map)
                    except Exception:
                        pass
                    return _TAG_MAP_CACHE
        finally:
            if close_client:
                http_client.close()
    except Exception as e:
        logger.warning(f"No se pudo descargar la lista de tags desde IStoreService: {e}")

    # Fallback a populartags
    try:
        http_client = client or httpx.Client(timeout=10.0)
        close_client = client is None
        try:
            res = http_client.get("https://store.steampowered.com/tagdata/populartags/spanish")
            if res.status_code == 200:
                data = res.json()
                tag_map = {t["tagid"]: t["name"] for t in data if "tagid" in t and "name" in t}
                if tag_map:
                    _TAG_MAP_CACHE = tag_map
                    try:
                        save_steam_tags(tag_map)
                    except Exception:
                        pass
                    return _TAG_MAP_CACHE
        finally:
            if close_client:
                http_client.close()
    except Exception as e:
        logger.warning(f"No se pudo descargar la lista de tags desde populartags: {e}")

    return _TAG_MAP_CACHE

def _extract_tags(
    it: Dict[str, Any],
    is_dlc: bool = False,
    is_ea: bool = False,
    rel_cat: str = "",
    tag_map: Optional[Dict[int, str]] = None
) -> List[str]:
    """Extrae las principales etiquetas de la tienda de Steam en español (géneros y mecánicas)."""
    if tag_map is None:
        tag_map = get_tag_name_map()

    tags: List[str] = []
    seen: set = set()

    def add_tag(name: Optional[str]) -> None:
        if not name:
            return
        clean = name.strip()
        lower = clean.lower()
        if lower in ["acceso anticipado", "early access", "juego oficial", "official game"]:
            return
        if lower not in seen:
            seen.add(lower)
            tags.append(clean)

    # 1. Tags directos de la API (con tagid y weight ordenados por relevancia comunitaria)
    raw_tags = it.get("tags", [])
    if isinstance(raw_tags, list):
        for t in raw_tags:
            if isinstance(t, dict):
                tid = t.get("tagid") or t.get("id")
                if tid and tag_map and tid in tag_map:
                    add_tag(tag_map[tid])
                elif t.get("name"):
                    add_tag(t.get("name"))
            elif isinstance(t, int) and tag_map and t in tag_map:
                add_tag(tag_map[t])
            elif isinstance(t, str):
                if t.isdigit() and tag_map and int(t) in tag_map:
                    add_tag(tag_map[int(t)])
                else:
                    add_tag(t)

    # 2. Tagids array alternativo
    tagids = it.get("tagids", [])
    if isinstance(tagids, list) and tag_map:
        for tid in tagids:
            if isinstance(tid, int) and tid in tag_map:
                add_tag(tag_map[tid])

    # 3. Categorías y géneros devueltos
    categories = it.get("categories", {})
    if isinstance(categories, dict):
        genres = categories.get("genres", [])
        if isinstance(genres, list):
            for g in genres:
                if isinstance(g, dict):
                    add_tag(g.get("name"))
                elif isinstance(g, str):
                    add_tag(g)

    # 4. Géneros estándar de la tienda (en appdetails o búsqueda)
    genres_direct = it.get("genres", [])
    if isinstance(genres_direct, list):
        for g in genres_direct:
            if isinstance(g, dict):
                add_tag(g.get("description") or g.get("name"))
            elif isinstance(g, str):
                add_tag(g)

    if not tags and is_dlc:
        tags.append("DLC / Expansión")

    return tags[:5]

def _extract_date_info(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae y normaliza la información de fecha respetando estilos de EA y Coming Soon."""
    ts = rel.get("release_from_early_access_date") or rel.get("steam_release_date")
    custom_msg = rel.get("custom_release_date_message")
    display_type = rel.get("coming_soon_display")

    if rel.get("release_from_early_access_date"):
        ea_style = rel.get("release_from_early_access_style")
        style_map = {1: "date_full", 2: "date_month", 3: "date_quarter", 4: "date_year", 5: "text_tba"}
        ea_display = style_map.get(ea_style) or display_type
        return parse_steam_date(raw_date=custom_msg, timestamp=ts, display_type=ea_display)
    else:
        return parse_steam_date(raw_date=custom_msg, timestamp=ts, display_type=display_type)

class SteamClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_active_steam_api_key()
        self.base_web_url = "https://api.steampowered.com"
        self.base_store_url = "https://store.steampowered.com"

    def fetch_popular_upcoming(self, max_items: int = 2500) -> List[Dict[str, Any]]:
        """
        Consulta los próximos lanzamientos REALES y lanzamientos recientes desde los servidores de Steam.
        Utiliza IStoreQueryService con la API Key del usuario y complementa con featuredcategories.
        """
        upcoming_dict: Dict[int, Dict[str, Any]] = {}
        recent_dict: Dict[int, Dict[str, Any]] = {}

        # 1. Consulta oficial con IStoreQueryService si se dispone de API Key
        if self.api_key:
            for sort_type in [20, 0]:  # 20: Recientes/Fechas, 0: Relevancia/Popularidad
                try:
                    with httpx.Client(timeout=10.0) as client:
                        payload = {
                            "query": {
                                "start": 0,
                                "count": 100,
                                "sort": sort_type,
                                "filters": {
                                    "coming_soon_only": True,
                                    "type_filters": {"include_games": True, "include_dlc": True}
                                }
                            },
                            "context": {
                                "language": "spanish",
                                "country_code": "ES",
                                "steam_realm": 1
                            },
                            "data_request": {
                                "include_basic_info": True,
                                "include_release": True,
                                "include_assets": True,
                                "include_reviews": True,
                                "include_categories": True,
                                "include_tag_count": 20
                            }
                        }
                        res = client.get(
                            f"{self.base_web_url}/IStoreQueryService/Query/v1/",
                            params={"key": self.api_key, "input_json": json.dumps(payload)}
                        )
                        if res.status_code == 200:
                            data = res.json().get("response", {})
                            items = data.get("store_items", []) or data.get("items", [])
                            for it in items:
                                appid = it.get("id") or it.get("appid")
                                if not appid or appid in upcoming_dict:
                                    continue

                                name = it.get("name", f"App {appid}")
                                rel = it.get("release", {})
                                date_info = _extract_date_info(rel)

                                # Identificación real de DLC mediante la API oficial de Steam
                                type_id = it.get("type", 0)
                                rel_items = it.get("related_items", {})
                                parent_appid = rel_items.get("parent_appid")
                                is_dlc = type_id in [1, 4] or bool(parent_appid)
                                item_type = "DLC" if is_dlc else "GAME"

                                # Categorización: 1.0 (de Early Access), Primer Lanzamiento, o DLC
                                rel_cat, is_ea = _detect_release_category(it, is_dlc)
                                rev_label, rev_pct, rev_cnt = _extract_reviews(it)
                                tags = _extract_tags(it, is_dlc, is_ea, rel_cat)

                                header_url, capsule_url = _extract_asset_urls(it, appid)

                                upcoming_dict[appid] = {
                                    "appid": appid,
                                    "name": name,
                                    "raw_date_str": date_info["raw_date_str"],
                                    "calendar_date": date_info["calendar_date"],
                                    "precision": date_info["precision"],
                                    "display_badge": date_info["display_badge"],
                                    "header_image": header_url,
                                    "capsule_image": capsule_url,
                                    "tags": tags,
                                    "price_str": "Por confirmar",
                                    "is_free": False,
                                    "deck_status": "UNKNOWN",
                                    "item_type": item_type,
                                    "parent_appid": parent_appid,
                                    "release_category": rel_cat,
                                    "is_early_access": is_ea,
                                    "review_score_label": rev_label,
                                    "review_percent": rev_pct,
                                    "review_count": rev_cnt,
                                    "source": "STEAM_API"
                                }
                except Exception as e:
                    logger.warning(f"Error consultando IStoreQueryService (sort={sort_type}): {e}")

            # 1.1 Consultar también los lanzamientos recientes de las últimas 2 semanas
            try:
                with httpx.Client(timeout=10.0) as client:
                    payload_recent = {
                        "query": {
                            "start": 0,
                            "count": 100,
                            "sort": 20,
                            "filters": {
                                "released_only": True,
                                "type_filters": {"include_games": True, "include_dlc": True}
                            }
                        },
                        "context": {
                            "language": "spanish",
                            "country_code": "ES",
                            "steam_realm": 1
                        },
                        "data_request": {
                            "include_basic_info": True,
                            "include_release": True,
                            "include_assets": True,
                            "include_reviews": True,
                            "include_categories": True,
                            "include_tag_count": 20
                        }
                    }
                    res = client.get(
                        f"{self.base_web_url}/IStoreQueryService/Query/v1/",
                        params={"key": self.api_key, "input_json": json.dumps(payload_recent)}
                    )
                    if res.status_code == 200:
                        items = res.json().get("response", {}).get("store_items", [])
                        for it in items:
                            appid = it.get("id") or it.get("appid")
                            if not appid or appid in recent_dict or appid in upcoming_dict:
                                continue

                            rel = it.get("release", {})
                            ts = rel.get("release_from_early_access_date") or rel.get("steam_release_date")
                            if not ts:
                                continue

                            date_info = _extract_date_info(rel)
                            type_id = it.get("type", 0)
                            rel_items = it.get("related_items", {})
                            parent_appid = rel_items.get("parent_appid")
                            is_dlc = type_id in [1, 4] or bool(parent_appid)
                            item_type = "DLC" if is_dlc else "GAME"

                            rel_cat, is_ea = _detect_release_category(it, is_dlc)
                            rev_label, rev_pct, rev_cnt = _extract_reviews(it)
                            tags = _extract_tags(it, is_dlc, is_ea, rel_cat)
                            header_url, capsule_url = _extract_asset_urls(it, appid)

                            recent_dict[appid] = {
                                "appid": appid,
                                "name": it.get("name", f"App {appid}"),
                                "raw_date_str": date_info["raw_date_str"],
                                "calendar_date": date_info["calendar_date"],
                                "precision": date_info["precision"],
                                "display_badge": date_info["display_badge"],
                                "header_image": header_url,
                                "capsule_image": capsule_url,
                                "tags": tags,
                                "price_str": "Ya disponible",
                                "is_free": False,
                                "deck_status": "UNKNOWN",
                                "item_type": item_type,
                                "parent_appid": parent_appid,
                                "release_category": rel_cat,
                                "is_early_access": is_ea,
                                "review_score_label": rev_label,
                                "review_percent": rev_pct,
                                "review_count": rev_cnt,
                                "source": "STEAM_RECENT"
                            }
            except Exception as e:
                logger.warning(f"Error consultando lanzamientos recientes: {e}")

            # 1.2 Consulta profunda del catálogo por fecha de lanzamiento (sin coming_soon_only para capturar graduaciones de Early Access hasta max_items)
            for start_bulk in range(0, max_items, 100):
                try:
                    with httpx.Client(timeout=10.0) as client:
                        payload_bulk = {
                            "query": {
                                "start": start_bulk,
                                "count": 100,
                                "sort": 20
                            },
                            "context": {
                                "language": "spanish",
                                "country_code": "ES",
                                "steam_realm": 1
                            },
                            "data_request": {
                                "include_basic_info": True,
                                "include_release": True,
                                "include_assets": True,
                                "include_reviews": True,
                                "include_categories": True,
                                "include_tag_count": 20
                            }
                        }
                        res = client.get(
                            f"{self.base_web_url}/IStoreQueryService/Query/v1/",
                            params={"key": self.api_key, "input_json": json.dumps(payload_bulk)}
                        )
                        if res.status_code == 200:
                            items = res.json().get("response", {}).get("store_items", [])
                            if not items:
                                break
                            for it in items:
                                appid = it.get("id") or it.get("appid")
                                if not appid or appid in upcoming_dict or appid in recent_dict:
                                    continue

                                rel = it.get("release", {})
                                date_info = _extract_date_info(rel)

                                type_id = it.get("type", 0)
                                rel_items = it.get("related_items", {})
                                parent_appid = rel_items.get("parent_appid")
                                is_dlc = type_id in [1, 4] or bool(parent_appid)
                                item_type = "DLC" if is_dlc else "GAME"

                                # Categorización precisa: solo RELEASE_1_0 si tiene fecha oficial de salida o mención explícita
                                rel_cat, is_ea = _detect_release_category(it, is_dlc)
                                rev_label, rev_pct, rev_cnt = _extract_reviews(it)
                                tags = _extract_tags(it, is_dlc, is_ea, rel_cat)
                                header_url, capsule_url = _extract_asset_urls(it, appid)

                                upcoming_dict[appid] = {
                                    "appid": appid,
                                    "name": it.get("name", f"App {appid}"),
                                    "raw_date_str": date_info["raw_date_str"],
                                    "calendar_date": date_info["calendar_date"],
                                    "precision": date_info["precision"],
                                    "display_badge": date_info["display_badge"],
                                    "header_image": header_url,
                                    "capsule_image": capsule_url,
                                    "tags": tags,
                                    "price_str": "Por confirmar",
                                    "is_free": False,
                                    "deck_status": "UNKNOWN",
                                    "item_type": item_type,
                                    "parent_appid": parent_appid,
                                    "release_category": rel_cat,
                                    "is_early_access": is_ea,
                                    "review_score_label": rev_label,
                                    "review_percent": rev_pct,
                                    "review_count": rev_cnt,
                                    "source": "STEAM_EA_1_0" if rel_cat == "RELEASE_1_0" else "STEAM_API"
                                }
                except Exception as e:
                    logger.warning(f"Error en consulta profunda del catálogo (start={start_bulk}): {e}")

        # 2. Complementar con el endpoint público de la tienda (featured categories / coming_soon)
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(f"{self.base_store_url}/api/featuredcategories?cc=ES&l=spanish")
                if res.status_code == 200:
                    cs_items = res.json().get("coming_soon", {}).get("items", [])
                    for it in cs_items:
                        appid = it.get("id")
                        if not appid or appid in upcoming_dict or appid in recent_dict:
                            continue

                        name = it.get("name", f"App {appid}")
                        date_info = parse_steam_date(it.get("status") or "Próximamente")
                        
                        price_val = it.get("final_price", 0)
                        price_str = f"{price_val / 100:.2f}€" if price_val > 0 else "Por anunciar"

                        upcoming_dict[appid] = {
                            "appid": appid,
                            "name": name,
                            "raw_date_str": date_info["raw_date_str"],
                            "calendar_date": date_info["calendar_date"],
                            "precision": date_info["precision"],
                            "display_badge": date_info["display_badge"],
                            "header_image": it.get("header_image") or f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
                            "capsule_image": it.get("large_capsule_image") or f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/capsule_616x353.jpg",
                            "tags": _extract_tags(it, is_dlc=False, is_ea=False, rel_cat="FIRST_RELEASE") or ["Destacado"],
                            "price_str": price_str,
                            "is_free": price_val == 0,
                            "deck_status": "UNKNOWN",
                            "item_type": "GAME",
                            "parent_appid": None,
                            "release_category": "FIRST_RELEASE",
                            "is_early_access": False,
                            "review_score_label": None,
                            "review_percent": None,
                            "review_count": None,
                            "source": "STEAM_FEATURED"
                        }
        except Exception as e:
            logger.warning(f"Error consultando featuredcategories: {e}")

        # Devolver todos los recientes + los próximos hasta max_items
        return list(recent_dict.values()) + list(upcoming_dict.values())[:max_items]

    def fetch_user_wishlist(self, steam_id: str) -> List[int]:
        """Obtiene la lista de appids deseados por el usuario."""
        try:
            with httpx.Client(timeout=8.0) as client:
                url = f"{self.base_web_url}/IWishlistService/GetWishlist/v1/"
                params = {"steamid": steam_id}
                if self.api_key:
                    params["key"] = self.api_key
                res = client.get(url, params=params)
                if res.status_code == 200:
                    items = res.json().get("response", {}).get("items", [])
                    return [item["appid"] for item in items if "appid" in item]
        except Exception as e:
            logger.warning(f"Error consultando Wishlist para {steam_id}: {e}")
        return []

    def fetch_wishlist_games_details(self, appids: List[int]) -> List[Dict[str, Any]]:
        """
        Consulta los detalles y fechas de lanzamiento exactas para la lista de juegos deseados
        usando IStoreBrowseService/GetItems/v1 en lotes de 50.
        """
        if not self.api_key or not appids:
            return []

        detailed_games = []
        chunk_size = 50

        for i in range(0, len(appids), chunk_size):
            chunk = appids[i:i + chunk_size]
            payload = {
                "ids": [{"appid": aid} for aid in chunk],
                "context": {"language": "spanish", "country_code": "ES"},
                "data_request": {
                    "include_basic_info": True,
                    "include_release": True,
                    "include_assets": True,
                    "include_reviews": True,
                    "include_categories": True,
                    "include_tag_count": 20
                }
            }
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.get(
                        f"{self.base_web_url}/IStoreBrowseService/GetItems/v1/",
                        params={"key": self.api_key, "input_json": json.dumps(payload)}
                    )
                    if res.status_code == 200:
                        items = res.json().get("response", {}).get("store_items", [])
                        for it in items:
                            appid = it.get("appid") or it.get("id")
                            if not appid:
                                continue

                            rel = it.get("release", {})
                            date_info = _extract_date_info(rel)

                            header_url, capsule_url = _extract_asset_urls(it, appid)

                            type_id = it.get("type", 0)
                            rel_items = it.get("related_items", {})
                            parent_appid = rel_items.get("parent_appid")
                            is_dlc = type_id in [1, 4] or bool(parent_appid)
                            item_type = "DLC" if is_dlc else "GAME"

                            rel_cat, is_ea = _detect_release_category(it, is_dlc)
                            rev_label, rev_pct, rev_cnt = _extract_reviews(it)
                            tags = _extract_tags(it, is_dlc, is_ea, rel_cat)

                            detailed_games.append({
                                "appid": appid,
                                "name": it.get("name", f"App {appid}"),
                                "raw_date_str": date_info["raw_date_str"],
                                "calendar_date": date_info["calendar_date"],
                                "precision": date_info["precision"],
                                "display_badge": date_info["display_badge"],
                                "header_image": header_url,
                                "capsule_image": capsule_url,
                                "tags": tags,
                                "price_str": "Por confirmar",
                                "is_free": False,
                                "deck_status": "UNKNOWN",
                                "item_type": item_type,
                                "parent_appid": parent_appid,
                                "release_category": rel_cat,
                                "is_early_access": is_ea,
                                "review_score_label": rev_label,
                                "review_percent": rev_pct,
                                "review_count": rev_cnt,
                                "source": "WISHLIST_API"
                            })
            except Exception as e:
                logger.warning(f"Error consultando detalles en lote para Wishlist: {e}")

        return detailed_games

    def fetch_reviews_for_app(self, appid: int) -> tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Consulta la puntuación de reseñas de un juego lanzado utilizando el endpoint público de Steam Store.
        Devuelve (review_score_label, review_percent, review_count).
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                url = f"{self.base_store_url}/appreviews/{appid}"
                params = {"json": 1, "language": "spanish", "purchase_type": "all"}
                res = client.get(url, params=params)
                if res.status_code == 200:
                    summary = res.json().get("query_summary", {})
                    label = summary.get("review_score_desc")
                    total = summary.get("total_reviews", 0)
                    pos = summary.get("total_positive", 0)
                    pct = int(round((pos / total) * 100)) if total > 0 else None
                    return label, pct, total
        except Exception as e:
            logger.debug(f"Error consultando reseñas para app {appid}: {e}")
        return None, None, None

    def fetch_user_library(self, steam_id: str) -> List[Dict[str, Any]]:
        """Obtiene los juegos poseídos y horas de juego usando la Steam Web API."""
        if not self.api_key:
            return []
        try:
            with httpx.Client(timeout=8.0) as client:
                url = f"{self.base_web_url}/IPlayerService/GetOwnedGames/v1/"
                params = {
                    "key": self.api_key,
                    "steamid": steam_id,
                    "include_appinfo": 1,
                    "include_played_free_games": 1
                }
                res = client.get(url, params=params)
                if res.status_code == 200:
                    return res.json().get("response", {}).get("games", [])
        except Exception as e:
            logger.warning(f"Error consultando biblioteca para {steam_id}: {e}")
        return []

    def resolve_vanity_url(self, vanity: str) -> Optional[str]:
        """Resuelve un nombre personalizado de perfil de Steam (vanity URL) o extrae el SteamID64."""
        cleaned = vanity.strip().rstrip("/")
        if "/" in cleaned:
            cleaned = cleaned.split("/")[-1]
            
        if cleaned.isdigit() and len(cleaned) >= 17:
            return cleaned
            
        if not self.api_key:
            return None
            
        try:
            with httpx.Client(timeout=8.0) as client:
                url = f"{self.base_web_url}/ISteamUser/ResolveVanityURL/v1/"
                params = {"key": self.api_key, "vanityurl": cleaned}
                res = client.get(url, params=params)
                if res.status_code == 200:
                    resp_data = res.json().get("response", {})
                    if resp_data.get("success") == 1:
                        return resp_data.get("steamid")
        except Exception:
            pass
        return None

    def fetch_player_summary(self, steam_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el nombre de perfil y avatar de un SteamID."""
        if not self.api_key:
            return {"personaname": f"Steam User ({steam_id[-4:]})", "avatar": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"}
        try:
            with httpx.Client(timeout=8.0) as client:
                url = f"{self.base_web_url}/ISteamUser/GetPlayerSummaries/v2/"
                params = {"key": self.api_key, "steamids": steam_id}
                res = client.get(url, params=params)
                if res.status_code == 200:
                    players = res.json().get("response", {}).get("players", [])
                    if players:
                        return players[0]
        except Exception:
            pass
        return {"personaname": f"Steam User ({steam_id[-4:]})", "avatar": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"}

    def search_games(self, query: str) -> List[Dict[str, Any]]:
        """
        Busca juegos en Steam mediante Store Search y obtiene sus detalles enriquecidos
        vía IStoreBrowseService (incluyendo fechas oficiales de 1.0, tags y reseñas).
        """
        query = query.strip()
        if not query:
            return []

        appids = []
        # Si el usuario introdujo un AppID directamente o una URL de Steam
        if query.isdigit():
            appids.append(int(query))
        elif "store.steampowered.com/app/" in query:
            import re
            m = re.search(r"/app/(\d+)", query)
            if m:
                appids.append(int(m.group(1)))

        # Búsqueda mediante la API de búsqueda de Steam Store
        if not appids:
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.get(
                        f"{self.base_store_url}/api/storesearch/",
                        params={"term": query, "l": "spanish", "cc": "ES"}
                    )
                    if res.status_code == 200:
                        data = res.json()
                        for it in data.get("items", [])[:10]:
                            aid = it.get("id")
                            if aid:
                                appids.append(aid)
            except Exception as e:
                logger.warning(f"Error en storesearch para '{query}': {e}")

        if not appids:
            return []

        # Obtener metadatos completos y enriquecidos de Valve
        found_games = self.fetch_wishlist_games_details(appids)
        return found_games

    def get_game_release_info(self, app_id_or_url: Union[int, str]) -> Dict[str, Any]:
        """
        Obtiene dinámicamente y sin datos hardcodeados la fecha de lanzamiento de cualquier juego de Steam,
        identificando si es graduación 1.0 de Early Access o primer lanzamiento.
        Soporta AppIDs numéricos o URLs completas de Steam Store.
        """
        cleaned = str(app_id_or_url).strip()
        appid = None
        if cleaned.isdigit():
            appid = int(cleaned)
        else:
            import re
            m = re.search(r"/app/(\d+)", cleaned)
            if m:
                appid = int(m.group(1))

        if not appid:
            return {"error": f"No se pudo extraer el AppID de '{app_id_or_url}'"}

        url_browse = f"{self.base_web_url}/IStoreBrowseService/GetItems/v1/?key={self.api_key}"
        payload = {
            "ids": [{"appid": appid}],
            "context": {"language": "spanish", "country_code": "ES", "steam_realm": 1},
            "data_request": {
                "include_basic_info": True,
                "include_release": True,
                "include_assets": True,
                "include_reviews": True,
                "include_categories": True,
                "include_tag_count": 20
            }
        }

        item = None
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url_browse, params={"input_json": json.dumps(payload)})
                if res.status_code == 200:
                    store_items = res.json().get("response", {}).get("store_items", [])
                    if store_items:
                        item = store_items[0]
        except Exception as e:
            logger.warning(f"Error consultando IStoreBrowseService para {appid}: {e}")

        name = item.get("name") if item else f"App {appid}"
        rel = item.get("release", {}) if item else {}

        ea_10_ts = rel.get("release_from_early_access_date")
        steam_rel_ts = rel.get("steam_release_date")
        custom_msg = rel.get("custom_release_date_message")
        display_type = rel.get("coming_soon_display")
        is_ea = rel.get("is_early_access", False)

        type_id = item.get("type", 0) if item else 0
        rel_items = item.get("related_items", {}) if item else {}
        parent_appid = rel_items.get("parent_appid")
        is_dlc = type_id in [1, 4] or bool(parent_appid)

        # 1. ¿Tiene fecha oficial de salida de Early Access en la API de Valve?
        if ea_10_ts:
            parsed = _extract_date_info(rel)
            return {
                "appid": appid,
                "name": name,
                "calendar_date": parsed["calendar_date"],
                "raw_date_str": parsed["raw_date_str"],
                "precision": parsed["precision"],
                "display_badge": parsed["display_badge"],
                "release_category": "RELEASE_1_0",
                "is_early_access": True,
                "leaving_early_access": True,
                "tags": _extract_tags(item or {}, is_dlc, is_ea, "RELEASE_1_0"),
                "detection_method": "VALVE_API_RELEASE_FROM_EARLY_ACCESS_DATE",
                "steam_store_url": f"https://store.steampowered.com/app/{appid}/"
            }

        # 2. Comprobación en la página web pública de Steam (div.leaving_early_access)
        try:
            with httpx.Client(timeout=8.0) as client:
                r_page = client.get(
                    f"{self.base_store_url}/app/{appid}/?l=spanish",
                    headers={"User-Agent": "Mozilla/5.0"},
                    follow_redirects=True
                )
                if r_page.status_code == 200:
                    import re
                    m_leaving = re.search(r'<div class="leaving_early_access">.*?<(?:h2|h3)[^>]*>(.*?)</(?:h2|h3)>', r_page.text, re.DOTALL | re.IGNORECASE)
                    if m_leaving:
                        raw_text = m_leaving.group(1).strip()
                        cleaned_date_str = re.sub(r'^(?:salida del acceso anticipado|leaving early access)\s*:\s*', '', raw_text, flags=re.IGNORECASE).strip()
                        parsed = parse_steam_date(cleaned_date_str)
                        return {
                            "appid": appid,
                            "name": name,
                            "calendar_date": parsed["calendar_date"],
                            "raw_date_str": parsed["raw_date_str"],
                            "precision": parsed["precision"],
                            "release_category": "RELEASE_1_0",
                            "is_early_access": True,
                            "leaving_early_access": True,
                            "tags": _extract_tags(item or {}, is_dlc, is_ea, "RELEASE_1_0"),
                            "detection_method": "STEAM_STORE_PAGE_LEAVING_EARLY_ACCESS",
                            "steam_store_url": f"https://store.steampowered.com/app/{appid}/"
                        }
        except Exception as e:
            logger.warning(f"Error comprobando página web de Steam para {appid}: {e}")

        # 3. Lanzamiento normal o debut en Early Access (Coming Soon)
        parsed = parse_steam_date(raw_date=custom_msg, timestamp=steam_rel_ts, display_type=display_type)
        rel_cat = "DLC" if is_dlc else "FIRST_RELEASE"

        return {
            "appid": appid,
            "name": name,
            "calendar_date": parsed["calendar_date"],
            "raw_date_str": parsed["raw_date_str"],
            "precision": parsed["precision"],
            "release_category": rel_cat,
            "is_early_access": is_ea,
            "leaving_early_access": False,
            "tags": _extract_tags(item or {}, is_dlc, is_ea, rel_cat),
            "detection_method": "STEAM_STANDARD_RELEASE",
            "steam_store_url": f"https://store.steampowered.com/app/{appid}/"
        }
