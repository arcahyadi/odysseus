# PARTIE 1 — AVANT-PROJET (Discovery & Cadrage)

## 1.1 Analyse des besoins

- Identifier **le problème réel**, pas directement la solution — creuser le "pourquoi" avant le "comment" (technique des 5 pourquoi).
- Interviewer les parties prenantes et utilisateurs finaux (pas seulement le commanditaire).
- Formaliser des personas et premiers parcours utilisateurs si le produit a des utilisateurs finaux identifiables.
- Étudier la concurrence / l'existant (benchmark).
- Lister les contraintes non négociables : budget, délai, réglementaire (RGPD, accessibilité légale, secteur réglementé...).
- Livrable : **brief / document de cadrage initial**.

## 1.2 Étude de faisabilité

- Faisabilité **technique** : la stack envisagée peut-elle répondre au besoin ? Y a-t-il un risque technique majeur à valider tôt (POC) ?
- Faisabilité **financière** : budget disponible vs coût estimé, ROI attendu.
- Faisabilité **organisationnelle** : compétences disponibles en interne, besoin de recrutement/prestataire.
- Faisabilité **légale/réglementaire**.
- Arbitrage **build vs buy vs no-code/low-code** : ne pas coder ce qui existe déjà en solution mature, sauf avantage concurrentiel clair.

## 1.3 Choix méthodologique

| Méthodologie | Contexte idéal | Points forts | Limites |
|---|---|---|---|
| Waterfall / Cycle en V | Besoin très stable, contraintes réglementaires fortes (aérospatial, médical) | Prévisibilité, traçabilité | Rigide, feedback tardif |
| Scrum | Produit avec roadmap évolutive, équipe stable | Cadence régulière, cérémonies structurantes | Overhead si équipe très petite |
| Kanban | Flux de demandes continu (support, run) | Flexible, visualise le flux | Moins structurant pour un gros projet neuf |
| Scrumban | Entre les deux | Souplesse + cadence | Nécessite discipline d'équipe |
| SAFe / Agile à l'échelle | Grande organisation, plusieurs équipes | Coordination multi-équipes | Lourd, coûteux à mettre en place |
| Shape Up | Petites équipes autonomes, cycles fixes | Réduit le sur-cadrage ("bets" à 6 semaines) | Demande une maturité produit forte |

🧍 Solo/petit projet : un Kanban simple (To do / In progress / Done) suffit largement.
🏢 Grande équipe : Scrum ou SAFe selon le nombre d'équipes à coordonner.

## 1.4 Cadrage projet

- **Charte de projet** : objectifs, périmètre (ce qui est inclus / exclu explicitement), contraintes, critères de succès mesurables.
- **Matrice RACI** (Responsible, Accountable, Consulted, Informed) pour clarifier qui décide/fait/est consulté/est informé.
- **Roadmap macro** avec jalons (milestones) à haut niveau — pas un planning détaillé figé.

## 1.5 Analyse des risques initiale

- Identifier les risques : techniques, humains (dépendance à une personne), business, externes (fournisseur, réglementation).
- Matrice **probabilité × impact** pour prioriser.
- Plan de mitigation pour chaque risque majeur.
- Créer un **registre des risques** — à tenir à jour tout au long du projet, pas juste au début.

## 1.6 Estimation & budget

- Techniques : **Planning Poker**, **T-shirt sizing**, **Story points**, estimation à trois points (optimiste/pessimiste/probable).
- ⚠️ Une estimation initiale a une marge d'erreur énorme (cône d'incertitude) — la communiquer comme une fourchette, pas un chiffre figé.
- Budget prévisionnel : développement, infrastructure/hébergement, licences tierces, marge de contingence (15-20% généralement).

## ✅ Checklist fin de Partie 1

- [ ] Le problème à résoudre est formulé clairement (pas la solution)
- [ ] Charte de projet validée par les parties prenantes
- [ ] Méthodologie choisie et justifiée
- [ ] Registre des risques initial créé
- [ ] Budget et délai macro estimés avec marge

> **Retour à l'index :** [README.md](./README.md)
