import sqlite3
import json
import time
from typing import Optional, List, Dict, Any
from app.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Inicializa el esquema de tablas en SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla de juegos y lanzamientos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            appid INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            raw_date_str TEXT,
            calendar_date TEXT,
            precision TEXT NOT NULL,
            display_badge TEXT,
            header_image TEXT,
            capsule_image TEXT,
            tags TEXT,
            price_str TEXT,
            is_free INTEGER DEFAULT 0,
            deck_status TEXT DEFAULT 'UNKNOWN',
            item_type TEXT DEFAULT 'GAME',
            parent_appid INTEGER DEFAULT NULL,
            release_category TEXT DEFAULT 'FIRST_RELEASE',
            is_early_access INTEGER DEFAULT 0,
            review_score_label TEXT DEFAULT NULL,
            review_percent INTEGER DEFAULT NULL,
            review_count INTEGER DEFAULT NULL,
            follower_count INTEGER DEFAULT 0,
            source TEXT DEFAULT 'POPULAR',
            updated_at INTEGER NOT NULL
        )
        """)

        # Migración segura de columnas si la tabla ya existía
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN item_type TEXT DEFAULT 'GAME'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN parent_appid INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN release_category TEXT DEFAULT 'FIRST_RELEASE'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN is_early_access INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN review_score_label TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN review_percent INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN review_count INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE games ADD COLUMN follower_count INTEGER DEFAULT 0")
        except Exception:
            pass

        # Backfill inicial seguro para categorización en datos existentes
        try:
            cursor.execute("UPDATE games SET release_category = 'DLC' WHERE item_type = 'DLC' OR parent_appid IS NOT NULL")
        except Exception:
            pass

        # Normalización de fechas difusas y placeholders de Valve (1 de enero para AÑO y 1 de dic para Q4)
        try:
            cursor.execute("""
                UPDATE games 
                SET calendar_date = NULL, 
                    precision = 'YEAR', 
                    display_badge = 'Año ' || substr(calendar_date, 1, 4),
                    raw_date_str = CASE 
                        WHEN raw_date_str = calendar_date OR raw_date_str IS NULL OR raw_date_str = '' 
                        THEN substr(calendar_date, 1, 4) 
                        ELSE raw_date_str 
                    END
                WHERE calendar_date LIKE '%-01-01' 
                  AND CAST(substr(calendar_date, 1, 4) AS INTEGER) >= 2026
                  AND (raw_date_str NOT LIKE '%1 de %' AND raw_date_str NOT LIKE '%01 de %' AND raw_date_str NOT LIKE '%jan 1%')
            """)
            cursor.execute("""
                UPDATE games 
                SET calendar_date = NULL, 
                    precision = 'QUARTER', 
                    display_badge = 'Q4 ' || substr(calendar_date, 1, 4),
                    raw_date_str = CASE 
                        WHEN raw_date_str = calendar_date OR raw_date_str IS NULL OR raw_date_str = '' 
                        THEN 'Q4 ' || substr(calendar_date, 1, 4) 
                        ELSE raw_date_str 
                    END
                WHERE calendar_date LIKE '%-12-01' 
                  AND CAST(substr(calendar_date, 1, 4) AS INTEGER) >= 2026
                  AND (raw_date_str NOT LIKE '%1 de %' AND raw_date_str NOT LIKE '%01 de %' AND raw_date_str NOT LIKE '%dec 1%' AND raw_date_str NOT LIKE '%dic 1%')
            """)
            cursor.execute("""
                UPDATE games 
                SET calendar_date = NULL, 
                    precision = 'QUARTER', 
                    display_badge = 'Q1 ' || substr(calendar_date, 1, 4)
                WHERE calendar_date LIKE '%-03-01' 
                  AND CAST(substr(calendar_date, 1, 4) AS INTEGER) >= 2026
                  AND (raw_date_str = calendar_date OR raw_date_str LIKE '%trimestre%' OR raw_date_str LIKE '%q1%')
            """)
            cursor.execute("""
                UPDATE games 
                SET calendar_date = NULL, 
                    precision = 'QUARTER', 
                    display_badge = 'Q2 ' || substr(calendar_date, 1, 4)
                WHERE calendar_date LIKE '%-06-01' 
                  AND CAST(substr(calendar_date, 1, 4) AS INTEGER) >= 2026
                  AND (raw_date_str = calendar_date OR raw_date_str LIKE '%trimestre%' OR raw_date_str LIKE '%q2%')
            """)
            cursor.execute("""
                UPDATE games 
                SET calendar_date = NULL, 
                    precision = 'QUARTER', 
                    display_badge = 'Q3 ' || substr(calendar_date, 1, 4)
                WHERE calendar_date LIKE '%-09-01' 
                  AND CAST(substr(calendar_date, 1, 4) AS INTEGER) >= 2026
                  AND (raw_date_str = calendar_date OR raw_date_str LIKE '%trimestre%' OR raw_date_str LIKE '%q3%')
            """)
        except Exception:
            pass
        
        # Tabla de lista de deseados de usuarios
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_wishlist (
            steam_id TEXT NOT NULL,
            appid INTEGER NOT NULL,
            priority INTEGER DEFAULT 0,
            date_added INTEGER DEFAULT 0,
            PRIMARY KEY (steam_id, appid)
        )
        """)
        
        # Tabla de biblioteca de usuarios (juegos comprados y horas)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_library (
            steam_id TEXT NOT NULL,
            appid INTEGER NOT NULL,
            name TEXT NOT NULL,
            playtime_forever INTEGER DEFAULT 0,
            PRIMARY KEY (steam_id, appid)
        )
        """)
        
        # Tabla de configuración y metadatos del sistema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """)

        # Tabla de diccionario oficial de etiquetas de Steam (TagID -> Nombre)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS steam_tags (
            tagid INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """)
        
        # Índices para consultas rápidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_calendar_date ON games (calendar_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_precision ON games (precision)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_follower_count ON games (follower_count)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_steam_id ON user_wishlist (steam_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_library_steam_id ON user_library (steam_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steam_tags_name ON steam_tags (name)")
        
        conn.commit()

def save_game(game_data: Dict[str, Any]) -> None:
    """Inserta o actualiza un juego en la base de datos."""
    tags_json = json.dumps(game_data.get("tags", [])) if isinstance(game_data.get("tags"), list) else game_data.get("tags", "[]")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO games (
            appid, name, raw_date_str, calendar_date, precision, display_badge,
            header_image, capsule_image, tags, price_str, is_free, deck_status, item_type, parent_appid,
            release_category, is_early_access, review_score_label, review_percent, review_count,
            follower_count, source, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(appid) DO UPDATE SET
            name=excluded.name,
            raw_date_str=excluded.raw_date_str,
            calendar_date=excluded.calendar_date,
            precision=excluded.precision,
            display_badge=excluded.display_badge,
            header_image=excluded.header_image,
            capsule_image=excluded.capsule_image,
            tags=excluded.tags,
            price_str=excluded.price_str,
            is_free=excluded.is_free,
            deck_status=excluded.deck_status,
            item_type=excluded.item_type,
            parent_appid=excluded.parent_appid,
            release_category=excluded.release_category,
            is_early_access=excluded.is_early_access,
            review_score_label=excluded.review_score_label,
            review_percent=excluded.review_percent,
            review_count=excluded.review_count,
            follower_count=CASE WHEN excluded.follower_count > 0 THEN excluded.follower_count ELSE games.follower_count END,
            source=excluded.source,
            updated_at=excluded.updated_at
        """, (
            game_data["appid"],
            game_data["name"],
            game_data.get("raw_date_str", ""),
            game_data.get("calendar_date"),
            game_data.get("precision", "TBA"),
            game_data.get("display_badge", ""),
            game_data.get("header_image", ""),
            game_data.get("capsule_image", ""),
            tags_json,
            game_data.get("price_str", ""),
            1 if game_data.get("is_free") else 0,
            game_data.get("deck_status", "UNKNOWN"),
            game_data.get("item_type", "GAME"),
            game_data.get("parent_appid"),
            game_data.get("release_category", "FIRST_RELEASE"),
            1 if game_data.get("is_early_access") else 0,
            game_data.get("review_score_label"),
            game_data.get("review_percent"),
            game_data.get("review_count"),
            game_data.get("follower_count", 0),
            game_data.get("source", "POPULAR"),
            int(time.time())
        ))
        conn.commit()

