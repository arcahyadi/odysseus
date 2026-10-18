# AgentOS Sandbox — Isolated execution environment for projects
# Each project gets its own sandbox instance. No host filesystem access.
FROM python:3.12-slim

LABEL com.agentos.role=sandbox
LABEL com.agentos.description="AgentOS Sandbox — isolated project execution"

# Common tools for project execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl nodejs npm \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python packages commonly needed
RUN pip install --no-cache-dir \
    flask uvicorn fastapi pytest \
    requests httpx \
    matplotlib pandas \
    sqlalchemy

# Create sandbox user
RUN useradd -m -s /bin/bash sandbox
WORKDIR /home/sandbox/workspace

# Project workspace (INTERNAL volume, no host bind mount)
RUN mkdir -p /home/sandbox/workspace && chown -R sandbox:sandbox /home/sandbox/workspace

USER sandbox
ENV HOME=/home/sandbox

# Default: wait for commands via stdin
CMD ["sh", "-c", "echo 'Sandbox ready. Send commands via stdin.' && tail -f /dev/null"]
