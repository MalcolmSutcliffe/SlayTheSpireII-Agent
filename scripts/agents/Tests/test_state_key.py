"""state_key: equal for transposed play orders, different for anything that changes the fight.
Run from scripts/: python -m pytest sts2_lite/Tests/test_state_key.py"""
import itertools
import json
from pathlib import Path

import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.relic import RelicId, RelicInstance
from agents.sts2_MCTS.state_key import state_key
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state

BENCH_STATES = Path(__file__).resolve().parents[2] / "benchmarks" / "act1"


def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def key_after(hand, order, enemy_count=1):
    """Plays hand[i] for i in `order` (always at enemy 0) and returns the key."""
    cs = make_state([Card.create_copy(c) for c in hand], enemy_count=enemy_count, enemy_hp=100)
    cs.energy = cs.max_energy = 10
    sim = CombatSimulator(cs)
    chosen = [cs.player.hand[i] for i in order]
    for card in chosen:
        sim.play_card(cs.player.hand.index(card), 0)
    return state_key(cs)


# ---------------------------------------------------------------- transpositions
def test_a_state_and_its_copy_have_the_same_key():
    cs = make_state([strike(), defend()])
    assert state_key(cs) == state_key(CombatState.deepcopy(cs))

def test_the_key_is_hashable():
    assert isinstance(hash(state_key(make_state([strike(), defend(), bash()]))), int)

def test_play_order_does_not_change_the_key():
    hand = [strike(), defend(), strike(), defend()]
    by_set = {}
    for order in itertools.permutations(range(4), 3):
        by_set.setdefault(frozenset(order), set()).add(key_after(hand, order))
    assert all(len(v) == 1 for v in by_set.values())
    assert len({next(iter(v)) for v in by_set.values()}) == 2       # {S,D,S} and {S,D,D}: equal cards are interchangeable

def test_an_order_that_changes_the_outcome_changes_the_key():
    """Bash before Strike lands the Strike on a Vulnerable enemy."""
    hand = [strike(), bash()]
    assert key_after(hand, (0, 1)) != key_after(hand, (1, 0))

def test_playing_different_cards_gives_different_keys():
    hand = [strike(), defend(), bash()]
    assert len({key_after(hand, (i,)) for i in range(3)}) == 3

def test_hand_order_alone_is_ignored():
    a, b = make_state([strike(), defend(), bash()]), make_state([bash(), strike(), defend()])
    assert state_key(a) == state_key(b)

def test_discard_and_exhaust_order_are_ignored():
    a, b = make_state([]), make_state([])
    a.player.discard_pile, b.player.discard_pile = [strike(), defend()], [defend(), strike()]
    a.player.exhaust_pile, b.player.exhaust_pile = [strike(), bash()], [bash(), strike()]
    assert state_key(a) == state_key(b)


# ---------------------------------------------------------------- the draw pile: unseen part is a multiset, known top is ordered
def test_order_of_the_unseen_draw_pile_is_ignored():
    a, b = make_state([]), make_state([])
    a.player.draw_pile, b.player.draw_pile = [strike(), defend(), bash()], [bash(), strike(), defend()]
    assert state_key(a) == state_key(b)

def test_order_of_the_known_top_matters():
    a, b = make_state([]), make_state([])
    a.player.draw_pile, b.player.draw_pile = [bash(), strike(), defend()], [bash(), defend(), strike()]
    a.player.known_top = b.player.known_top = 2
    assert state_key(a) != state_key(b)

def test_the_known_top_differs_from_an_unseen_pile_with_the_same_cards():
    a, b = make_state([]), make_state([])
    a.player.draw_pile = b.player.draw_pile = [bash(), strike(), defend()]
    a.player.known_top, b.player.known_top = 0, 2
    assert state_key(a) != state_key(b)

def test_the_unseen_part_below_the_known_top_is_still_a_multiset():
    a, b = make_state([]), make_state([])
    a.player.draw_pile = [bash(), strike(), defend()]
    b.player.draw_pile = [strike(), bash(), defend()]
    a.player.known_top = b.player.known_top = 1
    assert state_key(a) == state_key(b)


