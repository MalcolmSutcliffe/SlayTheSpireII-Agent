from agents.decision import Decision, Option, MAP
from agents.pathing import PathPlanner


def node(col, row, typ, *children):
    return {"col": col, "row": row, "type": typ, "children": [list(c) for c in children]}


def decide(nodes, choices, visited=(), hp=80, max_hp=80, gold=0, here=None):
    options = [Option(f"{c['type']}", {"action": "choose_map_node", "index": i}, {**c, "index": i}) for i, c in enumerate(choices)]
    state = {"nodes": nodes, "visited": list(visited), "choices": choices, "player": {"hp": hp, "max_hp": max_hp, "gold": gold}}
    if here is not None:
        state["current_position"] = {"col": 0, "row": here}
    return PathPlanner().choose(Decision(MAP, state, options)).data["index"]


def test_picks_the_higher_scoring_route():
    nodes = [node(0, 1, "Monster", (0, 2)), node(1, 1, "RestSite", (1, 2)), node(0, 2, "Boss"), node(1, 2, "Boss")]
    assert decide(nodes, [nodes[0], nodes[1]]) == 1        # rest 1.5 > combat 1.5? tie on score -> more rests
    nodes[1]["type"] = "Shop"
    assert decide(nodes, [nodes[0], nodes[1]]) == 0


def test_rest_beats_combat_when_hurt():
    nodes = [node(0, 1, "Monster", (0, 2)), node(1, 1, "Unknown", (1, 2)), node(2, 1, "RestSite", (2, 2)),
             node(0, 2, "Boss"), node(1, 2, "Boss"), node(2, 2, "Boss")]
    assert decide(nodes, nodes[:3], hp=20) == 2
    assert decide(nodes, nodes[:3], hp=80) == 2        # 1.5 ties with Unknown/Monster: most rests wins


def test_first_three_combats_count_from_the_start_of_the_act():
    # after 3 combats a combat is worth 1.0, so a Shop route with nothing loses to it but an Unknown (1.5) wins
    nodes = [node(0, 1, "Monster"), node(1, 1, "Unknown")]
    visited = [{"type": "Monster"}] * 3
    assert decide(nodes, nodes, visited) == 1
    assert decide([node(0, 1, "Monster"), node(1, 1, "Shop")], [node(0, 1, "Monster"), node(1, 1, "Shop")], visited) == 0


def test_elite_is_worth_more_after_the_treasure():
    # route A: elite then treasure (0.8); route B: treasure then elite (1.8); same other nodes
    a = [node(0, 1, "Elite", (0, 2)), node(0, 2, "Treasure")]
    b = [node(1, 1, "Treasure", (1, 2)), node(1, 2, "Elite")]
    assert decide(a + b, [a[0], b[0]]) == 1


def test_treasure_already_visited_makes_every_elite_late():
    nodes = [node(0, 1, "Elite"), node(1, 1, "Monster")]
    assert decide(nodes, nodes, visited=[{"type": "Treasure"}]) == 0
    assert decide(nodes, nodes) == 1        # 0.8 < 1.5


def test_ties_go_to_more_rests_then_leftmost():
    nodes = [node(0, 1, "Monster"), node(1, 1, "Monster")]
    assert decide(nodes, nodes) == 0


def test_first_shop_is_worth_gold_and_floors_to_it():
    # shop 4 rows ahead: 100 gold + 3 floors in between * 20 = 160 -> 1.6; a lone combat is 1.5
    shop = [node(0, 1, "Monster", (0, 2)), node(0, 2, "Monster", (0, 3)), node(0, 3, "Monster", (0, 4)), node(0, 4, "Shop")]
    combat = [node(1, 1, "Monster")]
    # the shop route scores 1.5 * 3 + 1.6 = 6.1 against 1.5
    assert decide(shop + combat, [shop[0], combat[0]], gold=100, here=0) == 0


def test_a_rich_shop_next_door_beats_a_combat_and_only_the_first_shop_counts():
    nodes = [node(0, 1, "Shop", (0, 2)), node(0, 2, "Shop"), node(1, 1, "Monster")]
    assert decide(nodes, [nodes[0], nodes[2]], gold=300, here=0) == 0      # 3.0 (the second shop adds nothing)
    assert decide(nodes, [nodes[0], nodes[2]], gold=100, here=0) == 1      # 1.0 < 1.5
