"""State comparison used by agent_tester to find drift between the sim and the game."""
import json
from pathlib import Path

from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId
from sts2_lite.verify import compare, snapshot, is_random_step

DATA = Path(__file__).parent / "data"

def load(name="relics/spiked_gauntlets.json"):
    return CombatState.from_dict(json.loads((DATA / name).read_text()))

def played(cs, action):
    after = CombatState.deepcopy(cs)
    CombatSimulator(after).perform_action(action)
    return after

def first_play(cs):
    return next(a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "play_card")


def test_a_state_matches_its_own_copy():
    cs = load()
    assert compare(cs, CombatState.deepcopy(cs)) == []

def test_player_and_enemy_differences_are_named():
    cs, other = load(), load()
    other.player.current_hp -= 3
    other.energy -= 1
    other.enemies[0].current_hp -= 5
    other.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    diffs = compare(cs, other)
    assert "player hp: sim 80, game 77" in diffs
    assert any("energy" in d for d in diffs)
    assert any("enemy 0" in d and "hp" in d for d in diffs)
    assert any("VULNERABLE" in d for d in diffs)

def test_a_card_missing_from_the_game_is_reported():
    cs, other = load(), load()
    other.player.discard_pile.append(Card.create_soot())
    assert any("cards owned" in d and "SOOT" in d for d in compare(cs, other))

def test_hand_differences_are_exact_unless_the_step_was_random():
    cs, other = load(), load()
    other.player.hand.append(other.player.draw_pile.pop())      # the game drew a card the sim did not
    assert any(d.startswith("hand") for d in compare(cs, other))
    relaxed = compare(cs, other, random_step=True)
    assert all(not d.startswith(("hand", "draw", "discard")) for d in relaxed)

def test_a_played_card_matches_its_own_reload():
    cs = load()
    predicted = played(cs, first_play(cs))
    assert predicted.energy < cs.energy
    assert compare(predicted, CombatState.deepcopy(predicted)) == []
    assert compare(cs, predicted) != []

def test_end_turn_is_a_random_step_and_a_plain_play_is_not():
    cs = load()
    end = {"action": "end_turn"}
    assert is_random_step(cs, played(cs, end), [end])
    play = first_play(cs)
    assert not is_random_step(cs, played(cs, play), [play])

def test_snapshot_is_plain_data():
    json.dumps(snapshot(load()))


# ---------------------------------------------------------------- randomly rolled HP of a fresh spawn
def _as_wriggler(cs, hp, max_hp):
    enemy = cs.enemies[0]
    enemy.enemy_id, enemy.current_hp, enemy.max_hp = "WRIGGLER_2", hp, max_hp
    return cs

def test_a_fresh_wrigglers_rolled_hp_is_not_a_difference():
    sim, game = _as_wriggler(load(), 19, 19), _as_wriggler(load(), 21, 21)
    assert not any("hp" in d and "enemy" in d for d in compare(sim, game))

def test_a_hatchlings_rolled_hp_is_not_a_difference_but_its_damage_is():
    """A Tough Egg that hatches keeps its id and comes out with 19-22 HP (captured: sim 21, game 20)."""
    def egg(hp, max_hp):
        cs = load()
        cs.enemies[0].enemy_id, cs.enemies[0].current_hp, cs.enemies[0].max_hp = "TOUGH_EGG_0", hp, max_hp
        return cs
    assert not any("hp" in d and "enemy" in d for d in compare(egg(21, 21), egg(20, 20)))
    assert any("hp" in d and "enemy" in d for d in compare(egg(15, 21), egg(20, 20)))

def test_a_hurt_wrigglers_hp_is_still_compared():
    sim, game = _as_wriggler(load(), 15, 19), _as_wriggler(load(), 16, 21)
    assert any("enemy 0 (WRIGGLER_2) hp: sim 15, game 16" in d for d in compare(sim, game))

def test_a_wriggler_outside_the_spawn_range_is_still_compared():
    sim, game = _as_wriggler(load(), 19, 19), _as_wriggler(load(), 30, 30)
    assert any("hp" in d and "WRIGGLER_2" in d for d in compare(sim, game))

def test_other_enemies_hp_is_always_compared():
    sim, game = load(), load()
    game.enemies[0].current_hp = sim.enemies[0].current_hp - 2
    assert any("enemy 0" in d and "hp" in d for d in compare(sim, game))