# ---------------------------------------------------------------- anything that changes the fight changes the key
def _edit_first_card(player, field, value):
    """Cards are shared between states (Card.create_copy to change one), so edit a copy."""
    card = Card.create_copy(player.hand[0])
    setattr(card, field, value)
    player.hand[0] = card

def _mutations():
    def player(f):
        return lambda cs: f(cs.player)
    yield "energy", lambda cs: setattr(cs, "energy", cs.energy - 1)
    yield "max_energy", lambda cs: setattr(cs, "max_energy", cs.max_energy + 1)
    yield "turn", lambda cs: setattr(cs, "turn_number", cs.turn_number + 1)
    yield "extra_turns", lambda cs: setattr(cs, "extra_turns", 1)
    yield "cards_played", lambda cs: setattr(cs, "cards_played", 1)
    yield "player hp", player(lambda p: setattr(p, "current_hp", p.current_hp - 1))
    yield "player max hp", player(lambda p: setattr(p, "max_hp", p.max_hp + 1))
    yield "player block", player(lambda p: setattr(p, "block", 3))
    yield "player status", player(lambda p: p.apply_status(StatusId.STRENGTH, 1))
    yield "hand", player(lambda p: p.hand.append(strike()))
    yield "hand card upgraded", player(lambda p: _edit_first_card(p, "is_upgraded", True))
    yield "hand card cost", player(lambda p: _edit_first_card(p, "energy_cost", 0))
    yield "draw", player(lambda p: p.draw_pile.append(strike()))
    yield "discard", player(lambda p: p.discard_pile.append(strike()))
    yield "exhaust", player(lambda p: p.exhaust_pile.append(strike()))
    yield "relic", player(lambda p: p.relics.__setitem__(RelicId.BURNING_BLOOD, RelicInstance(RelicId.BURNING_BLOOD)))
    yield "gold", player(lambda p: setattr(p, "gold", 5))
    yield "attacks played", player(lambda p: setattr(p, "attacks_played_this_turn", 2))
    yield "cards played total", player(lambda p: setattr(p, "cards_played_total", 4))
    yield "hp loss events", player(lambda p: setattr(p, "hp_loss_events", 1))
    yield "returning", player(lambda p: p.returning.append((CardId.STRIKE_IRONCLAD, False)))
    yield "enemy hp", lambda cs: setattr(cs.enemies[0], "current_hp", cs.enemies[0].current_hp - 1)
    yield "enemy block", lambda cs: setattr(cs.enemies[0], "block", 4)
    yield "enemy status", lambda cs: cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    yield "enemy move", lambda cs: setattr(cs.enemies[0], "move_id", "OTHER")
    yield "enemy damage", lambda cs: setattr(cs.enemies[0], "attack_damage", cs.enemies[0].attack_damage + 1)
    yield "enemy streak", lambda cs: setattr(cs.enemies[0], "move_streak", cs.enemies[0].move_streak + 1)
    yield "enemy used moves", lambda cs: cs.enemies[0].used_moves.add("X")
    yield "enemy order", lambda cs: cs.enemies.reverse()
    yield "enemy removed", lambda cs: cs.enemies.pop()
    yield "revival", lambda cs: cs.revivals.append(("M", 0))

@pytest.mark.parametrize("name,mutate", list(_mutations()), ids=[n for n, _ in _mutations()])
def test_a_difference_changes_the_key(name, mutate):
    base = make_state([strike(), defend()], enemy_count=2)
    base.enemies[1].current_hp = 7                  # so reversing the enemies is a change
    other = CombatState.deepcopy(base)
    other.player.hand = list(base.player.hand)
    mutate(other)
    assert state_key(base) != state_key(other), name

def test_a_pending_choice_changes_the_key():
    from sts2_lite.combat import PendingChoice
    a = make_state([strike(), defend()])
    b = CombatState.deepcopy(a)
    b.pending_choice = PendingChoice("exhaust", [0, 1])
    c = CombatState.deepcopy(a)
    c.pending_choice = PendingChoice("exhaust", [1])
    assert len({state_key(a), state_key(b), state_key(c)}) == 3

