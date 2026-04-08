from __future__ import annotations

import json
import socketserver
import threading
from dataclasses import dataclass, field
from random import Random
from typing import Dict, List, Tuple


FACTIONS = ["Aube de Fer", "Conclave Astral", "Horde Émeraude"]
CLASSES = ["Guerrier", "Mage", "Rôdeur", "Clerc"]


@dataclass
class Enemy:
    name: str
    level: int
    hp: int
    attack: int
    xp_reward: int


@dataclass
class Region:
    name: str
    min_level: int
    enemies: List[Enemy]


@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def clamp(self, min_value: float, max_value: float) -> "Vec3":
        return Vec3(
            x=max(min_value, min(max_value, self.x)),
            y=max(min_value, min(max_value, self.y)),
            z=max(min_value, min(max_value, self.z)),
        )


@dataclass
class Player:
    name: str
    faction: str
    klass: str
    level: int = 1
    xp: int = 0
    hp: int = 100
    max_hp: int = 100
    attack: int = 12
    gold: int = 0
    inventory: Dict[str, int] = field(default_factory=lambda: {"Potion": 2})

    def xp_for_next_level(self) -> int:
        return 100 + (self.level - 1) * 60

    def add_xp(self, amount: int) -> List[str]:
        messages = [f"+{amount} XP"]
        self.xp += amount
        while self.xp >= self.xp_for_next_level():
            self.xp -= self.xp_for_next_level()
            self.level += 1
            self.max_hp += 20
            self.hp = self.max_hp
            self.attack += 4
            messages.append(
                f"Niveau {self.level} atteint ! HP {self.max_hp}, Attaque {self.attack}"
            )
        return messages

    def heal(self, amount: int) -> str:
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return f"Soin: {old} -> {self.hp}"

    def use_potion(self) -> str:
        if self.inventory.get("Potion", 0) <= 0:
            return "Aucune potion disponible."
        self.inventory["Potion"] -= 1
        return self.heal(40)


@dataclass
class ConnectedPlayerState:
    player: Player
    position: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    velocity: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    nearby_chat: List[str] = field(default_factory=list)
    shard_id: int = 0
    region_name: str = "Plaine des Novices"
    guild: str | None = None
    resources: Dict[str, int] = field(default_factory=dict)