def test_a_wriggler_hurt_by_the_same_amount_is_not_a_difference():
    """Phrog Parasite dies to Whirlwind's first hit; the Wrigglers it spawns take the other hits: 21-16 vs 17-16."""
    sim, game = _as_wriggler(load(), 5, 21), _as_wriggler(load(), 1, 17)
    assert not any("hp" in d and "enemy" in d for d in compare(sim, game))


# ---------------------------------------------------------------- cards that exhaust a random card
def _hand_with(card_id, upgraded=False):
    from test_cards import make_card, make_state
    from sts2_lite.card import CardType, TargetType
    card = make_card(card_id, "x", CardType.Skill, 1, TargetType.Self)
    card.is_upgraded = upgraded
    return make_state([card], enemy_count=1)

def test_true_grit_is_random_only_when_not_upgraded():
    play = [{"action": "play_card", "card_index": 0, "target": 0}]
    assert is_random_step(_hand_with(CardId.TRUE_GRIT), _hand_with(CardId.TRUE_GRIT), play)
    assert not is_random_step(_hand_with(CardId.TRUE_GRIT, True), _hand_with(CardId.TRUE_GRIT, True), play)

def test_cinder_and_thrash_are_random_steps():
    play = [{"action": "play_card", "card_index": 0, "target": 0}]
    for card_id in (CardId.CINDER, CardId.THRASH):
        assert is_random_step(_hand_with(card_id), _hand_with(card_id), play)


def test_a_random_exhaust_of_another_card_is_not_a_difference_but_a_lost_card_is():
    cs = load()
    sim, game = CombatState.deepcopy(cs), CombatState.deepcopy(cs)
    a, b = sim.player.hand[0], next(c for c in sim.player.hand if (c.card_id, c.is_upgraded) != (sim.player.hand[0].card_id, sim.player.hand[0].is_upgraded))
    sim.player.hand.remove(a); sim.player.exhaust_pile.append(a)
    other = next(c for c in game.player.hand if (c.card_id, c.is_upgraded) == (b.card_id, b.is_upgraded))
    game.player.hand.remove(other); game.player.exhaust_pile.append(other)
    assert any("exhaust pile" in d for d in compare(sim, game))                         # a plain step still reports it
    assert not any(d.startswith(("exhaust pile", "cards owned")) for d in compare(sim, game, random_step=True))
    game.player.exhaust_pile.clear()                                                    # the game lost the card altogether
    assert any(d.startswith("cards owned") for d in compare(sim, game, random_step=True))


# ---------------------------------------------------------------- random targets
def test_a_random_target_only_changes_which_enemy_was_hit():
    cs, other = load(), load()
    cs.enemies.append(CombatState.deepcopy(cs).enemies[0]); other.enemies.append(CombatState.deepcopy(other).enemies[0])
    cs.enemies[0].current_hp -= 5                     # the sim hit the first enemy, the game the second
    other.enemies[1].current_hp -= 5
    assert any("hp" in d for d in compare(cs, other))
    assert compare(cs, other, random_target=True) == []
    other.enemies[1].current_hp -= 1                  # but the damage as a whole is still checked
    assert any("total hp" in d for d in compare(cs, other, random_target=True))

def test_a_random_target_with_one_enemy_is_still_compared_exactly():
    cs, other = load(), load()
    cs.enemies[0].current_hp -= 5
    assert any("hp" in d for d in compare(cs, other, random_target=True))

def test_picking_among_several_enemies_is_counted_and_one_enemy_is_not():
    from sts2_lite import rng
    before = rng.target_rolls
    assert rng.pick_target(["only"]) == "only" and rng.target_rolls == before
    rng.pick_target(["a", "b"])
    assert rng.target_rolls == before + 1


def test_random_targets_that_differ_in_vulnerability_are_matched_by_replaying():
    """Captured: Sword Boomerang's three hits all went to the Crusher in the game; the Rocket has Vulnerable, so the totals differ."""
    from sts2_lite import enemy as enemy_module
    from sts2_lite.verify import some_target_roll_matches
    enemy_module.STRICT_BRIDGE_CHECKS = True
    before = CombatState.from_dict(json.loads((DATA / "act2_hive/kaiser_crab/boomerang_before.json").read_text()))
    after = CombatState.from_dict(json.loads((DATA / "act2_hive/kaiser_crab/boomerang_after.json").read_text()))
    action = {"action": "play_card", "card_index": 0, "target": 0}
    assert some_target_roll_matches(before, [action], after, random_step=False)
    after.enemies[0].current_hp -= 1                    # a wrong amount is still caught
    assert not some_target_roll_matches(before, [action], after, random_step=False, tries=60)
