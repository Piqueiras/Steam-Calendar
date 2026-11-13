import os
import json
from flask import Flask, render_template, request, redirect, session, jsonify, Response, url_for
from app.config import settings, get_active_steam_api_key, update_env_api_key
from app.db import init_db, save_user_wishlist, save_user_library, set_setting, get_setting, save_games_batch, save_game
from app.auth import build_steam_login_url, validate_steam_login
from app.calendar_service import CalendarService
from app.steam_client import SteamClient

app = Flask(
    __name__,
    template_folder=str(settings.DB_PATH.replace("steam_calendar.db", "templates")),
    static_folder=str(settings.DB_PATH.replace("steam_calendar.db", "static"))
)
app.secret_key = settings.SECRET_KEY

# Inicializar base de datos al arrancar
init_db()

calendar_service = CalendarService()

@app.route("/")
def index():
    """Página principal: Réplica del Steam Personal Calendar."""
    steam_id = session.get("steam_id")
    api_key = get_active_steam_api_key()
    has_api_key = bool(api_key and len(api_key) == 32)
    user_info = session.get("user_info", {})
    return render_template(
        "index.html",
        steam_id=steam_id,
        user_info=user_info,
        has_api_key=has_api_key,
        current_api_key=api_key or ""
    )

@app.route("/auth/steam/login")
def steam_login():
    """Inicia el flujo de autenticación con Steam OpenID 2.0."""
    return_to = f"{settings.STEAM_REALM}/auth/steam/callback"
    login_url = build_steam_login_url(return_to)
    return redirect(login_url)

@app.route("/auth/steam/callback")
def steam_callback():
    """Maneja el retorno seguro desde Valve."""
    query_params = request.args.to_dict()
    steam_id = validate_steam_login(query_params)
    
    if steam_id:
        session["steam_id"] = steam_id
        
        # Sincronizar perfil y deseados del usuario
        client = SteamClient()
        user_summary = client.fetch_player_summary(steam_id)
        session["user_info"] = user_summary or {
            "personaname": f"Steam User ({steam_id[-4:]})",
            "avatar": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"
        }
        
        wishlist_ids = client.fetch_user_wishlist(steam_id)
        if wishlist_ids:
            save_user_wishlist(steam_id, wishlist_ids)
            
        library_games = client.fetch_user_library(steam_id)
        if library_games:
            save_user_library(steam_id, library_games)
            
    return redirect(url_for("index"))

@app.route("/auth/logout")
def logout():
    """Cierra la sesión del usuario."""
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/calendar")
def api_calendar():
    """API endpoint que devuelve la estructura completa día a día."""
    try:
        steam_id = session.get("steam_id") or request.args.get("steam_id")
        include_past = request.args.get("include_past", "0") in ["1", "true", "True"]
        data = calendar_service.get_personal_calendar(steam_id=steam_id, include_past=include_past)
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Error procesando calendario: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/calendar/sync", methods=["POST"])
def api_sync():
    """Fuerza la sincronización con los servidores de Steam actualizando la base de datos."""
    games = calendar_service.sync_upcoming_games(clear_first=False)
    steam_id = session.get("steam_id")
    if steam_id:
        client = SteamClient()
        wishlist_ids = client.fetch_user_wishlist(steam_id)
        if wishlist_ids:
            save_user_wishlist(steam_id, wishlist_ids)
        library_games = client.fetch_user_library(steam_id)
        if library_games:
            save_user_library(steam_id, library_games)
            
        owned_appids = [g["appid"] for g in library_games] if library_games else []
        all_user_appids = list(set((wishlist_ids or []) + owned_appids))
        if all_user_appids:
            user_games = client.fetch_wishlist_games_details(all_user_appids[:100])
            if user_games:
                save_games_batch(user_games)
    return jsonify({"success": True, "count": len(games)})

