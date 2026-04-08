# Eternia Online — Prototype MMORPG 3D + serveur massivement multijoueur

J'ai fait évoluer le dépôt en **prototype MMORPG extensible** avec :

- Un noyau RPG (progression, classes, factions, zones, combat, loot)
- Un **serveur temps réel TCP** JSON prêt à connecter à un client 3D (Unity/Godot/Unreal)
- Gestion multi-joueurs : connexion, déplacement 3D, proximité, chat local, combat
- **Sharding automatique** (simulation massif): attribution des joueurs sur plusieurs shards
- Téléportation inter-régions et état global du monde pour dashboard live

> Objectif: fournir une base technique solide pour aller vers un "vrai" MMORPG à grande échelle.

## Fonctionnalités implémentées

### Monde RPG
- Progression XP/niveaux
- Statistiques de classe
- Zones débloquées par niveau
- Système de combat et économie (or + potions)

### Serveur temps réel
- Action `join` pour enregistrer un joueur
- Action `move` pour déplacer un joueur dans un espace 3D
- Action `nearby` pour récupérer les joueurs visibles à proximité
- Action `say` + `chat_pull` pour le chat local de zone
- Action `fight` pour déclencher un combat PvE côté serveur
- Action `teleport` pour changer de région (si niveau suffisant)
- Action `world_state` pour obtenir l'état massif du serveur (online, shards, top joueurs, régions)

## Lancer en mode solo CLI

```bash
python3 src/mmorpg.py
```

Choisir `solo` puis jouer avec:
- `statut`
- `carte`
- `combat`
- `potion`
- `quitter`

## Lancer le serveur MMO

```bash
python3 src/mmorpg.py
```

Choisir `server`, puis host/port (défaut: `127.0.0.1:7777`).

Le protocole est **JSON line-based**:

```json
{"action":"join","name":"Alice","faction":"Aube de Fer","class":"Guerrier"}
{"action":"move","name":"Alice","dx":3,"dy":0,"dz":1}
{"action":"nearby","name":"Alice","radius":120}
{"action":"say","name":"Alice","message":"Bonjour le monde"}
{"action":"chat_pull","name":"Alice"}
{"action":"fight","name":"Alice"}
{"action":"teleport","name":"Alice","region":"Ruines d'Obsidienne"}
{"action":"world_state"}
```

Réponse serveur:
- `{ "ok": true, "event": ... }`
- ou `{ "ok": false, "error": "..." }`

## Tests

```bash
python3 -m pytest -q
```

## Prochaines étapes AAA

1. Gateway WebSocket + sharding horizontal
2. Tick serveur autoritatif + anti-cheat
3. Snapshot delta-compressed + interpolation client
4. Persistance PostgreSQL + Redis + event sourcing
5. Matchmaking, guildes, raids, économie joueur-joueur
6. Client 3D complet avec inventaire, compétences, quêtes et streaming monde