def save_games_batch(games_list: List[Dict[str, Any]]) -> None:
    """Inserta o actualiza una lista de juegos en una sola transacción."""
    now = int(time.time())
    with get_connection() as conn:
        cursor = conn.cursor()
        for g in games_list:
            tags_json = json.dumps(g.get("tags", [])) if isinstance(g.get("tags"), list) else g.get("tags", "[]")
            cursor.execute("""
            INSERT INTO games (
                appid, name, raw_date_str, calendar_date, precision, display_badge,
                header_image, capsule_image, tags, price_str, is_free, deck_status, item_type, parent_appid,
                release_category, is_early_access, review_score_label, review_percent, review_count,
                follower_count, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(appid) DO UPDATE SET
                name=excluded.name,
                raw_date_str=excluded.raw_date_str,
                calendar_date=excluded.calendar_date,
                precision=excluded.precision,
                display_badge=excluded.display_badge,
                header_image=excluded.header_image,
                capsule_image=excluded.capsule_image,
                tags=excluded.tags,
                price_str=excluded.price_str,
                is_free=excluded.is_free,
                deck_status=excluded.deck_status,
                item_type=excluded.item_type,
                parent_appid=excluded.parent_appid,
                release_category=excluded.release_category,
                is_early_access=excluded.is_early_access,
                review_score_label=excluded.review_score_label,
                review_percent=excluded.review_percent,
                review_count=excluded.review_count,
                follower_count=CASE WHEN excluded.follower_count > 0 THEN excluded.follower_count ELSE games.follower_count END,
                source=excluded.source,
                updated_at=excluded.updated_at
            """, (
                g["appid"],
                g["name"],
                g.get("raw_date_str", ""),
                g.get("calendar_date"),
                g.get("precision", "TBA"),
                g.get("display_badge", ""),
                g.get("header_image", ""),
                g.get("capsule_image", ""),
                tags_json,
                g.get("price_str", ""),
                1 if g.get("is_free") else 0,
                g.get("deck_status", "UNKNOWN"),
                g.get("item_type", "GAME"),
                g.get("parent_appid"),
                g.get("release_category", "FIRST_RELEASE"),
                1 if g.get("is_early_access") else 0,
                g.get("review_score_label"),
                g.get("review_percent"),
                g.get("review_count"),
                g.get("follower_count", 0),
                g.get("source", "POPULAR"),
                now
            ))
        conn.commit()

