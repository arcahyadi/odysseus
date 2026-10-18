# Odysseus App — UI + API + provenance_memory + EventBus
# Se connecte au daemon OpenCode via HTTP REST (interne, non exposé)
# Architecture: opencode-daemon:9888 ← HTTP → odysseus-app:9889
FROM python:3.12-slim

LABEL com.agentos.role=odysseus-app
LABEL com.agentos.description="Odysseus AgentOS — UI HTMX + API FastAPI + provenance"

# ====================================================================
# System deps minimales
# ====================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ====================================================================
# Créer utilisateur non-root
# ====================================================================
RUN useradd -m -s /bin/bash odysseus
WORKDIR /app

# ====================================================================
# Installer les dépendances Python (layer cache)
# ====================================================================
COPY requirements.txt requirements-optional.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ -f requirements-optional.txt ]; then pip install --no-cache-dir -r requirements-optional.txt 2>/dev/null || true; fi

# ====================================================================
# Copier le code de l'application
# ====================================================================
COPY app.py pyproject.toml setup.py ./
COPY src/ /app/src/
COPY core/ /app/core/
COPY routes/ /app/routes/
COPY static/ /app/static/
COPY config/ /app/config/
COPY packages/ /app/packages/
COPY opencode.json /app/opencode.json

# ====================================================================
# Dossiers de données
# ====================================================================
RUN mkdir -p /app/data /app/logs && chown -R odysseus:odysseus /app

USER odysseus
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 9889

# Healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9889/', timeout=5).read(1)" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9889", "--log-level", "info"]
