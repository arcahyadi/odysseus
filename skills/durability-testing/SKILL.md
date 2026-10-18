# skill: durability-testing

## triggers
- valider NF-04 (fiabilité), test de reprise après panne
- "teste la résilience", "vérifie la reprise"

## tools
- src/durable_execution/ (workflows SQLite, retry, saga)
- docker compose stop/start pour simuler des pannes

## procedure
1. Créer un workflow durable (ex: déploiement simulé en 3 étapes)
2. Exécuter l'étape 1, puis tuer le processus (simuler crash)
3. Redémarrer, vérifier que le workflow reprend à l'étape 2
4. Vérifier qu'aucune étape n'est exécutée deux fois
5. Tester le pattern saga : échec à l'étape 3 → compensation étapes 2 puis 1
6. Tester l'approbation humaine longue durée
7. Rapporter : taux de reprise, intégrité, idempotence

## success criteria
- Reprise exacte après kill -9 (même étape, pas de double exécution)
- Compensation en ordre inverse fonctionnelle
- Signal d'approbation survit 24h+
