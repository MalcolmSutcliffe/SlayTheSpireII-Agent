"""The outcome score: _enemy_progress_left and what _rate_outcome does with it.

A win scores WIN_BASE plus the HP it ended with (potions and max HP counted in HP, a turn costing TURN_COST), as a share of the starting HP.
A loss scores minus the share of the enemies' HP that is left, plus LOSS_TURN_BONUS for each turn it lasted.
Run from scripts/: python -m pytest agents/Tests/test_outcome.py"""
import pytest

from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy import Enemy
from sts2_lite.potion import Potion, PotionId
from sts2_lite.status import StatusId, StatusInstance
from agents.sts2_MCTS.MCTS import (
    DEFAULT_POTION_BONUS, LOSS_TURN_BONUS, MAX_HP_SCALING, MAX_ROLLOUT_TURNS, POTION_BONUS, TURN_COST, WIN_BASE,
    _dormant_hp,
)
from test_mcts import make_state, primed, strike


# ---------------------------------------------------------------- builders
def enemy(hp, max_hp=60, enemy_id="E0", minion=False):
    e = Enemy()
    e.max_hp, e.current_hp, e.enemy_id = max_hp, hp, enemy_id
    e.attack_damage, e.num_attacks = 0, 0
    e.is_minion = minion
    return e

def segment(place, hp, max_hp=50):
    """A living Decimillipede segment (place: FRONT, MIDDLE or BACK)."""
    e = enemy(hp, max_hp, f"DECIMILLIPEDE_SEGMENT_{place}_0")
    e.status = {StatusId.REATTACH: StatusInstance(StatusId.REATTACH, 25)}
    return e

def dead_segment(place, max_hp=50):
    """A killed one, waiting to reattach."""
    return Enemy.dormant_segment(f"DECIMILLIPEDE_SEGMENT_{place}", 9, max_hp)

def fight(*enemies, dormant=(), player_hp=0, turn=0):
    """A fight of these enemies, rated for a searcher that began it with them at the given HP. By default the player is dead on turn 0."""
    cs = make_state([])
    cs.enemies = list(enemies)
    cs.dormant = list(dormant)
    cs.player.current_hp = player_hp
    cs.turn_number = turn
    return cs

def rate(cs, root=None, starting_hp=None):
    """Rate `cs` with a searcher whose fight began at `root` (default: `cs` as it is)."""
    mcts = primed(root or cs, starting_hp=starting_hp)
    return mcts._rate_outcome(cs)

def progress(cs, root=None):
    return primed(root or cs)._enemy_progress_left(cs)

def won(hp=50, max_hp=50, turns=3, potions=(), start=50, start_max=50):
    """Score of a win ending at `hp`/`max_hp` for a fight begun at `start`/`start_max`."""
    cs = make_state([])
    cs.enemies[0].current_hp = 0
    cs.player.current_hp, cs.player.max_hp, cs.turn_number = hp, max_hp, turns
    cs.player.potions = [Potion(p, i) for i, p in enumerate(potions)]
    mcts = primed(cs, starting_hp=start)
    mcts._starting_max_hp = start_max
    return mcts._rate_outcome(cs)


# ---------------------------------------------------------------- _enemy_progress_left
def test_all_enemy_hp_is_left_at_the_start():
    assert progress(fight(enemy(60))) == 1.0

def test_nothing_is_left_when_every_enemy_is_dead():
    root = fight(enemy(60))
    assert progress(fight(enemy(0)), root) == 0.0

def test_damage_dealt_is_the_share_of_the_fights_hp():
    root = fight(enemy(60))
    assert progress(fight(enemy(45)), root) == pytest.approx(0.75)

def test_enemies_count_together():
    root = fight(enemy(60, enemy_id="A"), enemy(20, 20, "B"))
    assert progress(fight(enemy(30, enemy_id="A"), enemy(10, 20, "B")), root) == pytest.approx(40 / 80)

def test_minions_are_not_counted_in_the_total_or_in_what_is_left():
    root = fight(enemy(60), enemy(30, enemy_id="M", minion=True))
    assert primed(root)._expected_total_hp == 60
    assert progress(fight(enemy(60), enemy(30, enemy_id="M", minion=True)), root) == 1.0

def test_a_phrog_parasite_counts_the_wrigglers_it_will_release():
    root = fight(enemy(61, 61, "PHROG_PARASITE_0"))
    assert primed(root)._expected_total_hp == 61 + 4 * 19
    assert progress(root) == 1.0
    assert progress(fight(enemy(1, 61, "PHROG_PARASITE_0")), root) < 1.0


