# Registre des Risques — Odysseus AgentOS

**Version :** 1.0
**Dernière mise à jour :** 2026-08-06
**Propriétaire :** Équipe Odysseus AgentOS
**Revue :** Trimestrielle

---

## Guide de lecture

| Niveau | Probabilité | Impact |
|--------|:----------:|:------:|
| **Élevé** | > 50% de chances sur 12 mois | Arrêt de service, perte de données, faille critique |
| **Moyen** | 10-50% de chances sur 12 mois | Dégradation de service, incident de sécurité modéré |
| **Faible** | < 10% de chances sur 12 mois | Impact mineur, contournement existant |

---

## Risques techniques

### R-01 : Panne de l'agentos-engine isolé

| Attribut | Valeur |
|----------|--------|
| **Description** | Le conteneur `agentos-engine` (OpenCode Engine isolé) s'arrête ou devient injoignable, rendant impossible toute exécution agent |
| **Probabilité** | Moyenne |
| **Impact** | Élevé — arrêt complet du service agent |
| **Détection** | Healthcheck Docker (`docker-compose.yml:healthcheck`), `opencode_bridge.py:health()` |
| **Mitigation** | 1. Fallback automatique vers le mode legacy dans `opencode_bridge.py:31-38` quand l'engine est injoignable<br>2. Healthcheck Docker avec `restart: unless-stopped`<br>3. Monitoring via ntfy alertes |
| **Kill-switch** | `AGENTOS_ENGINE_HOST=` (vide) → force le mode legacy |
| **Référence** | `docker-compose.yml:688-714`, `src/opencode_bridge.py:32-41` |

### R-02 : Prompt injection via contenu non fiable

| Attribut | Valeur |
|----------|--------|
| **Description** | Un contenu externe (page web scrapée, email, mémoire utilisateur) contient des instructions malveillantes qui modifient le comportement de l'agent |
| **Probabilité** | Élevée |
| **Impact** | Élevé — l'agent exécute des actions non autorisées ou divulgue des données |
| **Détection** | `src/prompt_security.py:untrusted_context_message()` |
| **Mitigation** | 1. Tous les contenus externes passent par `untrusted_context_message()` qui les wrappe en données, pas en instructions<br>2. Politique `UNTRUSTED_CONTEXT_POLICY` injectée dans le system prompt<br>3. Sandbox `agentos-sandbox` isole l'exécution de code<br>4. `ODYSSEUS_DESTRUCTIVE_GATE=on` bloque les opérations destructrices |
| **Kill-switch** | `ODYSSEUS_DESTRUCTIVE_GATE=on` (activé par défaut) |
| **Référence** | `THREAT_MODEL.md:54-61`, `src/prompt_security.py` |

### R-03 : Épuisement des tokens et dépassement de budget

| Attribut | Valeur |
|----------|--------|
| **Description** | Le pipeline 7 phases ou une boucle de correction consomme un nombre excessif de tokens, épuisant le budget LLM configuré |
| **Probabilité** | Moyenne |
| **Impact** | Élevé — coût financier, blocage du service |
| **Détection** | `src/budget_enforcer.py`, `src/trace_writer.py` (comptage unifié de tokens) |
| **Mitigation** | 1. Budgets obligatoires par projet (principe P4)<br>2. Limite de 3 itérations BUILD→QUALITY→AUTOEVAL<br>3. Compaction automatique du contexte<br>4. `ODYSSEUS_UNIFIED_TOKENS=on` active le comptage corrélé |
| **Kill-switch** | `ODYSSEUS_UNIFIED_TOKENS=off` (désactive le comptage) |
| **Référence** | `SF

D.md §5.9`, `src/budget_enforcer.py` |

### R-04 : Fuite de secrets dans les logs ou le code généré

