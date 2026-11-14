"""Enemy-engine hooks used by the Act 2 monsters: Move effects, the generic STUNNED move and reactions to damage.
Run from scripts/: python -m pytest sts2_lite/Tests"""
from sts2_lite import rng
from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.damage import modify_damage
from sts2_lite.enemy import Enemy, STUNNED
from sts2_lite.enemy_moves import Move, Branch
from sts2_lite.hooks import HookType
from sts2_lite.player import Player
from sts2_lite.status import StatusId, StatusInstance


def build(moves, start, *others):
    p = Player()
    p.max_hp = p.current_hp = 80
    e = Enemy()
    e.max_hp = e.current_hp = 50
    e.enemy_id, e.slot = "TEST_0", 0
    e.moves, e.move_id = moves, start
    e.attack_damage, e.num_attacks = moves[start].damage, moves[start].hits
    cs = CombatState()
    cs.player, cs.enemies = p, [e, *others]
    cs.energy = cs.max_energy = 3
    cs.turn_number = 1
    return cs, CombatSimulator(cs), e

def hit(e, cs, damage, powered=True):
    e.apply_damage(damage, cs.player, powered)

def give(c, status_id, amount=1):
    c.status[status_id] = StatusInstance(status_id, amount)

ATTACK = frozenset({"attack"})
IDLE = frozenset({"buff"})


# ---------------------------------------------------------------- Move effects
def test_move_effects_reach_the_player_and_the_team():
    ally = Enemy()
    ally.max_hp, ally.current_hp, ally.enemy_id = 20, 20, "ALLY_0"
    ally.attack_damage = ally.num_attacks = 0
    moves = {"A": Move(IDLE, "A", hand_cards=((CardId.DAZED, 2),), draw_cards=((CardId.DAZED, 1),),
                       team_status=((StatusId.STRENGTH, 3),), heal=10)}
    cs, sim, e = build(moves, "A", ally)
    e.current_hp = 30
    sim._play_enemy_turn()
    assert [c.card_id for c in cs.player.hand] == [CardId.DAZED] * 2
    assert [c.card_id for c in cs.player.draw_pile] == [CardId.DAZED]
    assert e.status_amount(StatusId.STRENGTH) == 3 and ally.status_amount(StatusId.STRENGTH) == 3
    assert e.current_hp == 40

def test_effect_and_choose_callbacks_run():
    seen = []
    moves = {"A": Move(IDLE, "A", effect=lambda e, c: seen.append(e.enemy_id), choose=lambda e, c: "B"),
             "B": Move(IDLE, "B")}
    cs, sim, e = build(moves, "A")
    sim._play_enemy_turn()
    assert seen == ["TEST_0"] and e.move_id == "B"

def test_a_full_hand_sends_added_cards_to_the_discard_pile():
    moves = {"A": Move(IDLE, "A", hand_cards=((CardId.DAZED, 1),))}
    cs, sim, e = build(moves, "A")
    cs.player.hand = [Card.create(CardId.DAZED) for _ in range(10)]
    sim._play_enemy_turn()
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 1

def test_several_summons_are_added_at_once():
    moves = {"A": Move(IDLE, "A", summons=(("WRIGGLER", 0), ("WRIGGLER", 1)))}
    cs, sim, e = build(moves, "A")
    sim._play_enemy_turn()
    assert sorted(x.enemy_id for x in cs.enemies if x is not e) == ["WRIGGLER_0", "WRIGGLER_1"]


# ---------------------------------------------------------------- STUNNED
MOVES = {"HIT": Move(ATTACK, "HIT", damage=9, hits=1), "OTHER": Move(ATTACK, "OTHER", damage=4, hits=2)}

def test_stun_replaces_the_next_move_and_resumes_the_interrupted_one():
    cs, sim, e = build(MOVES, "HIT")
    e.stun()
    assert (e.move_id, e.num_attacks, e.attack_damage) == (STUNNED, 0, 0)
    sim._play_enemy_turn()
    assert cs.player.current_hp == 80
    assert (e.move_id, e.attack_damage, e.num_attacks, e.after_stun) == ("HIT", 9, 1, None)

def test_stun_can_name_the_move_after_it():
    cs, sim, e = build(MOVES, "HIT")
    e.stun("OTHER")
    sim._play_enemy_turn()
    assert e.move_id == "OTHER" and e.num_attacks == 2

def test_stunning_twice_keeps_the_first_follow_up():
    cs, sim, e = build(MOVES, "HIT")
    e.stun("OTHER")
    e.stun()
    assert e.after_stun == "OTHER"

def test_a_stunned_enemy_keeps_its_block_clear_but_loses_nothing_else():
    cs, sim, e = build(MOVES, "HIT")
    e.stun()
    e.block = 5
    sim._play_enemy_turn()
    assert e.block == 0

def test_stunned_move_is_read_from_the_bridge():
    raw = {"entity_id": "NIBBIT_0", "max_hp": 40, "hp": 40, "block": 0, "status": [], "intents": [{"type": "Stun", "label": ""}],
           "move_id": "STUNNED", "follow_up_id": "BUTT_MOVE", "move_log": ["BUTT_MOVE", "STUNNED"]}
    e = Enemy.from_dict(raw)
    assert (e.move_id, e.after_stun) == (STUNNED, "BUTT")
    e.check_against_bridge(raw, Player())       # agreeing with the game is not a mismatch