# ---------------------------------------------------------------- dormant Decimillipede segments
def three_segments(front=50, middle=50, back=50):
    return fight(segment("FRONT", front), segment("MIDDLE", middle), segment("BACK", back))

def test_a_killed_segment_is_only_partly_progress_it_comes_back_with_25_hp():
    root = three_segments()
    alive = three_segments(front=40)
    killed = fight(segment("MIDDLE", 50), segment("BACK", 50), dormant=[dead_segment("FRONT")])
    assert progress(killed, root) == pytest.approx((50 + 50 + 25) / 150)
    assert progress(killed, root) < progress(alive, root)      # a kill is still better than 10 damage

def test_killing_a_segment_at_full_hp_gains_less_than_its_hp():
    root = three_segments()
    killed = fight(segment("MIDDLE", 50), segment("BACK", 50), dormant=[dead_segment("FRONT")])
    assert 1.0 - progress(killed, root) == pytest.approx(25 / 150)

def test_a_segment_that_came_back_hurt_counts_what_it_has():
    root = three_segments()
    assert progress(fight(segment("FRONT", 25), segment("MIDDLE", 50), segment("BACK", 50)), root) == pytest.approx(125 / 150)

def test_every_dead_segment_counts_while_one_is_alive():
    root = three_segments()
    two_dead = fight(segment("BACK", 30), dormant=[dead_segment("FRONT"), dead_segment("MIDDLE")])
    assert progress(two_dead, root) == pytest.approx((30 + 25 + 25) / 150)

def test_a_dormant_segment_cannot_return_more_than_its_max_hp():
    cs = fight(segment("BACK", 5), dormant=[dead_segment("FRONT", max_hp=10)])
    assert _dormant_hp(cs) == 10

def test_dead_segments_count_for_nothing_once_the_last_living_one_is_gone():
    """ReattachPower revives a segment only while another one lives: with none left the fight is over."""
    assert _dormant_hp(fight(dormant=[dead_segment("FRONT"), dead_segment("MIDDLE")])) == 0
    assert _dormant_hp(fight(segment("BACK", 0), dormant=[dead_segment("FRONT")])) == 0

def test_a_minion_alone_does_not_keep_the_dead_segments_coming_back():
    assert _dormant_hp(fight(enemy(10, enemy_id="M", minion=True), dormant=[dead_segment("FRONT")])) == 0

def test_dormant_enemies_without_reattach_add_nothing():
    other = enemy(0, enemy_id="OTHER")
    assert _dormant_hp(fight(segment("BACK", 30), dormant=[other])) == 0

def test_the_search_sees_a_real_kill_as_a_segment_that_comes_back():
    """Through the simulator: Strike a nearly dead segment while the others live."""
    cs = fight(segment("FRONT", 6), segment("MIDDLE", 50), segment("BACK", 50), player_hp=50, turn=1)
    cs.player.hand = [strike()]
    root_progress = progress(cs)
    sim = CombatSimulator(cs)
    sim.perform_action({"action": "play_card", "card_index": 0, "target": 0})
    assert len(cs.dormant) == 1 and len(cs.enemies) == 2
    assert progress(cs, root=fight(segment("FRONT", 50), segment("MIDDLE", 50), segment("BACK", 50))) == pytest.approx((50 + 50 + 25) / 150)
    assert root_progress < 1.0


# ---------------------------------------------------------------- losses
def test_a_loss_scores_minus_the_share_of_enemy_hp_left():
    root = fight(enemy(60))
    assert rate(fight(enemy(15)), root) == pytest.approx(-0.25)

def test_less_enemy_hp_left_is_a_better_loss():
    root = fight(enemy(60))
    assert rate(fight(enemy(10)), root) > rate(fight(enemy(30)), root) > rate(fight(enemy(60)), root)

def test_a_killed_segment_is_a_better_loss_than_an_untouched_one_but_not_by_its_whole_hp():
    root = three_segments()
    untouched = rate(three_segments(), root)
    killed = rate(fight(segment("MIDDLE", 50), segment("BACK", 50), dormant=[dead_segment("FRONT")]), root)
    assert killed > untouched
    assert killed - untouched == pytest.approx(25 / 150)

def test_a_dormant_segment_makes_a_loss_worse_than_ignoring_it():
    root = three_segments()
    with_dormant = fight(segment("MIDDLE", 50), segment("BACK", 50), dormant=[dead_segment("FRONT")])
    without = fight(segment("MIDDLE", 50), segment("BACK", 50))
    assert rate(with_dormant, root) < rate(without, root)

def test_when_every_enemy_died_with_the_player_it_is_a_plain_loss():
    root = fight(enemy(60))
    assert rate(fight(enemy(0)), root) == -1.0

