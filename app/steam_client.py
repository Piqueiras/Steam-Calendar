import json
import logging
from typing import Optional, List, Dict, Any
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

class SteamClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_active_steam_api_key()
        self.base_web_url = "https://api.steampowered.com"
        self.base_store_url = "https://store.steampowered.com"

    def fetch_popular_upcoming(self, max_items: int = 250) -> List[Dict[str, Any]]:
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
                                "include_assets": True
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
                                ts = rel.get("steam_release_date")
                                custom_msg = rel.get("custom_release_date_message")
                                display_type = rel.get("coming_soon_display")

                                date_info = parse_steam_date(
                                    raw_date=custom_msg,
                                    timestamp=ts,
                                    display_type=display_type
                                )

                                # Identificación real de DLC mediante la API oficial de Steam
                                type_id = it.get("type", 0)
                                rel_items = it.get("related_items", {})
                                parent_appid = rel_items.get("parent_appid")
                                is_dlc = type_id in [1, 4] or bool(parent_appid)
                                item_type = "DLC" if is_dlc else "GAME"

                                # Etiquetas
                                basic = it.get("basic_info", {})
                                tags = []
                                if is_dlc:
                                    tags.append("DLC / Expansión")
                                elif basic.get("short_description"):
                                    tags.append("Juego Oficial")
                                else:
                                    tags.append("Próximo Estreno")

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
                            "count": 50,
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
                            "include_assets": True
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
                            ts = rel.get("steam_release_date")
                            if not ts:
                                continue

                            date_info = parse_steam_date("", timestamp=ts)
                            type_id = it.get("type", 0)
                            rel_items = it.get("related_items", {})
                            parent_appid = rel_items.get("parent_appid")
                            is_dlc = type_id in [1, 4] or bool(parent_appid)
                            item_type = "DLC" if is_dlc else "GAME"

                            tags = ["DLC / Expansión"] if is_dlc else ["Lanzamiento Reciente"]
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
                                "source": "STEAM_RECENT"
                            }
            except Exception as e:
                logger.warning(f"Error consultando lanzamientos recientes: {e}")

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
                            "tags": ["Destacado Steam"],
                            "price_str": price_str,
                            "is_free": price_val == 0,
                            "deck_status": "UNKNOWN",
                            "item_type": "GAME",
                            "parent_appid": None,
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
                    "include_assets": True
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
                            # Si es un juego ya lanzado y no un próximo estreno, lo omitimos o marcamos
                            is_coming_soon = rel.get("is_coming_soon", False)
                            
                            ts = rel.get("steam_release_date")
                            custom_msg = rel.get("custom_release_date_message")
                            display_type = rel.get("coming_soon_display")

                            date_info = parse_steam_date(
                                raw_date=custom_msg,
                                timestamp=ts,
                                display_type=display_type
                            )

                            header_url, capsule_url = _extract_asset_urls(it, appid)

                            type_id = it.get("type", 0)
                            rel_items = it.get("related_items", {})
                            parent_appid = rel_items.get("parent_appid")
                            is_dlc = type_id in [1, 4] or bool(parent_appid)
                            item_type = "DLC" if is_dlc else "GAME"

                            tags = []
                            if is_dlc:
                                tags.append("DLC / Expansión")
                            else:
                                basic = it.get("basic_info", {})
                                if basic.get("short_description"):
                                    tags.append("Juego en Seguimiento")
                                else:
                                    tags.append("Próximo Estreno")

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
                                "source": "WISHLIST_API"
                            })
            except Exception as e:
                logger.warning(f"Error consultando detalles en lote para Wishlist: {e}")

        return detailed_games

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