@app.route("/api/search")
def api_search():
    """Busca juegos en Steam mediante nombre o appid y los almacena en el calendario."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []})
    client = SteamClient()
    games = client.search_games(query)
    if games:
        save_games_batch(games)
    return jsonify({"results": games})

@app.route("/api/game/inspect")
def api_inspect_game():
    """Inspecciona dinámicamente cualquier juego de Steam (por AppID o URL) y obtiene su fecha exacta y categoría."""
    target = request.args.get("target") or request.args.get("url") or request.args.get("appid", "")
    target = target.strip()
    if not target:
        return jsonify({"error": "Parámetro 'target' requerido (URL o AppID)."}), 400
    client = SteamClient()
    info = client.get_game_release_info(target)
    if isinstance(info, dict) and info.get("appid"):
        try:
            save_game(info)
        except Exception:
            pass
    return jsonify(info)

@app.route("/api/calendar/export.ics")
def api_export_ics():
    """Genera el feed de suscripción a iCalendar (.ics)."""
    steam_id = session.get("steam_id") or request.args.get("steam_id")
    wishlist_only = request.args.get("wishlist_only", "0") in ["1", "true", "True"]
    library_only = request.args.get("library_only", "0") in ["1", "true", "True"]
    hide_unowned_dlc = request.args.get("hide_unowned_dlc", "0") in ["1", "true", "True"]
    hide_nsfw = request.args.get("hide_nsfw", "0") in ["1", "true", "True"]
    ics_content = calendar_service.export_ical_feed(
        steam_id=steam_id,
        wishlist_only=wishlist_only,
        library_only=library_only,
        hide_unowned_dlc=hide_unowned_dlc,
        hide_nsfw=hide_nsfw
    )
    
    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=steam_calendar.ics"}
    )

@app.route("/api/settings/api-key", methods=["POST"])
def api_save_key():
    """Permite configurar la API Key de Steam directamente desde la interfaz web."""
    data = request.get_json() or {}
    new_key = data.get("api_key", "").strip()
    
    if new_key and len(new_key) != 32:
        return jsonify({"success": False, "error": "La clave de Steam debe tener exactamente 32 caracteres."}), 400
        
    update_env_api_key(new_key)
    set_setting("STEAM_API_KEY", new_key)
    
    # Reinstanciar el servicio con la nueva clave
    global calendar_service
    calendar_service = CalendarService(api_key=new_key)
    
    return jsonify({"success": True, "has_key": bool(new_key)})

@app.route("/api/user/set-steamid", methods=["POST"])
def api_set_steamid():
    """Permite fijar manualmente el SteamID o Vanity URL sin pasar por OpenID."""
    data = request.get_json() or {}
    identifier = data.get("steam_id_or_url", "").strip()
    if not identifier:
        return jsonify({"success": False, "error": "Debes proporcionar un SteamID o URL personalizada."}), 400

    client = SteamClient()
    resolved_id = client.resolve_vanity_url(identifier)
    if not resolved_id:
        return jsonify({"success": False, "error": "No se pudo resolver el SteamID. Asegúrate de que el formato es correcto o de tener la API Key configurada."}), 400

    session["steam_id"] = resolved_id
    user_summary = client.fetch_player_summary(resolved_id)
    session["user_info"] = user_summary or {
        "personaname": f"Steam User ({resolved_id[-4:]})",
        "avatar": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"
    }

    wishlist_ids = client.fetch_user_wishlist(resolved_id)
    if wishlist_ids:
        save_user_wishlist(resolved_id, wishlist_ids)

    library_games = client.fetch_user_library(resolved_id)
    if library_games:
        save_user_library(resolved_id, library_games)

    return jsonify({"success": True, "steam_id": resolved_id, "wishlist_count": len(wishlist_ids)})

@app.route("/api/user/status")
def api_user_status():
    """Devuelve el estado actual de sesión y clave configurada."""
    steam_id = session.get("steam_id")
    user_info = session.get("user_info", {})
    api_key = get_active_steam_api_key()
    return jsonify({
        "is_authenticated": bool(steam_id),
        "steam_id": steam_id,
        "user_info": user_info,
        "has_api_key": bool(api_key and len(api_key) == 32)
    })