| Attribut | Valeur |
|----------|--------|
| **Description** | L'agent génère du code contenant des secrets, ou les logs/traces exposent des clés API, tokens, mots de passe |
| **Probabilité** | Moyenne |
| **Impact** | Élevé — compromission de comptes, fuite de données |
| **Détection** | GitHub secret scanning (`.github/workflows/secret-scan.yml`), `SECURITY.md` |
| **Mitigation** | 1. `src/settings_scrub.py` nettoie les secrets des logs<br>2. `.gitignore` exclut `.env`, `data/`, `logs/`<br>3. Scan de secrets dans la CI (`secret-scan.yml`)<br>4. Guide dans `SECURITY.md:30-33` |
| **Kill-switch** | N/A (mesure de prévention permanente) |
| **Référence** | `SECURITY.md`, `.github/workflows/secret-scan.yml` |

---

## Risques humains

### R-05 : Bus factor critique sur les composants cœur

| Attribut | Valeur |
|----------|--------|
| **Description** | Un seul contributeur maîtrise un composant critique (ex. le bridge OpenCode, le Docker Compose, l'orchestrateur) ; son absence bloque toute évolution |
| **Probabilité** | Moyenne |
| **Impact** | Moyen — ralentissement majeur, incapacité à corriger des bugs critiques |
| **Détection** | Analyse du bus factor (`bus-factor.md`), revue des CODEOWNERS |
| **Mitigation** | 1. Documentation complète dans `docs/master-ref/`<br>2. CODEOWNERS à la racine du repo<br>3. Sessions de transfert de connaissances<br>4. Tests automatisés comme documentation vivante |
| **Kill-switch** | N/A |
| **Référence** | `bus-factor.md`, `CODEOWNERS` |

### R-06 : Erreur humaine lors de la configuration Docker

| Attribut | Valeur |
|----------|--------|
| **Description** | Un administrateur expose accidentellement un service interne (ChromaDB, SearXNG, Ollama) sur une interface publique sans authentification |
| **Probabilité** | Faible |
| **Impact** | Critique — accès non autorisé aux données, utilisation abusive des LLMs |
| **Détection** | Revue manuelle, scan de ports externes |
| **Mitigation** | 1. Tous les services Docker bindent sur `127.0.0.1` par défaut<br>2. `AUTH_ENABLED=true` activé par défaut<br>3. `ODYSSEUS_TRAEFIK=off` par défaut, activation explicite<br>4. Documentation dans `SECURITY.md:11-24`<br>5. gVisor pour les conteneurs MCP |
| **Kill-switch** | `ODYSSEUS_GVISOR_RUNTIME=runsc` |
| **Référence** | `SECURITY.md`, `docker-compose.yml` (bind 127.0.0.1 sur tous les services) |

---

## Risques business

### R-07 : Dépendance à OpenCode comme fournisseur unique

| Attribut | Valeur |
|----------|--------|
| **Description** | OpenCode Engine est le moteur unique d'exécution agent. Un changement de licence, une rupture de compatibilité, ou l'arrêt du projet rendrait Odysseus inutilisable |
| **Probabilité** | Faible |
| **Impact** | Critique — nécessiterait une réécriture complète du moteur agent |
| **Détection** | Veille active sur le dépôt OpenCode, tests d'intégration dans la CI |
| **Mitigation** | 1. Le bridge `opencode_bridge.py` est une couche d'abstraction mince (~70 lignes) — remplaçable<br>2. Le mode legacy sans OpenCode Engine reste fonctionnel<br>3. Les plugins npm `@agentos/sfd-*` sont auto-suffisants<br>4. Architecture documentée dans `docs/master-ref/03-ARCHITECTURE-MIGRATION.md` |
| **Kill-switch** | `AGENTOS_ENGINE_HOST=` (vide) → fallback legacy |
| **Référence** | `src/opencode_bridge.py`, `docs/master-ref/03-ARCHITECTURE-MIGRATION.md` |

### R-08 : Non-conformité réglementaire (RGPD, AI Act)

| Attribut | Valeur |
|----------|--------|
| **Description** | Le stockage de données personnelles dans la mémoire agent, les logs, ou les traces peut violer le RGPD. Les décisions automatisées peuvent tomber sous l'AI Act européen |
| **Probabilité** | Moyenne |
| **Impact** | Élevé — sanctions financières, obligation d'arrêt |
| **Détection** | Audit régulier, revue des catégories de données stockées |
| **Mitigation** | 1. Classification de rétention à 5 niveaux (`src/data_classification.py`)<br>2. Règles d'omission strictes : attributs protégés, données sensibles, données identifiables JAMAIS stockés (SF

D.md §5.7.3)<br>3. Droit à l'oubli : suppression unitaire/totale (SF

