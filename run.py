import os
import sys
from app.config import settings, get_active_steam_api_key
from app.db import init_db
from app.main import app

def main():
    print("=" * 65)
    print(" 🎮 STEAM PERSONAL CALENDAR - SERVIDOR LOCAL")
    print("=" * 65)
    
    # Inicializar base de datos SQLite
    init_db()
    print(f" [*] Base de datos SQLite: {settings.DB_PATH}")

    # Comprobar estado de la API Key
    api_key = get_active_steam_api_key()
    if api_key:
        print(f" [✓] Steam API Key detectada: {api_key[:6]}...{api_key[-4:]}")
    else:
        print(" [!] Steam API Key no configurada en .env.")
        print("     -> La app funcionará en 'Modo Público'.")
        print("     -> Puedes introducir tu clave en cualquier momento desde los Ajustes ⚙️")

    print(f" [*] URL de acceso: {settings.STEAM_REALM}")
    print("=" * 65)
    print(" Presiona Ctrl+C para detener el servidor.\n")

    app.run(host="127.0.0.1", port=8000, debug=False)

if __name__ == "__main__":
    main()