# ---------------------------------------------------------------- reactions to damage
def test_hard_to_kill_caps_each_hit_even_before_block():
    cs, sim, e = build(MOVES, "HIT")
    give(e, StatusId.HARD_TO_KILL, 12)
    hit(e, cs, 40)
    assert e.current_hp == 38
    e.block = 20
    hit(e, cs, 40)          # capped to 12, all of it blocked
    assert e.current_hp == 38 and e.block == 8

def test_tainted_adds_to_attacks_that_hit_the_player_and_flutter_halves_them():
    cs, sim, e = build(MOVES, "HIT")
    give(cs.player, StatusId.TAINTED, 3)
    assert modify_damage(9, e, cs.player) == 12
    give(e, StatusId.FLUTTER, 3)
    assert modify_damage(10, cs.player, e) == 5

def test_personal_hive_puts_dazed_in_the_draw_pile_for_each_powered_hit():
    cs, sim, e = build(MOVES, "HIT")
    cs.player.draw_pile = [Card.create(CardId.WOUND)] * 3
    give(e, StatusId.PERSONAL_HIVE, 1)
    hit(e, cs, 4)
    hit(e, cs, 4, powered=False)
    assert [c.card_id for c in cs.player.draw_pile].count(CardId.DAZED) == 1

def test_personal_hive_triggers_on_a_fully_blocked_hit_but_not_a_kill():
    cs, sim, e = build(MOVES, "HIT")
    give(e, StatusId.PERSONAL_HIVE, 1)
    e.block = 10
    hit(e, cs, 4)
    assert len(cs.player.draw_pile) == 1
    hit(e, cs, 500)
    assert len(cs.player.draw_pile) == 1

def test_curl_up_gives_block_after_the_card_that_hit():
    cs, sim, e = build(MOVES, "HIT")
    give(e, StatusId.CURL_UP, 7)
    hit(e, cs, 3)
    hit(e, cs, 3)
    assert e.block == 0         # still in the middle of the card
    sim.fire(HookType.CARD_PLAYED, Card.create(CardId.DAZED))
    assert e.block == 7 and StatusId.CURL_UP not in e.status
    hit(e, cs, 3)
    sim.fire(HookType.CARD_PLAYED, Card.create(CardId.DAZED))
    assert e.block == 4         # the 7 absorbed the hit; no second Curl Up

def test_flutter_counts_down_on_unblocked_powered_hits_then_stuns():
    cs, sim, e = build(MOVES, "HIT")
    give(e, StatusId.FLUTTER, 2)
    e.block = 5
    hit(e, cs, 3)               # blocked: no tick
    hit(e, cs, 3, powered=False)
    assert e.status_amount(StatusId.FLUTTER) == 2
    e.block = 0
    hit(e, cs, 3)
    assert e.status_amount(StatusId.FLUTTER) == 1
    hit(e, cs, 3)
    assert StatusId.FLUTTER not in e.status and e.move_id == STUNNED and e.after_stun == "HIT"

def test_slumber_ticks_per_unblocked_hit_and_the_stun_leads_to_the_named_move():
    moves = {"SNORE": Move(IDLE, "SNORE"), "ROLL_OUT": Move(ATTACK, "ROLL_OUT", damage=16, hits=1)}
    cs, sim, e = build(moves, "SNORE")
    give(e, StatusId.SLUMBER, 2)
    hit(e, cs, 1)
    hit(e, cs, 1)
    assert StatusId.SLUMBER not in e.status
    assert e.move_id == STUNNED and e.after_stun == "ROLL_OUT"

def test_burrowed_breaks_with_its_block_and_stuns_into_bite():
    moves = {"BITE": Move(ATTACK, "BITE", damage=13, hits=1), "BURROW": Move(IDLE, "BURROW")}
    cs, sim, e = build(moves, "BURROW")
    give(e, StatusId.BURROWED)
    e.block = 20
    hit(e, cs, 5)
    assert StatusId.BURROWED in e.status and e.block == 15
    hit(e, cs, 15)              # exactly the block: it breaks
    assert StatusId.BURROWED not in e.status and e.block == 0
    assert e.move_id == STUNNED and e.after_stun == "BITE"

def test_burrowed_keeps_its_block_through_its_own_turn():
    moves = {"BURROW": Move(IDLE, "BURROW")}
    cs, sim, e = build(moves, "BURROW")
    give(e, StatusId.BURROWED)
    e.block = 20
    sim._play_enemy_turn()
    assert e.block == 20

def test_imbalanced_attacker_stumbles_after_a_fully_blocked_attack():
    cs, sim, e = build(MOVES, "HIT")
    give(e, StatusId.IMBALANCED)
    cs.player.block = 50
    sim._play_enemy_turn()
    assert cs.player.current_hp == 80
    assert e.move_id == STUNNED and e.after_stun == "HIT"
    sim._play_enemy_turn()
    assert e.move_id == "HIT"
    cs.player.block = 0
    sim._play_enemy_turn()
    assert cs.player.current_hp == 71 and e.move_id == "HIT"       # a hit that lands does not stun
