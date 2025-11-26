FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=app.py

WORKDIR /app

# Dependencias de WeasyPrint (cairo, pango, pixbuf) y utilidades mínimas
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libharfbuzz0b \
    libfreetype6 \
    libffi-dev \
    shared-mime-info \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Directorios persistentes para base de datos y plantillas cargadas
RUN mkdir -p /app/data /app/uploaded_templates

# Gunicorn usa la factoría create_app()
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "3", "app:create_app()"]
