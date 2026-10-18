# PARTIE 7 — DÉPLOIEMENT & RELEASE

## 7.1 Versioning

- **Semantic Versioning** : MAJOR (breaking change) . MINOR (nouvelle fonctionnalité rétrocompatible) . PATCH (correctif rétrocompatible).
- Tag Git correspondant à chaque version livrée en production.

## 7.2 Stratégies de déploiement

| Stratégie | Downtime | Risque | Complexité |
|---|---|---|---|
| Recreate (arrêt puis redémarrage) | Oui | Faible risque technique, mais coupure | Faible |
| Rolling update | Non (ou minime) | Moyen | Moyenne |
| Blue-green | Non | Faible (bascule instantanée, rollback immédiat) | Moyenne/élevée |
| Canary | Non | Très faible (exposition progressive) | Élevée |

Le choix dépend de la criticité du service et de la maturité de l'infra disponible.

## 7.3 Release management

- **Changelog** tenu à jour (idéalement généré depuis les Conventional Commits) — format "Keep a Changelog" recommandé : Ajouté / Modifié / Corrigé / Supprimé.
- Fréquence de release : déploiement continu (plusieurs fois par jour) vs releases planifiées (hebdo/mensuel) selon la maturité des tests automatisés et le contexte métier.
- Code freeze avant une release critique si l'équipe n'a pas encore une CI/CD suffisamment fiable pour du déploiement continu serein.

## 7.4 Checklist go-live

- [ ] Sauvegardes récentes vérifiées et restaurables
- [ ] Monitoring et alerting actifs sur le nouvel environnement
- [ ] Plan de rollback testé et documenté
- [ ] Communication (interne/externe) préparée
- [ ] Fenêtre de déploiement choisie (éviter les pics de trafic connus)

## 7.5 Rollback strategy

- Toujours avoir un plan de retour arrière **testé**, pas seulement théorique.
- Les feature flags (Partie 4.8) offrent un rollback quasi instantané sans redéploiement pour les fonctionnalités concernées.

## 7.6 Communication de lancement

- Interne : équipe support informée des changements pour répondre aux utilisateurs.
- Externe : utilisateurs/clients informés selon l'ampleur du changement (release notes publiques, email, in-app).

## ✅ Checklist fin de Partie 7

- [ ] Version taguée selon SemVer
- [ ] Changelog à jour
- [ ] Checklist go-live validée intégralement
- [ ] Plan de rollback prêt et testé
- [ ] Communication de lancement envoyée

> **Retour à l'index :** [README.md](./README.md)
