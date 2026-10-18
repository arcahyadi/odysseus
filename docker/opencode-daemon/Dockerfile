# OpenCode Daemon — moteur LLM/sessions/agents/plugins exposé via REST
# Conteneur isolé, PAS de partage avec l'app Python.
# Architecture: opencode-daemon:9888 ← HTTP → odysseus-app:9889
FROM node:22-slim

LABEL com.agentos.role=opencode-daemon
LABEL com.agentos.description="OpenCode headless daemon — LLM routing, sessions, agents, tools, MCP, plugins"

# ====================================================================
# Installer OpenCode CLI (version pinned via npm)
# Le binaire sous Linux est `lildax` (pas `opencode`)
# ====================================================================
RUN npm install -g @opencode-ai/cli@1.18.9

# ====================================================================
# Créer utilisateur non-root
# ====================================================================
RUN useradd -m -s /bin/bash opencode
WORKDIR /home/opencode

# ====================================================================
# Entrypoint — lit le password depuis l'env, configure, démarre
# ====================================================================
COPY docker/opencode-daemon/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ====================================================================
# Config minimale pour le daemon (providers, agents, permissions)
# Copiée depuis le projet hôte pour que le daemon ait accès aux
# providers/agents définis dans opencode.json + .opencode/
# ====================================================================
COPY opencode.json /home/opencode/opencode.json
COPY .opencode/ /home/opencode/.opencode/
RUN chown -R opencode:opencode /home/opencode

# ====================================================================
# Volume pour les données persistantes (sessions, traces, db)
# ====================================================================
RUN mkdir -p /home/opencode/data && chown -R opencode:opencode /home/opencode/data
VOLUME /home/opencode/data

USER opencode
ENV HOME=/home/opencode
ENV OPENCODE_HOME=/home/opencode
ENV OPENCODE_DAEMON_PASSWORD=opencode

EXPOSE 9888

# Healthcheck: lit le password du fichier local state, appelle /api/health
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "const h=require('http'),f=require('fs');\
    const p=f.readFileSync('/home/opencode/.local/state/opencode/password','utf8').trim();\
    const o={hostname:'localhost',port:9888,path:'/api/health',auth:'opencode:'+p};\
    h.get(o,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>process.exit(d.includes('healthy')?0:1))}).on('error',e=>process.exit(1))"

ENTRYPOINT ["/entrypoint.sh"]
