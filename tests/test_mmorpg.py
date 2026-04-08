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


def test_world_state_and_shard_metadata():
    server = MMORealtimeServer(seed=1, shard_count=2, shard_capacity=50)
    server.handle_request(
        {"action": "join", "name": "Alice", "faction": FACTIONS[0], "class": CLASSES[0]}
    )
    joined_bob = server.handle_request(
        {"action": "join", "name": "Bob", "faction": FACTIONS[1], "class": CLASSES[1]}
    )

    assert "shard_id" in joined_bob["player"]
    snapshot = server.handle_request({"action": "world_state"})
    assert snapshot["type"] == "world_state"
    assert snapshot["online"] == 2
    assert len(snapshot["shards"]) == 2


def test_teleport_requires_unlocked_region():
    server = MMORealtimeServer(seed=9)
    server.handle_request(
        {"action": "join", "name": "Alice", "faction": FACTIONS[0], "class": CLASSES[0]}
    )

    try:
        server.handle_request(
            {"action": "teleport", "name": "Alice", "region": "Faille Céleste"}
        )
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_explore_gather_and_craft_flow():
    server = MMORealtimeServer(seed=4)
    server.handle_request(
        {"action": "join", "name": "Alice", "faction": FACTIONS[0], "class": CLASSES[0]}
    )

    explored = server.handle_request({"action": "explore", "name": "Alice"})
    assert explored["type"] == "explore"
    assert "biome" in explored["chunk"]

    # injecte directement les ressources pour valider le craft de manière déterministe
    state = server.players["Alice"]
    state.resources["Fragment antique"] = 2
    state.resources["Noyau d'obsidienne"] = 1
    before_attack = state.player.attack
    crafted = server.handle_request(
        {"action": "craft", "name": "Alice", "recipe": "Lame astrale"}
    )
    assert crafted["type"] == "crafted"
    assert crafted["player"]["attack"] > before_attack


def test_guild_and_raid():
    server = MMORealtimeServer(seed=11)
    for idx, fname in enumerate(("Alice", "Bob", "Cleo")):
        server.handle_request(
            {"action": "join", "name": fname, "faction": FACTIONS[idx], "class": CLASSES[idx]}
        )

    created = server.handle_request(
        {"action": "guild_create", "name": "Alice", "guild": "Les Immortels"}
    )
    assert created["type"] == "guild_created"
    joined = server.handle_request(
        {"action": "guild_join", "name": "Bob", "guild": "Les Immortels"}
    )
    assert joined["type"] == "guild_joined"

    raid = server.handle_request({"action": "raid", "name": "Alice"})
    assert raid["type"] == "raid"
    assert len(raid["participants"]) == 3