def test_accounting_counters_are_ignored():
    a = make_state([strike()])
    b = CombatState.deepcopy(a)
    b.player.hand = list(a.player.hand)
    b.player.cards_drawn, b.player.unknown_draws, b.player.damage_taken = 9, 4, 30
    b.enemies[0].damage_taken = 12
    b.player.block_play, b.player.block_play_gains = 7, 1
    assert state_key(a) == state_key(b)


# ---------------------------------------------------------------- a new field must be a decision, not an oversight
KEYED_OR_IGNORED = {
    "Player": {"block", "current_hp", "max_hp", "status", "hand", "draw_pile", "discard_pile", "exhaust_pile", "relics", "known_top",
               "inferno_plays", "cards_played_total", "crimson_mantle_plays", "attacks_played_this_turn", "plays_started_this_turn",
               "returning", "card_blocks_this_turn", "cards_exhausted_this_turn", "gold", "has_been_attacked_this_turn",
               "lost_hp_this_turn", "hp_loss_events", "hp_lost_log", "is_minion", "binding", "bound_cards", "bound_played", "smogged",
               "potions", "extra_turn_pending",
               # ignored: accounting that nothing reads between actions, and hooks wired by the simulator
               "cards_drawn", "unknown_draws", "damage_taken", "block_play", "block_play_gains",
               "shuffle_hook", "draw_hook", "block_cleared_hook",
               "potion_slots"},           # ignored: fixed for the run; it only matters to Entropic Brew
    "Enemy": {"block", "current_hp", "max_hp", "status", "is_minion", "enemy_id", "slot", "attack_damage", "num_attacks", "damage_candidates",
              "moves", "move_id", "move_streak", "used_moves", "has_been_attacked_this_turn", "lost_hp_this_turn", "hp_loss_events",
              "hp_lost_log", "damage_taken", "after_stun", "off_balance", "counter"},
    "CombatState": {"player", "enemies", "energy", "max_energy", "turn_number", "extra_turns", "ascension", "cards_played", "revivals",
                    "pending_choice", "won", "dormant", "continuations",
                    "hp_loss_read"},      # ignored: set while loading, before any action
    "RelicInstance": {"relic_id", "counter", "used", "value", "triggering"},
}

def test_every_copied_field_is_in_the_key():
    """Any attribute that appears on a state's objects must be listed above, i.e. consciously keyed or ignored."""
    files = sorted(BENCH_STATES.glob("*.json"))[:12]
    assert files, "needs the benchmark states"
    seen = {k: set() for k in KEYED_OR_IGNORED}
    for f in files:
        cs = CombatState.from_dict(json.loads(f.read_text()))
        sim = CombatSimulator(cs)
        for _ in range(3):
            actions = [a for a in sim.get_available_actions() if a["action"] != "end_turn"]
            if not actions:
                break
            sim.perform_action(actions[0])
        seen["CombatState"] |= set(vars(cs))
        seen["Player"] |= set(vars(cs.player)) | {n for n in dir(cs.player) if n.endswith("_hook")}
        for e in cs.enemies:
            seen["Enemy"] |= set(vars(e))
        for r in cs.player.relics.values():
            seen["RelicInstance"] |= set(vars(r))
    for kind, names in seen.items():
        assert names <= KEYED_OR_IGNORED[kind], f"{kind}: unclassified field(s) {sorted(names - KEYED_OR_IGNORED[kind])}: add to state_key.py or ignore deliberately"


# ---------------------------------------------------------------- on real states: soundness and how often orders merge
def _playable(sim, state):
    out = []
    for a in sim.get_available_actions():
        if a["action"] == "play_card":
            out.append(a)
    return out

