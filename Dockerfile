# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=combined_ca \
    if [ -f /run/secrets/combined_ca ]; then export PIP_CERT=/run/secrets/combined_ca; fi; \
    pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 operador
COPY buscador/ ./buscador/
COPY panel/ ./panel/
COPY datos/ ./datos/
COPY --from=web /build/dist ./web/dist
RUN chmod -R a+rX /app
USER operador
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python", "-m", "panel.api", "--host", "0.0.0.0", "--port", "8000"]
