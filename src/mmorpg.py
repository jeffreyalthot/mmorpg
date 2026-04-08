from __future__ import annotations

import json
import socketserver
import threading
from dataclasses import dataclass, field
from random import Random
from typing import Dict, List


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


class World:
    """Noyau MMORPG: progression, zones, combat et économie."""

    def __init__(self, seed: int | None = None):
        self.rng = Random(seed)
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


class MMORealtimeServer:
    """Serveur TCP JSON line-based, prêt pour un client 3D (Unity/Godot/Unreal).

    Protocole:
      - Chaque requête est une ligne JSON UTF-8.
      - Réponse = événement(s) JSON avec champ `type`.
      - Le client doit d'abord faire `join`.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7777, seed: int | None = None):
        self.host = host
        self.port = port
        self.world = World(seed=seed)
        self._rng = Random(seed)
        self._lock = threading.RLock()
        self.players: Dict[str, ConnectedPlayerState] = {}

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
        }

    def join(self, *, name: str, faction: str, klass: str) -> Dict[str, object]:
        with self._lock:
            if name in self.players:
                raise ValueError("Pseudo déjà utilisé")
            player = self.world.create_player(name=name, faction=faction, klass=klass)
            self.players[name] = ConnectedPlayerState(player=player)
            return {
                "type": "joined",
                "player": self._serialize_player(self.players[name]),
                "online": len(self.players),
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
                        }
                    )
            result.sort(key=lambda x: x["distance"])
            return {"type": "nearby", "players": result}

    def say(self, *, name: str, message: str, radius: float = 180.0) -> Dict[str, object]:
        with self._lock:
            speaker = self.players[name]
            recipients = 0
            trimmed = message.strip()[:200]
            if not trimmed:
                raise ValueError("Message vide")
            for other_name, other in self.players.items():
                if _distance(speaker.position, other.position) <= radius:
                    other.nearby_chat.append(f"[{name}] {trimmed}")
                    recipients += 1
            return {
                "type": "say",
                "from": name,
                "delivered": recipients,
            }

    def chat_pull(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            inbox = self.players[name].nearby_chat[:]
            self.players[name].nearby_chat.clear()
            return {"type": "chat", "messages": inbox}

    def fight(self, *, name: str) -> Dict[str, object]:
        with self._lock:
            state = self.players[name]
            region = self.world.available_regions(state.player)[-1]
            enemy = self.world.rng.choice(region.enemies)
            log = self.world.run_combat(state.player, enemy)
            return {
                "type": "combat",
                "enemy": enemy.name,
                "log": log,
                "player": self._serialize_player(state),
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
