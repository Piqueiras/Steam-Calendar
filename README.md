# App Steam Calendar

Una aplicación para expandir la funcionalidad del experimento de Steam Calendar.


## Funcionalidades principales

- Lista de lanzamientos recientes
- Revisar los juegos de EA que salen a la 1.0
- Reseñas de los juegos

### Al iniciar sesión
- Consultar juegos de tu lista de deseados
- Ver cuándo salen DLC para tus juegos

## Requisitos Previos e Instalación

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

## Configuración de la Steam Web API Key

La clave es **gratuita** y se obtiene en menos de 1 minuto:
1. Accede a la página oficial de Valve: **[https://steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)**.
2. Inicia sesión e introduce un *Domain Name*.
3. Confirma en la app y obtén la clave.

## Ejecución

Para iniciar el servidor local:

```powershell
.\.venv\bin\python.exe run.py
```