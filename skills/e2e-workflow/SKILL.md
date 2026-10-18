# skill: e2e-workflow

## triggers
- "lance tous les tests", "test complet", "vérifie tout"
- avant release, après changement majeur
- workflow CI/CD automatique

## tools
- scripts/test-e2e.sh
- python -m pytest tests/ -q
- docker compose ps
- curl /api/health

## procedure
### Phase 1: Infrastructure
1. Vérifier Docker: docker compose ps (tous les services UP?)
2. Si non: docker compose --profile default up -d
3. Attendre health endpoint: curl /api/health → 200

### Phase 2: Tests unitaires
4. python -m pytest tests/test_thought_bus.py -q
5. python -m pytest tests/test_durable_execution.py -q
6. python -m pytest tests/test_memory_provenance.py -q
7. python -m pytest tests/test_preferences.py -q
8. python -m pytest tests/test_visual_output.py -q
9. python -m pytest tests/test_modules_6_5_6_7.py -q
10. python -m pytest tests/test_sfd_100.py -q
11. python -m pytest tests/test_integration_full.py -q
12. python -m pytest tests/test_ui_pipeline.py -q
13. python -m pytest tests/test_mode_detector.py -q
14. python -m pytest tests/test_agent_instructions.py -q
15. python -m pytest tests/test_sfd_wiring.py -q

### Phase 3: HTTP endpoints
16. curl /api/health → 200, status=healthy
17. curl /api/version → 200
18. curl / → contient cockpit-phase-bar

### Phase 4: SFD compliance
19. Vérifier 22/22 principes (audit)
20. Vérifier 20/20 modules actifs
21. Vérifier kill-switches (cœur ON)

### Phase 5: Live agent test
22. Envoyer un message test au LLM
23. Vérifier que le mode agent détecte le type
24. Vérifier que les outils sont disponibles
25. Vérifier que la mémoire est utilisée

### Phase 6: Rapport
26. Générer un rapport JSON avec tous les résultats
27. Si tout passe → GO pour déploiement
28. Si échec → lister les failures avec suggestions

## success criteria
- 223/223 tests passent
- Tous les endpoints HTTP 200
- Kill-switches cœur ON
- Agent répond en live
- Rapport généré