def clear_sample_data() -> None:
    """Elimina cualquier juego de muestra antiguo de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM games WHERE source = 'SAMPLE_DATA'")
        conn.commit()

def clear_all_games() -> None:
    """Limpia todos los juegos cacheados para forzar una sincronización limpia."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM games")
        conn.commit()

def get_cached_games() -> List[Dict[str, Any]]:
    """Devuelve todos los juegos cacheados."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games ORDER BY calendar_date ASC, name ASC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["tags"] = json.loads(d.get("tags") or "[]")
            except Exception:
                d["tags"] = []
            result.append(d)
        return result

def save_user_wishlist(steam_id: str, appids: List[int]) -> None:
    """Guarda la lista de deseados de un usuario."""
    now = int(time.time())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_wishlist WHERE steam_id = ?", (steam_id,))
        for idx, appid in enumerate(appids):
            cursor.execute("""
            INSERT OR REPLACE INTO user_wishlist (steam_id, appid, priority, date_added)
            VALUES (?, ?, ?, ?)
            """, (steam_id, appid, idx, now))
        conn.commit()

def get_user_wishlist_appids(steam_id: str) -> List[int]:
    """Obtiene los appids de la wishlist del usuario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT appid FROM user_wishlist WHERE steam_id = ? ORDER BY priority ASC", (steam_id,))
        return [row["appid"] for row in cursor.fetchall()]

def save_user_library(steam_id: str, games: List[Dict[str, Any]]) -> None:
    """Guarda los juegos de la biblioteca de un usuario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_library WHERE steam_id = ?", (steam_id,))
        for g in games:
            cursor.execute("""
            INSERT OR REPLACE INTO user_library (steam_id, appid, name, playtime_forever)
            VALUES (?, ?, ?, ?)
            """, (steam_id, g["appid"], g.get("name", ""), g.get("playtime_forever", 0)))
        conn.commit()

def get_user_library_games(steam_id: str) -> List[Dict[str, Any]]:
    """Obtiene los juegos poseídos y horas jugadas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_library WHERE steam_id = ? ORDER BY playtime_forever DESC", (steam_id,))
        return [dict(r) for r in cursor.fetchall()]

def set_setting(key: str, value: str) -> None:
    """Guarda un ajuste en la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, value, int(time.time())))
        conn.commit()

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Obtiene un ajuste de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

def save_steam_tags(tags_map: Dict[int, str]) -> None:
    """Guarda o actualiza el diccionario de etiquetas oficiales de Steam en español."""
    if not tags_map:
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR REPLACE INTO steam_tags (tagid, name) VALUES (?, ?)",
            list(tags_map.items())
        )
        conn.commit()

def get_steam_tags_map() -> Dict[int, str]:
    """Obtiene el mapeo completo de ID de tag a nombre en español."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tagid, name FROM steam_tags")
        return {row["tagid"]: row["name"] for row in cursor.fetchall()}

def update_game_followers_batch(updates: Dict[int, int]) -> None:
    """Actualiza el número de seguidores de un conjunto de juegos."""
    if not updates:
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "UPDATE games SET follower_count = ? WHERE appid = ?",
            [(cnt, aid) for aid, cnt in updates.items()]
        )
        conn.commit()
