"""Combat tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.player import Player
from sts2_lite.status import StatusId


# ---------------------------------------------------------------- helpers
def make_card(card_id, name, card_type, cost, target):
    c = Card()
    c.card_id, c.name, c.type = card_id, name, card_type
    c.energy_cost, c.target_type = cost, target
    c.is_upgraded = False
    c.is_unplayable = False
    return c

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def inflame():
    return make_card(CardId.INFLAME, "Inflame", CardType.Power, 1, TargetType.Self)

def crimson_mantle():
    return make_card(CardId.CRIMSON_MANTLE, "Crimson Mantle", CardType.Power, 1, TargetType.Self)

def make_state(hand=None, draw=None, discard=None, energy=3):
    p = Player()
    p.max_hp = p.current_hp = 50
    p.hand = list(hand or [])
    p.draw_pile = list(draw or [])
    p.discard_pile = list(discard or [])
    e = Enemy()
    e.max_hp = e.current_hp = 40
    e.enemy_id = "TEST_ENEMY"
    e.attack_damage, e.num_attacks = 0, 1
    cs = CombatState()
    cs.player, cs.enemies = p, [e]
    cs.energy = cs.max_energy = energy
    cs.turn_number = 1
    cs.deck = [strike() for _ in range(5)]
    return cs

def all_cards(player):
    return player.hand + player.draw_pile + player.discard_pile


# ---------------------------------------------------------------- power cards
@pytest.mark.parametrize("make_power", [inflame, crimson_mantle])
def test_power_card_leaves_the_hand(make_power):
    cs = make_state(hand=[make_power()])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand == []

@pytest.mark.parametrize("make_power", [inflame, crimson_mantle])
def test_power_card_is_in_no_pile_after_play(make_power):
    power = make_power()
    cs = make_state(hand=[power], draw=[strike()], discard=[strike()])
    CombatSimulator(cs).play_card(0, 0)
    assert power not in all_cards(cs.player)

def test_power_card_still_has_its_effect():
    cs = make_state(hand=[inflame()])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 2

def test_power_card_reduces_total_card_count_by_one():
    cs = make_state(hand=[inflame(), strike()], draw=[strike()], discard=[strike()])
    CombatSimulator(cs).play_card(0, 0)
    assert len(all_cards(cs.player)) == 3

def test_power_card_is_not_reshuffled_into_the_draw_pile():
    power = inflame()
    cs = make_state(hand=[power], discard=[strike(), strike()])
    CombatSimulator(cs).play_card(0, 0)
    cs.player.shuffle_discard_into_draw()
    assert power not in cs.player.draw_pile
    assert len(cs.player.draw_pile) == 2

def test_power_card_costs_energy():
    cs = make_state(hand=[inflame()])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.energy == 2


# ---------------------------------------------------------------- other card types
def test_attack_card_goes_to_discard_pile():
    played = strike()
    cs = make_state(hand=[played])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand == []
    assert cs.player.discard_pile == [played]


# ---------------------------------------------------------------- cards with no target
def bridge_card(card_id="SLIMED", name="Slimed", card_type="Status", cost="1", target_type="None"):
    return {"id": card_id, "name": name, "type": card_type, "cost": cost, "target_type": target_type,
            "can_play": True, "is_upgraded": False}

def test_bridge_none_target_becomes_the_none_enum():
    assert Card.from_dict(bridge_card()).target_type == TargetType.NONE

def test_card_with_no_target_is_offered_as_an_action():
    slimed = make_card(CardId.SLIMED, "Slimed", CardType.Status, 1, TargetType.NONE)
    actions = CombatSimulator(make_state([slimed])).get_available_actions()
    assert {"action": "play_card", "card_index": 0, "target": 0} in actions

def test_bridge_slimed_is_offered_as_an_action():
    cs = make_state([Card.from_dict(bridge_card())])
    actions = CombatSimulator(cs).get_available_actions()
    assert any(a["action"] == "play_card" for a in actions)

def test_card_with_no_target_is_not_offered_without_energy():
    slimed = make_card(CardId.SLIMED, "Slimed", CardType.Status, 1, TargetType.NONE)
    actions = CombatSimulator(make_state([slimed], energy=0)).get_available_actions()
    assert [a["action"] for a in actions] == ["end_turn"]

def test_card_with_no_target_is_offered_once():
    slimed = make_card(CardId.SLIMED, "Slimed", CardType.Status, 1, TargetType.NONE)
    cs = make_state([slimed, strike()])
    actions = CombatSimulator(cs).get_available_actions()
    plays = [a for a in actions if a["action"] == "play_card" and a["card_index"] == 0]
    assert len(plays) == 1

def test_card_with_no_target_can_be_played_through_perform_action():
    slimed = make_card(CardId.SLIMED, "Slimed", CardType.Status, 1, TargetType.NONE)
    drawn = strike()
    cs = make_state([slimed], draw=[drawn])
    sim = CombatSimulator(cs)
    action = next(a for a in sim.get_available_actions() if a["action"] == "play_card")
    sim.perform_action(action)
    assert cs.player.hand == [drawn]
    assert cs.energy == 2
    assert slimed not in cs.player.discard_pile


# ---------------------------------------------------------------- the played card leaves the hand first
from sts2_lite import card as card_module

def pommel_strike(upgraded=False):
    c = make_card(CardId.POMMEL_STRIKE, "Pommel Strike", CardType.Attack, 1, TargetType.AnyEnemy)
    c.is_upgraded = upgraded
    return c

def slimed():
    return make_card(CardId.SLIMED, "Slimed", CardType.Status, 1, TargetType.NONE)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def full_hand_with(card, others=9):
    return [card] + [defend() for _ in range(others)]

def test_pommel_strike_draws_from_a_full_hand():
    pommel, drawn = pommel_strike(), strike()
    cs = make_state(full_hand_with(pommel), draw=[drawn])
    CombatSimulator(cs).play_card(0, 0)
    assert drawn in cs.player.hand
    assert len(cs.player.hand) == 10
    assert cs.enemies[0].current_hp == 40 - 9

def test_upgraded_pommel_strike_draws_two_with_room_for_both():
    pommel = pommel_strike(upgraded=True)
    a, b = strike(), strike()
    cs = make_state(full_hand_with(pommel, others=8), draw=[a, b])
    CombatSimulator(cs).play_card(0, 0)
    assert a in cs.player.hand and b in cs.player.hand
    assert len(cs.player.hand) == 10

def test_slimed_draws_from_a_full_hand():
    drawn = strike()
    cs = make_state(full_hand_with(slimed()), draw=[drawn])
    CombatSimulator(cs).play_card(0, 0)
    assert drawn in cs.player.hand
    assert len(cs.player.hand) == 10

def test_a_full_hand_still_caps_draws_beyond_the_freed_slot():
    pommel = pommel_strike(upgraded=True)
    a, b = strike(), strike()
    cs = make_state(full_hand_with(pommel), draw=[a, b])
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 10
    assert len(cs.player.draw_pile) == 1

def test_played_card_is_not_in_the_hand_during_its_effect(monkeypatch):
    seen = {}
    cs = make_state([defend(), strike()])
    played = cs.player.hand[1]
    def probe(card, combat, target_index, is_upgraded=False):
        seen["in_hand"] = card in combat.combat_state.player.hand
        seen["hand_size"] = len(combat.combat_state.player.hand)
    monkeypatch.setitem(card_module.GET_CARD_FUNCTION, CardId.STRIKE_IRONCLAD, probe)
    CombatSimulator(cs).play_card(1, 0)
    assert seen == {"in_hand": False, "hand_size": 1}

def test_other_cards_keep_their_order_in_the_hand():
    a, b, c, d = strike(), defend(), strike(), defend()
    cs = make_state([a, b, c, d])
    CombatSimulator(cs).play_card(2, 0)
    assert cs.player.hand == [a, b, d]

def test_an_illegal_target_puts_the_card_back_where_it_was():
    a, b, c = defend(), strike(), defend()
    cs = make_state([a, b, c])
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(1, 7)
    assert cs.player.hand == [a, b, c]
    assert cs.player.discard_pile == []
    assert cs.energy == 3

def test_an_unplayable_card_stays_in_the_hand():
    a = strike()
    cs = make_state([a], energy=0)
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand == [a]


# ---- where the played card ends up
def test_a_played_attack_goes_to_the_discard_pile():
    s = strike()
    cs = make_state([s])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.discard_pile == [s]
    assert cs.player.exhaust_pile == []

def test_an_exhausting_card_goes_to_the_exhaust_pile_not_the_discard():
    s = slimed()
    cs = make_state([s], draw=[strike()])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.exhaust_pile == [s]
    assert cs.player.discard_pile == []
    assert s not in cs.player.hand

def test_a_power_goes_to_no_pile():
    p = inflame()
    cs = make_state([p])
    CombatSimulator(cs).play_card(0, 0)
    assert p not in all_cards(cs.player)
    assert cs.player.exhaust_pile == []

def test_exhaust_card_removes_it_from_whichever_pile_holds_it():
    for pile in ("hand", "draw_pile", "discard_pile"):
        cs = make_state()
        c = strike()
        getattr(cs.player, pile).append(c)
        cs.player.exhaust_card(c)
        assert c not in getattr(cs.player, pile)
        assert cs.player.exhaust_pile == [c]

def test_exhaust_pile_is_read_from_the_bridge():
    state = {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [], "draw_pile": [],
             "discard_pile": [], "exhaust_pile": [bridge_card()]}
    assert [c.card_id for c in Player.from_dict(state).exhaust_pile] == [CardId.SLIMED]

def test_missing_exhaust_pile_from_the_bridge_means_empty():
    state = {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [], "draw_pile": [], "discard_pile": []}
    assert Player.from_dict(state).exhaust_pile == []

def test_exhaust_pile_is_copied_separately():
    cs = make_state()
    cs.player.exhaust_pile.append(strike())
    clone = CombatState.deepcopy(cs)
    clone.player.exhaust_pile.append(strike())
    assert len(cs.player.exhaust_pile) == 1 and len(clone.player.exhaust_pile) == 2


# ---------------------------------------------------------------- resolve order
def test_card_played_fires_before_the_card_reaches_its_pile():
    import sts2_lite.combat as combat_module
    cs = make_state([strike()])
    c = cs.player.hand[0]
    seen = {}
    sim = CombatSimulator(cs)
    real = sim.fire
    def fire(event, *args):
        if event.name == "CARD_PLAYED":
            seen["in_pile"] = c in cs.player.discard_pile
            seen["in_hand"] = c in cs.player.hand
        return real(event, *args)
    sim.fire = fire
    sim.play_card(0, 0)
    assert seen == {"in_pile": False, "in_hand": False}
    assert c in cs.player.discard_pile

def test_exhaust_event_fires_after_card_played():
    cs = make_state([slimed()])
    sim = CombatSimulator(cs)
    events = []
    real = sim.fire
    sim.fire = lambda event, *a: (events.append(event.name), real(event, *a))[1]
    sim.play_card(0, 0)
    assert events.index("CARD_PLAYED") < events.index("CARD_EXHAUSTED")

def test_non_exhausting_card_fires_no_exhaust_event():
    cs = make_state([strike()])
    sim = CombatSimulator(cs)
    events = []
    real = sim.fire
    sim.fire = lambda event, *a: (events.append(event.name), real(event, *a))[1]
    sim.play_card(0, 0)
    assert "CARD_EXHAUSTED" not in events

def test_illegal_target_restores_the_card_at_its_index():
    cs = make_state([defend(), strike(), defend()])
    c = cs.player.hand[1]
    with pytest.raises(Exception):
        CombatSimulator(cs).play_card(1, 5)
    assert cs.player.hand[1] is c and len(cs.player.hand) == 3
    assert c not in cs.player.discard_pile

def test_tremble_is_exhausted_after_play():
    t = make_card(CardId.TREMBLE, "Tremble", CardType.Skill, 1, TargetType.AnyEnemy)
    cs = make_state([t])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.exhaust_pile == [t] and cs.player.discard_pile == []
    assert cs.enemies[0].status[StatusId.VULNERABLE].amount > 0