D.md UC-19)<br>4. Taggage de provenance `[stated]`/`[observed]`/`[inferred]` pour auditer l'origine des données<br>5. Self-hosted : contrôle total des données par l'utilisateur |
| **Kill-switch** | `ODYSSEUS_GOVERNANCE_ANCESTRY=off` (désactive le tracking) |
| **Référence** | `docs/master-ref/01-SFD-v3.1.md §5.7.3`, `src/data_classification.py`, `src/provenance_memory.py` |

---

## Risques externes

### R-09 : Défaillance d'un service Docker tiers

| Attribut | Valeur |
|----------|--------|
| **Description** | Un des 15 services Docker (SearXNG, ChromaDB, ntfy, Kroki, Serena, Scrapling, CBM, Graphify, LangFuse, n8n, OPA, Traefik, LocalAI, Qdrant, Meilisearch) devient indisponible ou incompatible |
| **Probabilité** | Élevée |
| **Impact** | Variable — de la dégradation mineure (Kroki hors service → pas de diagrammes) à l'arrêt complet (ChromaDB hors service → pas de RAG) |
| **Détection** | Healthchecks Docker, `src/service_health.py`, status cockpit |
| **Mitigation** | 1. Services optionnels via profils Docker (`profiles: [scrapling]`, `profiles: [observability]`, etc.)<br>2. Healthchecks avec `depends_on: condition: service_healthy`<br>3. Fallbacks : Qdrant comme alternative à ChromaDB (`ODYSSEUS_QDRANT=on`)<br>4. `restart: unless-stopped` sur tous les services |
| **Kill-switch** | Profils Docker : `docker compose --profile scrapling up` |
| **Référence** | `docker-compose.yml`, `README.md §Services` |

### R-10 : Attaque par déni de service sur le point d'entrée

| Attribut | Valeur |
|----------|--------|
| **Description** | Un attaquant inonde l'API Odysseus de requêtes, saturant les ressources et rendant le service indisponible |
| **Probabilité** | Faible |
| **Impact** | Élevé — indisponibilité du service |
| **Détection** | Rate limiting Traefik, monitoring ntfy |
| **Mitigation** | 1. Rate limiting intégré : `ratelimit.average=100`, `ratelimit.burst=50` dans Traefik (`docker-compose.yml:179-181`)<br>2. `src/rate_limiter.py` pour les endpoints sensibles<br>3. n8n workflows d'auto-défense (`ODYSSEUS_N8N=on`)<br>4. Ban IP via AdGuard dans `workflows/security-incident.yaml:81-91` |
| **Kill-switch** | Ban IP automatique après 3 incidents en 24h |
| **Référence** | `docker-compose.yml:179-181`, `workflows/security-incident.yaml`, `src/rate_limiter.py` |

---

## Matrice de criticité

| Risque | Probabilité | Impact | Criticité |
|--------|:----------:|:------:|:---------:|
| R-02 Prompt injection | Élevée | Élevé | **Critique** |
| R-09 Défaillance service tiers | Élevée | Variable | **Élevée** |
| R-03 Épuisement tokens | Moyenne | Élevé | **Élevée** |
| R-01 Panne engine isolé | Moyenne | Élevé | **Élevée** |
| R-04 Fuite de secrets | Moyenne | Élevé | **Élevée** |
| R-08 Non-conformité réglementaire | Moyenne | Élevé | **Élevée** |
| R-05 Bus factor | Moyenne | Moyen | **Moyenne** |
| R-07 Dépendance OpenCode | Faible | Critique | **Moyenne** |
| R-06 Erreur config Docker | Faible | Critique | **Moyenne** |
| R-10 DDoS | Faible | Élevé | **Faible** |

---

## Historique des révisions

| Date | Version | Changements |
|------|---------|-------------|
| 2026-08-06 | 1.0 | Création initiale — 10 risques identifiés |
