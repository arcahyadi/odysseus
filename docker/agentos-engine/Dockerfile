# AgentOS Engine — Isolated OpenCode runtime (V1)
# This is NOT the user's OpenCode CLI. This is the SYSTEM's own engine.
#
# Stack: Python 3.14 (engine_server.py + src/opencode_engine.py pipeline)
#        + Node 22 (OpenCode CLI install for sandbox-style project dispatch)
FROM python:3.14-slim

LABEL com.agentos.role=engine
LABEL com.agentos.description="AgentOS OpenCode Engine — isolated pipeline runtime"

# ====================================================================
# System deps
# ====================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node 22 (for OpenCode CLI install — official NodeSource setup)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# OpenCode CLI (the system's own copy — for future real agent dispatch via subprocess)
RUN curl -fsSL https://opencode.ai/install | bash

# ====================================================================
# Create agentos user (not root)
# ====================================================================
RUN useradd -m -s /bin/bash agentos
WORKDIR /home/agentos

# ====================================================================
# Copy the REAL engine source — Python pipeline
# ====================================================================
COPY --chown=agentos:agentos opencode.json /home/agentos/opencode.json
COPY --chown=agentos:agentos .opencode/ /home/agentos/.opencode/
COPY --chown=agentos:agentos packages/ /home/agentos/packages/

# Python engine code — the whole src/ + core/ that opencode_engine needs
COPY --chown=agentos:agentos src/ /home/agentos/src/
COPY --chown=agentos:agentos core/ /home/agentos/core/
COPY --chown=agentos:agentos docker/agentos-engine/engine_server.py /home/agentos/server.py

# Empty __init__ if missing
RUN touch /home/agentos/src/__init__.py /home/agentos/core/__init__.py 2>/dev/null || true

# Python deps for the engine server + pipeline
RUN pip install --no-cache-dir \
    fastapi==0.139.2 \
    uvicorn==0.49.0 \
    httpx \
    pyyaml

# Local SFD eventbus package (only one with real TS impl)
# sfd-phase is a custom tool loaded via .opencode/tools/, not an npm plugin
RUN cd /home/agentos/packages/sfd-eventbus && npm install && npm link \
    && cd /home/agentos && npm link @agentos/sfd-eventbus || true

# ====================================================================
# Volumes (workspace + data traces + vault)
# ====================================================================
RUN mkdir -p /home/agentos/workspace \
    && mkdir -p /home/agentos/data/traces \
    && mkdir -p /home/agentos/obsidian-vault \
    && chown -R agentos:agentos /home/agentos/data /home/agentos/workspace /home/agentos/obsidian-vault

USER agentos
ENV HOME=/home/agentos
ENV PYTHONPATH=/home/agentos
ENV PYTHONUNBUFFERED=1

EXPOSE 7001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:7001/health', timeout=3); print('healthy')" || exit 1

CMD ["python", "/home/agentos/server.py"]
