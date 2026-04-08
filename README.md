# Eternia Online — Prototype MMORPG

J'ai transformé ce dépôt minimal en **prototype jouable** d'un mini-MMORPG en ligne de commande.

## Vision

Le "meilleur MMORPG" demande habituellement :

- Progression satisfaisante (XP, niveaux, stats)
- Monde avec zones débloquées selon le niveau
- Combats dynamiques avec récompenses
- Économie basique (or, consommables)
- Boucle de jeu claire et extensible

Ce prototype implémente déjà ces fondations pour évoluer ensuite vers une version réseau/multi-joueur.

## Lancer le jeu

```bash
python3 src/mmorpg.py
```

Puis commandes en jeu :

- `statut`
- `carte`
- `combat`
- `potion`
- `quitter`

## Lancer les tests

```bash
python3 -m pytest -q
```

## Idées de prochaines étapes

1. Serveur temps réel (WebSocket) + synchronisation d'état
2. Quêtes procédurales et événements mondiaux
3. Guildes, raids et économie entre joueurs
4. Persistance (PostgreSQL)
5. Client web ou desktop