def _non_random_children(state):
    """(action key, child state) for every play whose result involves no rng and no unseen draw."""
    from agents.sts2_MCTS.MCTS import _action_key
    out = []
    sim = CombatSimulator(state)
    for a in [a for a in sim.get_available_actions() if a["action"] == "play_card"]:
        child = CombatState.deepcopy(state)
        calls, unknown = rng.calls, child.player.unknown_draws
        CombatSimulator(child).perform_action(a)
        if rng.calls == calls and child.player.unknown_draws == unknown:
            out.append((_action_key(sim, a), child))
    return out

def _expand(frontier):
    nxt = []
    for state in frontier:
        nxt += [child for _, child in _non_random_children(state)]
    return nxt

def test_equal_keys_mean_equal_futures_and_orders_do_merge():
    """Two plies of plays from real states: states with equal keys must offer the same plays and reach the same keys
    (random plays excluded), and a hand with several playable cards must show transpositions."""
    files = sorted(BENCH_STATES.glob("*.json"))
    assert files, "needs the benchmark states"
    merged_somewhere = False
    for f in files:
        root = CombatState.from_dict(json.loads(f.read_text()))
        level = [root]
        for _ in range(2):
            level = _expand(level)[:300]
        by_key = {}
        for s in level:
            by_key.setdefault(state_key(s), []).append(s)
        if len(by_key) < len(level):
            merged_somewhere = True
        for same in by_key.values():
            if len(same) < 2:
                continue
            first = same[0]
            expected = sorted((repr(k), state_key(c)) for k, c in _non_random_children(first))
            for other in same[1:]:
                got = sorted((repr(k), state_key(c)) for k, c in _non_random_children(other))
                assert got == expected, f"{f.name}: equal keys, different futures"
    assert merged_somewhere


# ---------------------------------------------------------------- pending picks name positions
def _picking(pile_name, cards, known_top=0):
    from sts2_lite.combat import PendingChoice
    cs = make_state([])
    pile = {"discard": "discard_pile", "draw": "draw_pile", "hand": "hand"}[pile_name]
    setattr(cs.player, pile, list(cards))
    cs.player.known_top = known_top
    cs.pending_choice = PendingChoice("to_draw_pile", list(range(len(cards))), pile_name)
    return cs

def test_a_pick_from_the_discard_pile_ignores_the_piles_order():
    """Headbutt: positions 0..n of the discard pile. The same cards in another order offer the same choices."""
    assert state_key(_picking("discard", [strike(), defend(), bash()])) == state_key(_picking("discard", [bash(), strike(), defend()]))

def test_a_pick_from_the_discard_pile_still_sees_which_cards_are_there():
    assert state_key(_picking("discard", [strike(), defend()])) != state_key(_picking("discard", [strike(), bash()]))

def test_a_pick_from_the_draw_pile_keeps_the_piles_order():
    a = _picking("draw", [strike(), defend(), bash()])
    b = _picking("draw", [bash(), strike(), defend()])
    assert state_key(a) != state_key(b)


# ---------------------------------------------------------------- copies keep the per-turn flags
def test_a_copy_between_two_attacks_remembers_the_first():
    """Skittish blocks on the first attack of a turn; the search copies the state after every play."""
    from sts2_lite.enemy import Enemy
    cs = make_state([strike(), strike()], enemy_count=1, enemy_hp=100)
    cs.enemies[0].apply_status(StatusId.SKITTISH, 6)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].block == 6
    copy = CombatState.deepcopy(cs)
    assert copy.enemies[0].has_been_attacked_this_turn
    CombatSimulator(copy).play_card(0, 0)
    assert copy.enemies[0].block == 0           # the second Strike (6 damage) used up the first block: no new Skittish block

def test_per_turn_flags_survive_a_copy():
    cs = make_state([])
    cs.enemies[0].has_been_attacked_this_turn = cs.enemies[0].lost_hp_this_turn = True
    cs.enemies[0].hp_loss_events = 2
    cs.player.has_been_attacked_this_turn = True
    copy = CombatState.deepcopy(cs)
    assert (copy.enemies[0].has_been_attacked_this_turn, copy.enemies[0].lost_hp_this_turn, copy.enemies[0].hp_loss_events) == (True, True, 2)
    assert copy.player.has_been_attacked_this_turn
