# HexCRM - Propuestas

Aplicación Flask para gestionar clientes y propuestas, renderizar HTML a PDF con WeasyPrint y administrar plantillas reutilizables.

## Requisitos locales
- Python 3.11+
- `pip install -r requirements.txt`
- (Opcional) `python -m venv .venv && source .venv/bin/activate`

Variables de entorno principales (`.env`):
- `SECRET_KEY` (requerida)
- `DATABASE_URL` (por defecto `sqlite:///crm.db`)

## Uso local
```bash
export FLASK_APP=app.py
flask run  # o python app.py
```
Las tablas se crean al inicio. Accede a `http://localhost:5000`.

## Docker / VPS
```bash
cp .env.example .env   # ajusta SECRET_KEY y DATABASE_URL
docker-compose up --build -d
```
La app queda en `http://<host>:8000`. Los datos y plantillas subidas persisten en volúmenes `hexcrm_data` y `hexcrm_uploads`.

## Estructura
- `app.py`: factory Flask, rutas y DB.
- `models.py`: modelos `Client`, `Proposal`, `User`.
- `proposal_engine.py`: render Jinja de cuerpos.
- `templates/`: vistas Jinja (español).
- `static/`: estilos y JS (Quill).
- `uploaded_templates/`: plantillas HTML subidas (persistidas en volumen).

## Comandos útiles
- Ejecutar en modo desarrollo: `FLASK_ENV=development flask run`
- Instalar deps: `pip install -r requirements.txt`
- Linter/format no configurado; seguir PEP 8.

## TODO / pendientes
- Añadir suite de tests `pytest` con `app.test_client()` y DB en memoria.
- Ruta de salud (`/health`) para monitoreo en despliegue.
- Hardening de auth (bloqueo por intentos, CSRF tokens en formularios).
- Validaciones extra en formularios (longitud, formatos) y mensajes accesibles.
- Accesibilidad: etiquetas aria en toggle de menú móvil y campos clave.
- Caché de assets estáticos y headers de seguridad en Gunicorn/Reverse proxy.
