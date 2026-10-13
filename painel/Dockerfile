FROM python:3.13.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 calendar \
    && useradd --uid 10001 --gid calendar --create-home calendar

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY calendar_app/ ./calendar_app/
COPY dist/ ./dist/
COPY legacy/dist/ ./legacy/dist/
COPY docs/catalogo-salas-preliminar.json docs/classificacao-costa-sauipe-2026-10-08.json docs/classificacao-rio-quente-2026-10-08.json ./docs/
COPY docker/run.py ./docker/run.py

RUN mkdir -p /app/instance && chown -R calendar:calendar /app/instance
USER calendar

EXPOSE 4174
CMD ["python", "docker/run.py", "serve"]
