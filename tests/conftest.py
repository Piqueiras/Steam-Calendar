import os
import pytest
from app.config import ENV_PATH

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Configura el entorno de test y garantiza que .env nunca sea alterado."""
    monkeypatch.setenv("TESTING", "1")
    
    env_content_before = None
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            env_content_before = f.read()

    yield

    # Verificación posterior: asegurar que el contenido de .env se mantuvo exactamente idéntico
    if ENV_PATH.exists() and env_content_before is not None:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            env_content_after = f.read()
        assert env_content_before == env_content_after, "El archivo .env fue modificado durante los tests!"