class World:
    """Noyau MMORPG: progression, zones, combat et économie."""

    def __init__(self, seed: int | None = None):
        self.rng = Random(seed)
        self.generated_chunks: Dict[Tuple[int, int], Dict[str, object]] = {}
        self.regions = [
            Region(
                "Plaine des Novices",
                1,
                [
                    Enemy("Loup famélique", 1, 24, 6, 28),
                    Enemy("Bandit errant", 2, 32, 7, 35),
                ],
            ),
            Region(
                "Ruines d'Obsidienne",
                4,
                [
                    Enemy("Golem fissuré", 4, 60, 11, 62),
                    Enemy("Nécromancien", 5, 72, 13, 80),
                ],
            ),
            Region(
                "Faille Céleste",
                8,
                [
                    Enemy("Drake d'orage", 8, 120, 18, 150),
                    Enemy("Arbitre du Néant", 10, 150, 24, 220),
                ],
            ),
        ]
        self.biomes = ["forêt", "désert", "toundra", "marais", "ruines"]
        self.resource_table = {
            "forêt": ["Bois ancien", "Sève arcanique"],
            "désert": ["Cristal solaire", "Sable runique"],
            "toundra": ["Givre vivant", "Minerai polaire"],
            "marais": ["Champignon abyssal", "Fibres de liane"],
            "ruines": ["Fragment antique", "Noyau d'obsidienne"],
        }
        self.recipes = {
            "Lame astrale": {
                "requires": {"Fragment antique": 2, "Noyau d'obsidienne": 1},
                "bonus_attack": 6,
                "bonus_hp": 0,
            },
            "Armure des titans": {
                "requires": {"Minerai polaire": 2, "Bois ancien": 2},
                "bonus_attack": 0,
                "bonus_hp": 35,
            },
        }

    def create_player(self, name: str, faction: str, klass: str) -> Player:
        if faction not in FACTIONS:
            raise ValueError("Faction inconnue")
        if klass not in CLASSES:
            raise ValueError("Classe inconnue")

        base_attack = {
            "Guerrier": 14,
            "Mage": 16,
            "Rôdeur": 13,
            "Clerc": 10,
        }[klass]
        base_hp = {
            "Guerrier": 130,
            "Mage": 90,
            "Rôdeur": 105,
            "Clerc": 115,
        }[klass]

        return Player(
            name=name,
            faction=faction,
            klass=klass,
            attack=base_attack,
            hp=base_hp,
            max_hp=base_hp,
        )

    def available_regions(self, player: Player) -> List[Region]:
        return [region for region in self.regions if player.level >= region.min_level]

    def run_combat(self, player: Player, enemy: Enemy) -> List[str]:
        log = [f"Combat: {player.name} vs {enemy.name} (niv {enemy.level})"]
        enemy_hp = enemy.hp

        while player.hp > 0 and enemy_hp > 0:
            damage = max(1, player.attack + self.rng.randint(-2, 4))
            enemy_hp -= damage
            log.append(f"{player.name} inflige {damage} dégâts.")
            if enemy_hp <= 0:
                break

            retaliation = max(1, enemy.attack + self.rng.randint(-2, 2))
            player.hp -= retaliation
            log.append(f"{enemy.name} riposte: {retaliation} dégâts.")

        if player.hp <= 0:
            player.hp = max(1, player.max_hp // 2)
            lost_gold = min(player.gold, 20)
            player.gold -= lost_gold
            log.append(f"Défaite. Vous perdez {lost_gold} or et revenez à {player.hp} HP.")
        else:
            gained_gold = enemy.level * 11 + self.rng.randint(0, 10)
            player.gold += gained_gold
            log.append(f"Victoire ! +{gained_gold} or")
            log.extend(player.add_xp(enemy.xp_reward))
            if self.rng.random() < 0.33:
                player.inventory["Potion"] = player.inventory.get("Potion", 0) + 1
                log.append("Butin: Potion")

        return log

    def chunk_key(self, pos: Vec3) -> Tuple[int, int]:
        return int(pos.x // 250), int(pos.z // 250)

    def generate_chunk(self, key: Tuple[int, int]) -> Dict[str, object]:
        if key in self.generated_chunks:
            return self.generated_chunks[key]
        biome = self.rng.choice(self.biomes)
        level_bias = self.rng.randint(1, 10)
        info = {
            "chunk": {"cx": key[0], "cz": key[1]},
            "biome": biome,
            "danger_level": level_bias,
            "resources": self.resource_table[biome],
            "landmark": self.rng.choice(
                ["tour effondrée", "autel oublié", "fortin détruit", "arbre-monde brisé"]
            ),
        }
        self.generated_chunks[key] = info
        return info


class MMORealtimeServer:
    """Serveur TCP JSON line-based, prêt pour un client 3D (Unity/Godot/Unreal).

    Protocole:
      - Chaque requête est une ligne JSON UTF-8.
      - Réponse = événement(s) JSON avec champ `type`.
      - Le client doit d'abord faire `join`.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7777,
        seed: int | None = None,
        shard_count: int = 1,
        shard_capacity: int = 200,
    ):
        self.host = host
        self.port = port
        self.world = World(seed=seed)
        self._rng = Random(seed)
        self._lock = threading.RLock()
        self.players: Dict[str, ConnectedPlayerState] = {}
        self.guilds: Dict[str, List[str]] = {}
        self.shard_count = max(1, shard_count)
        self.shard_capacity = max(10, shard_capacity)

    def _serialize_player(self, state: ConnectedPlayerState) -> Dict[str, object]:
        p = state.player
        return {
            "name": p.name,
            "faction": p.faction,
            "class": p.klass,
            "level": p.level,
            "hp": p.hp,
            "max_hp": p.max_hp,
            "attack": p.attack,
            "gold": p.gold,
            "position": {"x": state.position.x, "y": state.position.y, "z": state.position.z},
            "shard_id": state.shard_id,
            "region": state.region_name,
            "guild": state.guild,
            "resources": dict(state.resources),
        }

    def _assign_shard(self) -> int:
        populations: Dict[int, int] = {idx: 0 for idx in range(self.shard_count)}
        for state in self.players.values():
            populations[state.shard_id] = populations.get(state.shard_id, 0) + 1
        shard_id, size = min(populations.items(), key=lambda item: item[1])
        if size >= self.shard_capacity:
            raise ValueError("Serveur saturé: tous les shards sont pleins")
        return shard_id

    def _best_region_for_level(self, level: int) -> Region:
        unlocked = [region for region in self.world.regions if level >= region.min_level]
        return unlocked[-1]

    def join(self, *, name: str, faction: str, klass: str) -> Dict[str, object]:
        with self._lock:
            if name in self.players:
                raise ValueError("Pseudo déjà utilisé")
            player = self.world.create_player(name=name, faction=faction, klass=klass)
            shard_id = self._assign_shard()
            region = self._best_region_for_level(player.level)
            self.players[name] = ConnectedPlayerState(
                player=player,
                shard_id=shard_id,
                region_name=region.name,
            )
            return {
                "type": "joined",
                "player": self._serialize_player(self.players[name]),
                "online": len(self.players),
                "shard_population": self._shard_population(shard_id),
            }

    def move(self, *, name: str, dx: float, dy: float, dz: float) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            state.position = Vec3(
                state.position.x + dx,
                state.position.y + dy,
                state.position.z + dz,
            ).clamp(-5000.0, 5000.0)
            return {
                "type": "moved",
                "name": name,
                "position": {
                    "x": round(state.position.x, 2),
                    "y": round(state.position.y, 2),
                    "z": round(state.position.z, 2),
                },
            }

    def nearby(self, *, name: str, radius: float = 120.0) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            result: List[Dict[str, object]] = []
            for other_name, other in self.players.items():
                if other_name == name:
                    continue
                if other.shard_id != state.shard_id:
                    continue
                dist = _distance(state.position, other.position)
                if dist <= radius:
                    result.append(
                        {
                            "name": other_name,
                            "distance": round(dist, 2),
                            "position": {
                                "x": round(other.position.x, 2),
                                "y": round(other.position.y, 2),
                                "z": round(other.position.z, 2),
                            },
                            "level": other.player.level,
                            "region": other.region_name,
                        }
                    )
            result.sort(key=lambda x: x["distance"])
            return {"type": "nearby", "players": result, "shard_id": state.shard_id}

    def say(self, *, name: str, message: str, radius: float = 180.0) -> Dict[str, object]:
        with self._lock:
            speaker = self.players[name]
            recipients = 0
            trimmed = message.strip()[:200]
            if not trimmed:
                raise ValueError("Message vide")
            for other_name, other in self.players.items():
                if other.shard_id != speaker.shard_id:
                    continue
                if _distance(speaker.position, other.position) <= radius:
                    other.nearby_chat.append(f"[{name}] {trimmed}")
                    recipients += 1
            return {
                "type": "say",
                "from": name,
                "delivered": recipients,
                "shard_id": speaker.shard_id,
            }

    def chat_pull(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            inbox = self.players[name].nearby_chat[:]
            self.players[name].nearby_chat.clear()
            return {"type": "chat", "messages": inbox}

    def fight(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            region = self._best_region_for_level(state.player.level)
            state.region_name = region.name
            enemy = self.world.rng.choice(region.enemies)
            log = self.world.run_combat(state.player, enemy)
            return {
                "type": "combat",
                "enemy": enemy.name,
                "region": region.name,
                "log": log,
                "player": self._serialize_player(state),
            }

    def explore(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            key = self.world.chunk_key(state.position)
            chunk = self.world.generate_chunk(key)
            return {
                "type": "explore",
                "name": name,
                "chunk": chunk,
            }

    def gather(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            chunk = self.world.generate_chunk(self.world.chunk_key(state.position))
            resource = self._rng.choice(chunk["resources"])
            amount = self._rng.randint(1, 3)
            state.resources[resource] = state.resources.get(resource, 0) + amount
            return {
                "type": "gather",
                "resource": resource,
                "amount": amount,
                "inventory": dict(state.resources),
            }

    def craft(self, *, name: str, recipe_name: str) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            if recipe_name not in self.world.recipes:
                raise ValueError("Recette inconnue")
            recipe = self.world.recipes[recipe_name]
            for resource, needed in recipe["requires"].items():
                if state.resources.get(resource, 0) < needed:
                    raise ValueError(f"Ressources insuffisantes pour {resource}")
            for resource, needed in recipe["requires"].items():
                state.resources[resource] -= needed
            state.player.attack += recipe["bonus_attack"]
            state.player.max_hp += recipe["bonus_hp"]
            state.player.hp = min(state.player.max_hp, state.player.hp + recipe["bonus_hp"])
            return {
                "type": "crafted",
                "item": recipe_name,
                "player": self._serialize_player(state),
            }

    def create_guild(self, *, name: str, guild_name: str) -> Dict[str, object]:
        with self._lock:
            guild_name = guild_name.strip()[:32]
            if not guild_name:
                raise ValueError("Nom de guilde vide")
            if guild_name in self.guilds:
                raise ValueError("Guilde déjà existante")
            state = self.players[name]
            if state.guild:
                raise ValueError("Le joueur est déjà dans une guilde")
            self.guilds[guild_name] = [name]
            state.guild = guild_name
            return {"type": "guild_created", "guild": guild_name, "members": [name]}

    def join_guild(self, *, name: str, guild_name: str) -> Dict[str, object]:
        with self._lock:
            if guild_name not in self.guilds:
                raise ValueError("Guilde introuvable")
            state = self.players[name]
            if state.guild:
                raise ValueError("Le joueur est déjà dans une guilde")
            self.guilds[guild_name].append(name)
            state.guild = guild_name
            return {
                "type": "guild_joined",
                "guild": guild_name,
                "members": list(self.guilds[guild_name]),
            }

    def raid_boss(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            leader = self.players[name]
            party = [
                other for other in self.players.values()
                if other.shard_id == leader.shard_id and other.region_name == leader.region_name
            ]
            if len(party) < 3:
                raise ValueError("Il faut au moins 3 joueurs dans la même région pour un raid")
            boss_hp = 500 + len(party) * 80
            combined_attack = sum(member.player.attack for member in party)
            turns = 0
            while boss_hp > 0 and turns < 8:
                turns += 1
                boss_hp -= max(1, combined_attack + self._rng.randint(-10, 20))
                for member in party:
                    member.player.hp = max(1, member.player.hp - self._rng.randint(2, 12))
            victory = boss_hp <= 0
            rewards = []
            if victory:
                for member in party:
                    xp_gain = 120 + self._rng.randint(0, 50)
                    member.player.gold += 75
                    member.player.inventory["Potion"] = member.player.inventory.get("Potion", 0) + 1
                    member.player.add_xp(xp_gain)
                    rewards.append({"name": member.player.name, "xp": xp_gain, "gold": 75})
            return {
                "type": "raid",
                "boss": "Titan du Néant",
                "victory": victory,
                "turns": turns,
                "participants": [member.player.name for member in party],
                "rewards": rewards,
            }

    def teleport_region(self, *, name: str, region_name: str) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            candidates = {region.name: region for region in self.world.regions}
            if region_name not in candidates:
                raise ValueError("Région inconnue")
            region = candidates[region_name]
            if state.player.level < region.min_level:
                raise ValueError("Niveau insuffisant pour cette région")
            state.region_name = region_name
            # on repositionne le joueur pour éviter les collisions de spawn
            offset = self._rng.uniform(-30, 30)
            state.position = Vec3(offset, 0.0, offset)
            return {
                "type": "teleport",
                "region": region_name,
                "position": {"x": round(state.position.x, 2), "y": 0.0, "z": round(state.position.z, 2)},
                "shard_id": state.shard_id,
            }

    def _shard_population(self, shard_id: int) -> int:
        return sum(1 for state in self.players.values() if state.shard_id == shard_id)

    def world_state(self) -> Dict[str, object]:
        with self._lock:
            top_players: List[Tuple[str, int]] = sorted(
                ((name, state.player.level) for name, state in self.players.items()),
                key=lambda item: item[1],
                reverse=True,
            )[:10]
            shards = [
                {"shard_id": shard_id, "population": self._shard_population(shard_id)}
                for shard_id in range(self.shard_count)
            ]
            return {
                "type": "world_state",
                "online": len(self.players),
                "shards": shards,
                "top_players": [{"name": name, "level": level} for name, level in top_players],
                "regions": [
                    {"name": region.name, "min_level": region.min_level, "enemy_count": len(region.enemies)}
                    for region in self.world.regions
                ],
                "guilds": [{"name": gname, "members": len(members)} for gname, members in self.guilds.items()],
            }

    def handle_request(self, payload: Dict[str, object]) -> Dict[str, object]:
        action = payload.get("action")
        if not isinstance(action, str):
            raise ValueError("Champ 'action' manquant")

        if action == "join":
            return self.join(
                name=str(payload["name"]),
                faction=str(payload["faction"]),
                klass=str(payload["class"]),
            )
        if action == "world_state":
            return self.world_state()

        name = str(payload.get("name", ""))
        if not name:
            raise ValueError("Champ 'name' requis")
        if name not in self.players:
            raise ValueError("Joueur inconnu")

        if action == "move":
            return self.move(
                name=name,
                dx=float(payload.get("dx", 0.0)),
                dy=float(payload.get("dy", 0.0)),
                dz=float(payload.get("dz", 0.0)),
            )
        if action == "nearby":
            return self.nearby(name=name, radius=float(payload.get("radius", 120.0)))
        if action == "say":
            return self.say(name=name, message=str(payload.get("message", "")))
        if action == "chat_pull":
            return self.chat_pull(name=name)
        if action == "fight":
            return self.fight(name=name)
        if action == "explore":
            return self.explore(name=name)
        if action == "gather":
            return self.gather(name=name)
        if action == "craft":
            return self.craft(name=name, recipe_name=str(payload.get("recipe", "")))
        if action == "guild_create":
            return self.create_guild(name=name, guild_name=str(payload.get("guild", "")))
        if action == "guild_join":
            return self.join_guild(name=name, guild_name=str(payload.get("guild", "")))
        if action == "raid":
            return self.raid_boss(name=name)
        if action == "teleport":
            return self.teleport_region(name=name, region_name=str(payload.get("region", "")))

        raise ValueError(f"Action inconnue: {action}")

    def create_tcp_handler(self):
        server = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                while True:
                    raw = self.rfile.readline()
                    if not raw:
                        return
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                        response = server.handle_request(payload)
                        envelope = {"ok": True, "event": response}
                    except Exception as exc:  # Protocole: toujours encapsuler l'erreur
                        envelope = {"ok": False, "error": str(exc)}
                    self.wfile.write((json.dumps(envelope) + "\n").encode("utf-8"))

        return Handler

    def serve_forever(self):
        with socketserver.ThreadingTCPServer((self.host, self.port), self.create_tcp_handler()) as srv:
            print(f"MMO server ready on {self.host}:{self.port}")
            srv.serve_forever()


def _distance(a: Vec3, b: Vec3) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def short_status(player: Player) -> str:
    return (
        f"{player.name} | {player.klass} {player.level} | HP {player.hp}/{player.max_hp} | "
        f"XP {player.xp}/{player.xp_for_next_level()} | Or {player.gold} | "
        f"Potions {player.inventory.get('Potion', 0)}"
    )


def run_cli() -> None:
    print("=== ETERNIA ONLINE (prototype) ===")
    name = input("Nom du héros: ").strip() or "Héros"

    print("Factions:")
    for idx, faction in enumerate(FACTIONS, start=1):
        print(f"  {idx}. {faction}")
    faction = FACTIONS[int(input("Choix faction [1-3]: ") or "1") - 1]

    print("Classes:")
    for idx, klass in enumerate(CLASSES, start=1):
        print(f"  {idx}. {klass}")
    klass = CLASSES[int(input("Choix classe [1-4]: ") or "1") - 1]

    world = World()
    player = world.create_player(name, faction, klass)

    print("\nBienvenue dans Eternia. Tapez: statut, carte, combat, potion, quitter")
    while True:
        cmd = input("\n> ").strip().lower()

        if cmd in {"quitter", "exit"}:
            print("À bientôt, légende.")
            return

        if cmd == "statut":
            print(short_status(player))
            continue

        if cmd == "potion":
            print(player.use_potion())
            continue

        if cmd == "carte":
            for region in world.available_regions(player):
                print(f"- {region.name} (niv min {region.min_level})")
            continue

        if cmd == "combat":
            regions = world.available_regions(player)
            region = regions[-1]
            enemy = world.rng.choice(region.enemies)
            for line in world.run_combat(player, enemy):
                print(line)
            print(short_status(player))
            continue

        print("Commande inconnue.")


def run_server_cli() -> None:
    host = input("Host [127.0.0.1]: ").strip() or "127.0.0.1"
    port_raw = input("Port [7777]: ").strip() or "7777"
    port = int(port_raw)
    MMORealtimeServer(host=host, port=port).serve_forever()


if __name__ == "__main__":
    mode = input("Mode [solo/server]: ").strip().lower() or "solo"
    if mode == "server":
        run_server_cli()
    else:
        run_cli()
