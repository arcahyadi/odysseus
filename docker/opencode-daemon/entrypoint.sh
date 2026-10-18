#!/bin/sh
# OpenCode Daemon Entrypoint
# 1. Définit le mot de passe Basic Auth (via env ou défaut)
# 2. Démarre le serveur
set -e

PASSWORD="${OPENCODE_DAEMON_PASSWORD:-opencode}"
lildax service password "$PASSWORD"
exec lildax serve --port 9888 --hostname 0.0.0.0
