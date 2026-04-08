from src.mmorpg import CLASSES, FACTIONS, Enemy, MMORealtimeServer, World


def test_create_player_rejects_invalid_inputs():
    world = World(seed=1)

    try:
        world.create_player("Alice", "BadFaction", CLASSES[0])
        assert False, "Expected ValueError"
    except ValueError:
        pass

    try:
        world.create_player("Alice", FACTIONS[0], "BadClass")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_combat_grants_rewards_on_win():
    world = World(seed=7)
    player = world.create_player("Alice", FACTIONS[0], "Guerrier")
    enemy = Enemy("Rat géant", level=1, hp=1, attack=1, xp_reward=25)

    log = world.run_combat(player, enemy)

    assert any("Victoire" in line for line in log)
    assert player.gold > 0
    assert player.xp >= 25 or player.level > 1


def test_available_regions_progress_with_level():
    world = World(seed=3)
    player = world.create_player("Alice", FACTIONS[1], "Mage")

    initial = [r.name for r in world.available_regions(player)]
    assert "Plaine des Novices" in initial
    assert "Ruines d'Obsidienne" not in initial

    player.level = 8
    later = [r.name for r in world.available_regions(player)]
    assert "Ruines d'Obsidienne" in later
    assert "Faille Céleste" in later


def test_realtime_server_join_move_and_nearby():
    server = MMORealtimeServer(seed=42)

    joined_a = server.handle_request(
        {
            "action": "join",
            "name": "Alice",
            "faction": FACTIONS[0],
            "class": CLASSES[0],
        }
    )
    assert joined_a["type"] == "joined"

    server.handle_request(
        {
            "action": "join",
            "name": "Bob",
            "faction": FACTIONS[1],
            "class": CLASSES[1],
        }
    )

    server.handle_request({"action": "move", "name": "Bob", "dx": 10, "dy": 0, "dz": 0})
    nearby = server.handle_request({"action": "nearby", "name": "Alice", "radius": 15})

    assert nearby["type"] == "nearby"
    assert any(player["name"] == "Bob" for player in nearby["players"])


def test_realtime_chat_delivery_and_pull():
    server = MMORealtimeServer(seed=1)
    server.handle_request(
        {
            "action": "join",
            "name": "Alice",
            "faction": FACTIONS[0],
            "class": CLASSES[0],
        }
    )
    server.handle_request(
        {
            "action": "join",
            "name": "Bob",
            "faction": FACTIONS[1],
            "class": CLASSES[1],
        }
    )

    sent = server.handle_request({"action": "say", "name": "Alice", "message": "Salut Bob"})
    assert sent["delivered"] >= 2

    pulled = server.handle_request({"action": "chat_pull", "name": "Bob"})
    assert pulled["type"] == "chat"
    assert any("Salut Bob" in msg for msg in pulled["messages"])
