# Steam Personal Calendar 🎮

Una aplicación web moderna en Python que replica el **Steam Personal Calendar** (la función de seguimiento de lanzamientos día a día graduada recientemente de **Steam Labs - Experimento 16**).

Permite visualizar cronológicamente los próximos lanzamientos de juegos organizados día por día, integrando tu **Lista de Deseados (Wishlist)**, avisos de **DLCs para juegos que ya posees en tu biblioteca**, compatibilidad con **Steam Deck** y suscripción viva a calendarios externos mediante **iCalendar (.ics)**.

---

## ✨ Características Principales

1. **Línea Temporal Día a Día (Horizonte Rodante)**:
   - Visualización cronológica organizada por días específicos (*Hoy*, *Mañana*, *Lunes 17 de Noviembre*...).
   - Tarjetas completas con carátula de alta resolución, precio estimado, tags y enlaces directos a la tienda de Steam.

2. **Personalización Automática**:
   - **Insignia `[⭐ EN TU WISHLIST]`**: Resalta en verde brillante los juegos que tienes guardados en tu lista de seguimiento.
   - **Insignia `[📦 DLC DE TU BIBLIOTECA]`**: Te avisa si el lanzamiento es una expansión o contenido descargable para un juego base que ya compraste.
   - **Insignia `[🎮 Deck]`**: Muestra si el juego está Verificado o es Jugable en Steam Deck.

3. **Bandeja de Fechas Difusas (Q1, Mes, TBA)**:
   - Los títulos que aún no han fijado su día exacto (fechados como *"Q1 2027"*, *"Noviembre 2026"* o *"Coming Soon"*) se colocan en una bandeja lateral inteligente para no distorsionar la cuadrícula de días confirmados.

4. **Suscripción Externa iCal (`.ics`)**:
   - Generación de feeds RFC 5545 para suscribirte al calendario desde **Google Calendar**, **Apple Calendar** u **Outlook**, con recordatorios el día de cada estreno.

5. **Seguridad y Privacidad Absoluta**:
   - Autenticación oficial **Steam OpenID 2.0**: tus credenciales nunca pasan por la aplicación; el inicio de sesión se realiza en los servidores de Valve (`steamcommunity.com`).
   - El archivo `.gitignore` protege estrictamente tu clave `.env` y las bases de datos locales.

---

## 🚀 Requisitos Previos e Instalación

El proyecto utiliza Python 3.12 y un entorno virtual `.venv`.

### 1. Clonar y preparar entorno
```powershell
# Crear entorno virtual si aún no existe
python -m venv .venv

# Activar entorno virtual
.\.venv\bin\activate

# Instalar dependencias
.\.venv\bin\pip.exe install -r requirements.txt
```

---

## 🔑 Configuración de la Steam Web API Key

La clave es **gratuita** y se obtiene en menos de 1 minuto:
1. Accede a la página oficial de Valve: **[https://steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)**.
2. Inicia sesión e introduce `localhost` en el campo *Domain Name*.
3. Copia tu clave de 32 caracteres.

### Formas de introducir la clave:

* **Método 1 (Vía archivo `.env`)**:
  Abre el archivo `.env` en la raíz del proyecto y añade tu clave:
  ```env
  STEAM_API_KEY=A1B2C3D4E5F678901234567890ABCDEF
  ```
  *(El archivo `.gitignore` ya está configurado para que `.env` jamás se suba a ningún repositorio).*

* **Método 2 (Desde la Interfaz Web)**:
  Arranca la aplicación, pulsa el botón amarillo superior **"Configurar API Key"** y pégala en el modal emergente. La aplicación la guardará en tu `.env` de forma automática.

> **Nota:** Si no introduces ninguna clave, la aplicación funcionará igualmente en **Modo Público**, mostrando el catálogo de lanzamientos más populares de Steam.

---

## 💻 Ejecución

Para iniciar el servidor local:

```powershell
.\.venv\bin\python.exe run.py
```

Abre tu navegador en:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite completa de pruebas unitarias que cubren el normalizador de fechas de Steam, la autenticación OpenID, el generador iCalendar y las rutas de la API:

```powershell
.\.venv\bin\python.exe -m pytest -v
```

---

## 📁 Estructura del Código

```text
├── app/
│   ├── auth.py             # Flujo criptográfico Steam OpenID 2.0
│   ├── calendar_service.py # Lógica de fechas, correlación de Wishlist y generación iCal
│   ├── config.py           # Gestión segura de entorno y API Key
│   ├── date_parser.py      # Normalizador de los 5 tipos de fechas de Steam
│   ├── db.py               # Persistencia y caché SQLite
│   ├── main.py             # Servidor Flask y endpoints REST
│   └── steam_client.py     # Cliente HTTP hacia la API de Steamworks y Storefront
├── static/
│   ├── css/steam_theme.css # Estilos con paleta oficial de Steam
│   └── js/calendar_app.js  # Lógica reactiva y filtros interactivos
├── templates/
│   ├── base.html           # Barra de navegación y perfil
│   └── index.html          # Vista de línea temporal rodante día a día
├── tests/                  # Pruebas unitarias con pytest
├── .env.example            # Plantilla pública de variables de entorno
├── .gitignore              # Protección estricta de secretos
├── requirements.txt        # Dependencias de Python
└── run.py                  # Script de inicio
```
