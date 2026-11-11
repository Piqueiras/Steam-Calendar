import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Cargar variables de entorno desde .env si existe
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

class Settings:
    @property
    def STEAM_API_KEY(self) -> str:
        return os.getenv("STEAM_API_KEY", "").strip()

    @property
    def STEAM_REALM(self) -> str:
        return os.getenv("STEAM_REALM", "http://localhost:8000").rstrip("/")

    @property
    def SECRET_KEY(self) -> str:
        return os.getenv("SECRET_KEY", "steam_calendar_super_secret_key_12345")

    @property
    def CACHE_TTL_HOURS(self) -> int:
        try:
            return int(os.getenv("CACHE_TTL_HOURS", "6"))
        except ValueError:
            return 6

    @property
    def DB_PATH(self) -> str:
        return str(BASE_DIR / "steam_calendar.db")

settings = Settings()

def get_active_steam_api_key() -> str:
    """Devuelve la clave API activa si está configurada."""
    return settings.STEAM_API_KEY

def update_env_api_key(new_key: str) -> None:
    """Actualiza la clave en el archivo .env y en el entorno en tiempo de ejecución.
    Si se está ejecutando en un entorno de pruebas (pytest o TESTING=1), no toca el archivo .env en disco.
    """
    cleaned_key = new_key.strip()
    os.environ["STEAM_API_KEY"] = cleaned_key

    # Protección: nunca modificar el archivo .env físico durante la ejecución de pruebas
    if (
        os.getenv("TESTING") == "1"
        or "pytest" in sys.modules
        or os.environ.get("PYTEST_CURRENT_TEST")
    ):
        return

    lines = []
    found = False
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("STEAM_API_KEY="):
                    lines.append(f"STEAM_API_KEY={cleaned_key}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"STEAM_API_KEY={cleaned_key}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
