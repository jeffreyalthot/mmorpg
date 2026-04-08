from __future__ import annotations

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


class World:
    """Mini noyau MMORPG solo: progression, zones, combat et économie."""

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


if __name__ == "__main__":
    run_cli()
