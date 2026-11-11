"""Colorless cards, group 4: cards that generate or pick cards at random. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, COLORLESS_CARDS, GENERATABLE_CARDS, JACK_POOL, ZERO_COST_POOL, RARE_CARDS
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from test_cards import make_card, make_state, hps
from test_colorless import card, strike, defend

def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def ids(pile):
    return [c.card_id for c in pile]

# ------------------------------------------------------------ Jackpot
def test_jackpot_hits_and_adds_three_free_cards():
    for upgraded, damage in ((False, 25), (True, 30)):
        cs = one_enemy([card(CardId.JACKPOT).upgraded_copy() if upgraded else card(CardId.JACKPOT)], hp=100)
        cs.energy = 3
        play(cs)
        assert hps(cs) == [100 - damage] and len(cs.player.hand) == 3
        for c in cs.player.hand:
            assert c.card_id in ZERO_COST_POOL and c.energy_cost == 0 and c.is_upgraded == upgraded

def test_zero_cost_pool_has_only_cost_zero_ironclad_cards():
    assert ZERO_COST_POOL and all(GENERATABLE_CARDS[c][2] == 0 for c in ZERO_COST_POOL)
    assert CardId.ANGER in ZERO_COST_POOL and CardId.CASCADE not in ZERO_COST_POOL

def test_jackpot_overflow_goes_to_the_discard_pile():
    cs = one_enemy([card(CardId.JACKPOT)] + [defend() for _ in range(8)])
    cs.energy = 3
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 2

# ------------------------------------------------------------ Calamity
def test_calamity_adds_attacks_after_each_attack():
    cs = one_enemy([card(CardId.CALAMITY), strike(), defend()])
    cs.energy = 5
    sim = play(cs)
    assert cs.player.status_amount(StatusId.CALAMITY) == 1
    sim.play_card(1, 0)                 # Defend: nothing
    assert len(cs.player.hand) == 1
    sim.play_card(0, 0)                 # the Strike is replaced by a random Attack
    assert len(cs.player.hand) == 1 and ids(cs.player.hand)[-1] in [c for c, v in GENERATABLE_CARDS.items() if v[1] == CardType.Attack]

def test_calamity_stacks_and_the_power_card_itself_adds_nothing():
    cs = one_enemy([card(CardId.CALAMITY)])
    cs.player.apply_status(StatusId.CALAMITY, 1)
    play(cs)
    assert not cs.player.hand
    cs.player.hand = [strike()]
    cs.energy = 1
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 2         # two stacks: two Attacks

def test_calamity_upgrade_cost():
    assert card(CardId.CALAMITY).upgraded_copy().energy_cost == 2

# ------------------------------------------------------------ Jack of All Trades
def test_jack_of_all_trades_adds_distinct_colorless_cards_and_exhausts():
    assert CardId.JACK_OF_ALL_TRADES not in JACK_POOL and CardId.HAND_OF_GREED not in JACK_POOL
    for _ in range(20):
        cs = one_enemy([card(CardId.JACK_OF_ALL_TRADES).upgraded_copy()])
        play(cs)
        assert len(cs.player.hand) == 2 and len(set(ids(cs.player.hand))) == 2
        assert all(c.card_id in COLORLESS_CARDS for c in cs.player.hand) and cs.player.exhaust_pile

def test_jack_of_all_trades_makes_one_card():
    cs = one_enemy([card(CardId.JACK_OF_ALL_TRADES)])
    play(cs)
    assert len(cs.player.hand) == 1

# ------------------------------------------------------------ Catastrophe
def test_catastrophe_plays_random_cards_from_the_draw_pile():
    cs = one_enemy([card(CardId.CATASTROPHE)], hp=100)
    cs.player.draw_pile = [strike() for _ in range(5)]
    cs.energy = 3
    play(cs)
    assert hps(cs) == [88] and len(cs.player.draw_pile) == 3 and len(cs.player.discard_pile) == 3     # two Strikes and Catastrophe
    assert cs.energy == 1               # the Strikes were free

def test_catastrophe_upgrade_plays_three():
    cs = one_enemy([card(CardId.CATASTROPHE).upgraded_copy()], hp=100)
    cs.player.draw_pile = [strike() for _ in range(5)]
    play(cs)
    assert hps(cs) == [82]

def test_catastrophe_prefers_playable_cards():
    for _ in range(20):
        cs = one_enemy([card(CardId.CATASTROPHE)], hp=100)
        cs.player.draw_pile = [Card.create_dazed(), strike(), Card.create_dazed()]
        play(cs)
        assert len(cs.player.draw_pile) == 2 or hps(cs) == [94]
        assert hps(cs)[0] <= 94

def test_catastrophe_with_only_unplayable_cards_discards_them():
    cs = one_enemy([card(CardId.CATASTROPHE)])
    cs.player.draw_pile = [Card.create_dazed(), Card.create_dazed()]
    play(cs)
    assert not cs.player.draw_pile and len(cs.player.discard_pile) == 3

def test_catastrophe_with_an_empty_draw_pile_does_nothing():
    cs = one_enemy([card(CardId.CATASTROPHE)])
    play(cs)
    assert len(cs.player.discard_pile) == 1

# ------------------------------------------------------------ Beat Down
def test_beat_down_plays_attacks_from_the_discard_pile():
    cs = make_state([card(CardId.BEAT_DOWN)], enemy_count=1, enemy_hp=100)
    cs.player.discard_pile = [strike(), strike(), strike(), strike(), defend()]
    cs.energy = 3
    play(cs)
    assert hps(cs) == [82] and cs.energy == 0
    assert len(cs.player.discard_pile) == 6          # the four Strikes (three replayed), the Defend and Beat Down

def test_beat_down_upgrade_plays_four_and_skips_skills():
    cs = make_state([card(CardId.BEAT_DOWN).upgraded_copy()], enemy_count=1, enemy_hp=100)
    cs.player.discard_pile = [strike() for _ in range(6)] + [defend()]
    play(cs)
    assert hps(cs) == [76]

def test_beat_down_with_fewer_attacks_than_its_count():
    cs = make_state([card(CardId.BEAT_DOWN)], enemy_count=1, enemy_hp=100)
    cs.player.discard_pile = [strike(), defend()]
    play(cs)
    assert hps(cs) == [94]

def test_beat_down_stops_when_the_fight_is_won():
    cs = make_state([card(CardId.BEAT_DOWN)], enemy_count=1, enemy_hp=6)
    cs.player.discard_pile = [strike(), strike(), strike()]
    sim = play(cs)
    assert sim.is_over

def test_beat_down_is_not_manually_targeted():
    assert card(CardId.BEAT_DOWN).target_type.name == "RandomEnemy"

# ------------------------------------------------------------ Anointed
def test_anointed_brings_rares_from_the_draw_pile():
    cs = one_enemy([card(CardId.ANOINTED), defend()])
    rare = lambda: Card.create_generated(CardId.SALVO)
    cs.player.draw_pile = [strike(), rare(), strike(), rare(), rare()]
    play(cs)
    assert ids(cs.player.hand).count(CardId.SALVO) == 3 and len(cs.player.draw_pile) == 2
    assert cs.player.exhaust_pile

def test_anointed_is_limited_by_the_free_space_in_the_hand():
    cs = one_enemy([card(CardId.ANOINTED)] + [defend() for _ in range(7)])
    cs.player.draw_pile = [Card.create_generated(CardId.SALVO) for _ in range(5)]
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.draw_pile) == 2

def test_anointed_upgrade_retains():
    assert not card(CardId.ANOINTED).retains and card(CardId.ANOINTED).upgraded_copy().retains

def test_rare_table_matches_the_game_for_a_few_cards():
    assert {CardId.BARRICADE, CardId.SALVO, CardId.MAYHEM, CardId.THE_GAMBIT} <= RARE_CARDS
    assert not {CardId.STRIKE_IRONCLAD, CardId.BASH, CardId.ANGER, CardId.EQUILIBRIUM, CardId.AUTOMATION} & RARE_CARDS

# ------------------------------------------------------------ the verifier treats these as chance events
def test_verify_tags_random_card_plays_and_calamity_attacks():
    from sts2_lite.verify import is_random_step
    from sts2_lite.combat import CombatState
    cs = one_enemy([card(CardId.JACKPOT), strike()])
    assert is_random_step(cs, cs, [{"action": "play_card", "card_index": 0, "target": 0}])
    assert not is_random_step(cs, cs, [{"action": "play_card", "card_index": 1, "target": 0}])
    cs.player.apply_status(StatusId.CALAMITY, 1)
    assert is_random_step(cs, cs, [{"action": "play_card", "card_index": 1, "target": 0}])

def test_havoc_with_an_unseen_top_card_cannot_be_predicted_but_a_known_top_card_can():
    from sts2_lite.verify import is_unpredictable_step
    from sts2_lite.card import CardType, TargetType
    from sts2_lite.Tests.enemies.test_hive_simple import make_card
    havoc = make_card(CardId.HAVOC, "Havoc", CardType.Skill, 1, TargetType.Self)
    cs = one_enemy([havoc, strike()])
    play = lambda i: [{"action": "play_card", "card_index": i, "target": 0}]
    assert is_unpredictable_step(cs, play(0))
    assert not is_unpredictable_step(cs, play(1))
    cs.player.known_top = 1
    assert not is_unpredictable_step(cs, play(0))
