# Consulta de prerregistros (apps#7). Se construye en clinica01.
FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --system --uid 10001 --no-create-home --home-dir /app consultas
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates templates
COPY static static

USER consultas
EXPOSE 8200
# --preload: la llave de sesión se crea una vez y la comparten los workers.
# Sin socket de control, que no cabe en un sistema de archivos de solo lectura
CMD ["gunicorn", "--bind", "127.0.0.1:8200", "--workers", "2", "--timeout", "30", "--preload", "--no-control-socket", "app:app"]