def test_the_plain_loss_is_below_any_loss_that_hurt_the_enemy():
    root = fight(enemy(60), enemy(60, enemy_id="E1"))
    assert rate(fight(enemy(0), enemy(0, enemy_id="E1")), root) < rate(fight(enemy(59), enemy(60, enemy_id="E1")), root)

def test_lasting_longer_scores_a_little_better_in_a_loss():
    root = fight(enemy(60))
    early, late = rate(fight(enemy(30), turn=2), root), rate(fight(enemy(30), turn=7), root)
    assert late - early == pytest.approx(5 * LOSS_TURN_BONUS)

def test_an_unfinished_fight_is_rated_like_a_loss():
    cs = fight(enemy(40), player_hp=30, turn=MAX_ROLLOUT_TURNS)
    root = fight(enemy(60))
    assert rate(cs, root) == pytest.approx(-40 / 60 + LOSS_TURN_BONUS * MAX_ROLLOUT_TURNS)


# ---------------------------------------------------------------- wins
def test_a_win_scores_the_hp_it_ended_with_over_the_starting_hp():
    assert won(hp=40, turns=0, start=50) == pytest.approx(WIN_BASE + 40 / 50)

def test_less_hp_lost_is_a_better_win():
    assert won(hp=50) > won(hp=35) > won(hp=1)

def test_each_hp_is_worth_the_same():
    assert won(hp=50) - won(hp=40) == pytest.approx(won(hp=20) - won(hp=10))

def test_each_turn_costs_turn_cost_hp():
    assert won(turns=2) - won(turns=3) == pytest.approx(TURN_COST / 50)

def test_a_kept_potion_is_worth_its_hp():
    kept = won(hp=30, potions=[PotionId.FIRE_POTION]) - won(hp=30)
    assert kept == pytest.approx(DEFAULT_POTION_BONUS / 50)
    assert DEFAULT_POTION_BONUS == 16

def test_a_potion_with_its_own_value_is_worth_that_value():
    potion = next(iter(POTION_BONUS))
    assert won(hp=30, potions=[potion]) - won(hp=30) == pytest.approx(POTION_BONUS[potion] / 50)

def test_potions_add_up():
    two = won(hp=30, potions=[PotionId.FIRE_POTION, PotionId.FIRE_POTION]) - won(hp=30)
    assert two == pytest.approx(2 * DEFAULT_POTION_BONUS / 50)

def test_a_max_hp_gained_is_worth_two_hp():
    assert won(hp=30, max_hp=51) - won(hp=30, max_hp=50) == pytest.approx(MAX_HP_SCALING / 50)
    assert MAX_HP_SCALING == 2.0

def test_a_max_hp_lost_costs_two_hp():
    assert won(hp=30, max_hp=48) - won(hp=30, max_hp=50) == pytest.approx(-2 * MAX_HP_SCALING / 50)

def test_a_kept_potion_is_the_same_as_its_value_in_hp():
    assert won(hp=30, potions=[PotionId.FIRE_POTION], turns=3) == pytest.approx(won(hp=30 + DEFAULT_POTION_BONUS, turns=3))

def test_dead_segments_left_do_not_change_a_win():
    """A win is rated on HP only: enemies that were never beaten cannot appear in it."""
    cs = make_state([])
    cs.enemies = [segment("BACK", 0)]
    cs.dormant = [dead_segment("FRONT")]
    cs.player.current_hp = 40
    cs.turn_number = 3
    plain = make_state([])
    plain.enemies[0].current_hp = 0
    plain.player.current_hp = 40
    plain.turn_number = 3
    assert rate(cs, starting_hp=50) == pytest.approx(rate(plain, starting_hp=50))


# ---------------------------------------------------------------- wins against losses
@pytest.mark.parametrize("enemy_left", [1, 5, 30, 60])
@pytest.mark.parametrize("turns", [0, 10, MAX_ROLLOUT_TURNS, 10 * MAX_ROLLOUT_TURNS])
def test_every_loss_scores_below_every_win(enemy_left, turns):
    root = fight(enemy(60))
    worst_win = won(hp=1, turns=MAX_ROLLOUT_TURNS, start=50)
    assert rate(fight(enemy(enemy_left), turn=turns), root) < worst_win

def test_the_worst_win_still_beats_the_best_unfinished_fight():
    root = fight(enemy(60))
    best_loss = rate(fight(enemy(1), player_hp=50, turn=MAX_ROLLOUT_TURNS), root)
    assert won(hp=1, turns=MAX_ROLLOUT_TURNS, start=50) > best_loss
