# skill: deploy-vps

## triggers
- demande de déploiement, mise en production
- "déploie", "deploy", "mets en prod", "go live"

## tools
- docker compose (profil production)
- Traefik + Let's Encrypt (déjà configuré dans docker-compose.yml)
- scripts/test-e2e.sh

## procedure
1. Vérifier la checklist go-live:
   - [ ] Tests 223/223 passent
   - [ ] Docker images à jour (docker compose build)
   - [ ] Sauvegardes configurées
   - [ ] Monitoring actif (health endpoint)
   - [ ] Plan de rollback prêt (docker compose down + up version précédente)
2. Tagger la version selon SemVer
3. Générer le changelog depuis les commits
4. docker compose --profile production up -d
5. Exécuter scripts/test-e2e.sh --skip-docker
6. Vérifier health endpoint
7. Notifier l'utilisateur

## constraints
- Jamais déployer sans tests verts
- Toujours avoir un plan de rollback
- Fenêtre de déploiement: éviter les pics de trafic
