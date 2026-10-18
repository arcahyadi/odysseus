# skill: multi-agent-orchestration

## triggers
- projet complexe avec > 15 outils ou > 3 domaines non liés
- l'utilisateur demande explicitement du multi-agent
- le décideur détecte un des 3 critères (contexte/parallélisation/spécialisation)

## tools
- src/multi_agent_decision/ (3-criteria scorer)
- src/orchestrator/multi_agent.py (pipeline existant)
- src/orchestrator/agent_dispatcher.py (12 agents disponibles)

## procedure
1. Évaluer la tâche avec MultiAgentDecisionEngine.evaluate()
2. Si mode == SINGLE → continuer en agent unique
3. Si mode == MULTI → décomposer par contexte (pas par métier)
4. Assigner les sous-agents via AgentDispatcher
5. Chaque sous-agent reçoit un contexte filtré
6. Collecter les résultats, mesurer le multiplicateur de tokens
7. Rapporter le ratio single vs multi-agent tokens

## constraints
- Ne jamais décomposer par métier (planifieur/testeur/relecteur)
- Toujours mesurer le surcoût réel (3-10x attendu)
- Sous-agents = contexte filtré, jamais le contexte brut complet
