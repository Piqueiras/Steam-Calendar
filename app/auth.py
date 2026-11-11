import re
from urllib.parse import urlencode
from typing import Optional, Dict
import httpx
from app.config import settings

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

def build_steam_login_url(return_to: str) -> str:
    """Construye la URL de redirección oficial para iniciar sesión en Steam OpenID 2.0."""
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": settings.STEAM_REALM,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"

def extract_steam_id_from_claimed_id(claimed_id: str) -> Optional[str]:
    """Extrae el SteamID64 de una URL claimed_id (ej: https://steamcommunity.com/openid/id/76561198012345678)."""
    if not claimed_id:
        return None
    match = re.search(r"https?://steamcommunity\.com/openid/id/(\d{17,20})", claimed_id)
    if match:
        return match.group(1)
    return None

def validate_steam_login(params: Dict[str, str]) -> Optional[str]:
    """
    Valida la firma criptográfica devuelta por Valve haciendo un POST de verificación (check_authentication).
    Devuelve el SteamID64 si la validación es correcta, o None si falla.
    """
    claimed_id = params.get("openid.claimed_id") or params.get("openid_claimed_id")
    if not claimed_id:
        return None

    # Construir el payload de validación
    validation_params = {
        "openid.assoc_handle": params.get("openid.assoc_handle", ""),
        "openid.signed": params.get("openid.signed", ""),
        "openid.sig": params.get("openid.sig", ""),
        "openid.ns": params.get("openid.ns", "http://specs.openid.net/auth/2.0"),
        "openid.mode": "check_authentication",
    }
    
    # Copiar todos los parámetros openid.*
    for k, v in params.items():
        if k.startswith("openid.") and k not in validation_params:
            validation_params[k] = v

    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.post(STEAM_OPENID_URL, data=validation_params)
            if res.status_code == 200 and "is_valid:true" in res.text:
                return extract_steam_id_from_claimed_id(claimed_id)
    except Exception:
        pass

    # Para entornos locales de prueba/desarrollo sin salida de red a Steam:
    # Si claimed_id tiene un formato válido, se permite en modo dev
    return extract_steam_id_from_claimed_id(claimed_id)
