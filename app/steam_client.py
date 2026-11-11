import json
import re
import html
from typing import Optional, List, Dict, Any
import httpx
from app.config import settings, get_active_steam_api_key
from app.date_parser import parse_steam_date

# Lista de muestra realista para fallback cuando no hay conexión externa o en tests
SAMPLE_UPCOMING_GAMES = [
    {
        "appid": 1030300,
        "name": "Hollow Knight: Silksong",
        "raw_date_str": "Coming Soon",
        "tags": ["Metroidvania", "Souls-like", "Acción", "2D"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1030300/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1030300/header.jpg",
        "price_str": "Por anunciar",
        "is_free": False,
        "deck_status": "VERIFIED"
    },
    {
        "appid": 2246340,
        "name": "Monster Hunter Wilds",
        "raw_date_str": "28 Feb, 2027",
        "tags": ["Caza", "Multijugador", "Rol de acción", "Mundo abierto"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2246340/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2246340/header.jpg",
        "price_str": "69,99€",
        "is_free": False,
        "deck_status": "PLAYABLE"
    },
    {
        "appid": 1774580,
        "name": "STAR WARS Outlaws",
        "raw_date_str": "21 Nov, 2026",
        "tags": ["Aventura", "Mundo abierto", "Ciencia ficción", "Disparos"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1774580/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1774580/header.jpg",
        "price_str": "69,99€",
        "is_free": False,
        "deck_status": "VERIFIED"
    },
    {
        "appid": 2420110,
        "name": "Civilization VII",
        "raw_date_str": "11 Feb, 2027",
        "tags": ["Estrategia", "Por turnos", "Histórico", "4X"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2420110/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2420110/header.jpg",
        "price_str": "69,99€",
        "is_free": False,
        "deck_status": "PLAYABLE"
    },
    {
        "appid": 2358720,
        "name": "Black Myth: Wukong - Expansion DLC",
        "raw_date_str": "Q1 2027",
        "tags": ["Rol de acción", "Mitología", "Souls-like"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2358720/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2358720/header.jpg",
        "price_str": "29,99€",
        "is_free": False,
        "deck_status": "VERIFIED"
    },
    {
        "appid": 1462040,
        "name": "Final Fantasy XVI",
        "raw_date_str": "17 Nov, 2026",
        "tags": ["JRPG", "Acción", "Fantasía oscura", "Historia rica"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1462040/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1462040/header.jpg",
        "price_str": "49,99€",
        "is_free": False,
        "deck_status": "VERIFIED"
    },
    {
        "appid": 2050650,
        "name": "Resident Evil 9",
        "raw_date_str": "Q4 2027",
        "tags": ["Terror de supervivencia", "Acción", "Zombis"],
        "capsule_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2050650/header.jpg",
        "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2050650/header.jpg",
        "price_str": "69,99€",
        "is_free": False,
        "deck_status": "UNKNOWN"
    }
]

class SteamClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_active_steam_api_key()
        self.base_web_url = "https://api.steampowered.com"
        self.base_store_url = "https://store.steampowered.com"

    def _parse_html_search_results(self, html_content: str) -> List[Dict[str, Any]]:
        """Extrae juegos de los resultados HTML devueltos por el endpoint search/results."""
        games = []
        # Buscar bloques <a href=".../app/12345/..." ...>
        app_pattern = re.compile(
            r'href="https://store\.steampowered\.com/app/(\d+)/([^/"]*)/[^"]*".*?'
            r'class="title">([^<]+)</span>.*?'
            r'(?:class="search_released[^>]*>([^<]*)</div>)?.*?'
            r'(?:class="discount_final_price[^>]*>([^<]*)</div>)?',
            re.DOTALL
        )
        for match in app_pattern.finditer(html_content):
            appid_str, slug, name_raw, release_raw, price_raw = match.groups()
            appid = int(appid_str)
            name = html.unescape(name_raw.strip())
            raw_date = html.unescape(release_raw.strip()) if release_raw else "Coming Soon"
            price = html.unescape(price_raw.strip()) if price_raw else ""
            date_info = parse_steam_date(raw_date)

            header_img = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
            capsule_img = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/capsule_616x353.jpg"

            games.append({
                "appid": appid,
                "name": name,
                "raw_date_str": date_info["raw_date_str"],
                "calendar_date": date_info["calendar_date"],
                "precision": date_info["precision"],
                "display_badge": date_info["display_badge"],
                "header_image": header_img,
                "capsule_image": capsule_img,
                "tags": ["Destacado", "Popular"],
                "price_str": price,
                "is_free": "Free" in price or "Gratis" in price,
                "deck_status": "UNKNOWN",
                "source": "STEAM_SEARCH"
            })
        return games

    def fetch_popular_upcoming(self, count: int = 50) -> List[Dict[str, Any]]:
        """Consulta el catálogo de próximos lanzamientos de Steam (público o con API Key)."""
        # Si disponemos de clave, podemos consultar IStoreQueryService
        if self.api_key:
            try:
                with httpx.Client(timeout=8.0) as client:
                    input_payload = {
                        "query": {
                            "start": 0,
                            "count": count,
                            "sort": 20,
                            "filters": {
                                "coming_soon_only": True,
                                "type_filters": {"include_games": True}
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
                        params={"key": self.api_key, "input_json": json.dumps(input_payload)}
                    )
                    if res.status_code == 200:
                        items = res.json().get("response", {}).get("store_items", [])
                        if items:
                            parsed_items = []
                            for it in items:
                                appid = it.get("appid")
                                name = it.get("name", f"App {appid}")
                                rel = it.get("release", {})
                                raw_date = rel.get("custom_release_date_message") or ""
                                ts = rel.get("steam_release_date")
                                date_info = parse_steam_date(raw_date, timestamp=ts)
                                parsed_items.append({
                                    "appid": appid,
                                    "name": name,
                                    "raw_date_str": date_info["raw_date_str"],
                                    "calendar_date": date_info["calendar_date"],
                                    "precision": date_info["precision"],
                                    "display_badge": date_info["display_badge"],
                                    "header_image": f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
                                    "capsule_image": f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/capsule_616x353.jpg",
                                    "tags": ["Lanzamiento Oficial"],
                                    "price_str": "",
                                    "is_free": False,
                                    "deck_status": "UNKNOWN",
                                    "source": "ISTORE_QUERY"
                                })
                            return parsed_items
            except Exception:
                pass  # Fallback a search o sample data

        # Intentar con endpoint público de Steam search results
        try:
            with httpx.Client(timeout=8.0) as client:
                url = f"{self.base_store_url}/search/results/"
                params = {
                    "filter": "popularcomingsoon",
                    "category1": "998",
                    "count": count,
                    "json": "1"
                }
                res = client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    html_chunk = data.get("results_html", "")
                    games = self._parse_html_search_results(html_chunk)
                    if games:
                        return games
        except Exception:
            pass

        # Fallback resiliente si la red está inaccesible (sandbox / offline)
        results = []
        for g in SAMPLE_UPCOMING_GAMES:
            date_info = parse_steam_date(g["raw_date_str"])
            item = dict(g)
            item.update({
                "calendar_date": date_info["calendar_date"],
                "precision": date_info["precision"],
                "display_badge": date_info["display_badge"],
                "source": "SAMPLE_DATA"
            })
            results.append(item)
        return results

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
        except Exception:
            pass
        return []

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
        except Exception:
            pass
        return []

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
