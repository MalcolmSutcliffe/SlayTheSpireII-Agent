import json
import pytest
from pathlib import Path
from sts2_lite.card import Card, CardId, CardKeyword, CardType, EnchantmentId, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId
from agents.verify import compare
from sts2_lite.Tests.card.test_card import make_card, make_state, hps
from data_paths import ENCHANTMENTS


DATA = ENCHANTMENTS
E = EnchantmentId

def capture(name):
    return json.loads((DATA / f"{name}.json").read_text())

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.NONE)

def twin_strike():
    return make_card(CardId.TWIN_STRIKE, "Twin Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def enchanted(card, enchantment, amount=0):
    c = Card.create_copy(card)
    c.enchantment, c.enchant_amount = enchantment, amount
    return c

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim


# ------------------------------------------------------------ the bridge's format
def raw_card(**extra):
    return {"index": 0, "id": "STRIKE_IRONCLAD", "name": "Strike", "type": "Attack", "cost": "1", "description": "Deal 6 damage.",
            "target_type": "AnyEnemy", "can_play": True, "is_upgraded": False, "keywords": [], "card_keywords": [], **extra}

def test_the_enchantment_is_read_from_the_bridge_field():
    c = Card.from_dict(raw_card(enchantment={"id": "SHARP", "amount": 2}))
    assert (c.enchantment, c.enchant_amount) == (E.SHARP, 2)
    assert Card.from_dict(raw_card(enchantment=None)).enchantment is None
    assert Card.from_dict(raw_card()).enchantment is None          # an older bridge

def test_every_enchantment_id_is_screaming_snake_case():
    for e in E:
        assert Card.from_dict(raw_card(enchantment={"id": e.name, "amount": 1})).enchantment == e

def test_an_unknown_enchantment_is_ignored_not_fatal(capsys):
    c = Card.from_dict(raw_card(enchantment={"id": "MYSTERY", "amount": 1}))
    assert c.enchantment is None and "unknown enchantment MYSTERY" in capsys.readouterr().out

def test_royally_approved_grants_innate_and_retain():
    c = Card.from_dict(raw_card(enchantment={"id": "ROYALLY_APPROVED", "amount": 1}))
    assert {CardKeyword.INNATE, CardKeyword.RETAIN} <= c.keywords and c.retains

def test_glam_grants_the_replay_keyword_which_a_play_spends():
    c = Card.from_dict(raw_card(enchantment={"id": "GLAM", "amount": 1}))
    assert CardKeyword.REPLAY in c.keywords
    cs = make_state([c], enemy_count=1)
    play(cs)
    assert CardKeyword.REPLAY not in cs.player.discard_pile[0].keywords
    assert hps(cs) == [28]              # 6 twice

def test_a_copy_keeps_the_enchantment():
    c = enchanted(strike(), E.SHARP, 2)
    assert Card.create_copy(c).enchantment == E.SHARP and c.upgraded_copy().enchant_amount == 2


# ------------------------------------------------------------ damage
def damage_of(card, strength=0, enemies=1):
    cs = make_state([card], enemy_count=enemies)
    if strength:
        cs.player.apply_status(StatusId.STRENGTH, strength)
    play(cs)
    return 40 - cs.enemies[0].current_hp

def test_sharp_adds_to_every_hit():
    assert damage_of(enchanted(strike(), E.SHARP, 2)) == 8
    assert damage_of(enchanted(twin_strike(), E.SHARP, 2)) == 2 * (5 + 2)

def test_corrupted_is_half_again_before_strength():
    assert damage_of(enchanted(strike(), E.CORRUPTED, 1)) == 9
    assert damage_of(enchanted(strike(), E.CORRUPTED, 1), strength=2) == 11           # 6 * 1.5 + 2, not (6 + 2) * 1.5
    assert damage_of(enchanted(bash(), E.CORRUPTED, 1)) == 12

def test_instinct_doubles_before_strength():
    assert damage_of(enchanted(strike(), E.INSTINCT, 1)) == 12
    assert damage_of(enchanted(strike(), E.INSTINCT, 1), strength=2) == 14

def test_corrupted_halves_are_kept_until_the_end():
    # Twin Strike: 5 * 1.5 = 7.5 a hit, 7 after Weak-free truncation, twice
    assert damage_of(enchanted(twin_strike(), E.CORRUPTED, 1)) == 14

def test_tezcataras_ember_adds_three():
    assert damage_of(enchanted(strike(), E.TEZCATARAS_EMBER, 1)) == 9

def test_vigorous_is_spent_by_the_first_play():
    cs = make_state([enchanted(strike(), E.VIGOROUS, 4)], enemy_count=1)
    play(cs)
    assert hps(cs) == [30]
    spent = cs.player.discard_pile[0]
    assert (spent.enchantment, spent.enchant_amount) == (E.VIGOROUS, 0)      # the game keeps it, inactive

def test_a_shared_card_is_never_changed_in_place():
    original = enchanted(strike(), E.VIGOROUS, 4)
    cs = make_state([original], enemy_count=1)
    play(cs)
    assert original.enchantment == E.VIGOROUS and original.enchant_amount == 4

def test_momentum_grows_with_each_play():
    cs = make_state([enchanted(strike(), E.MOMENTUM, 3)], enemy_count=1)
    cs.energy = cs.max_energy = 10
    play(cs)
    assert hps(cs) == [34]
    played = cs.player.discard_pile.pop()
    cs.player.hand.append(played)
    play(cs)
    assert hps(cs) == [34 - 9]
    assert cs.player.discard_pile[0].enchant_bonus == 6


# ------------------------------------------------------------ block
def test_nimble_adds_block_before_frail():
    cs = make_state([enchanted(defend(), E.NIMBLE, 2)], enemy_count=1)
    play(cs)
    assert cs.player.block == 7
    cs = make_state([enchanted(defend(), E.NIMBLE, 2)], enemy_count=1)
    cs.player.apply_status(StatusId.FRAIL, 1)
    cs.player.apply_status(StatusId.DEXTERITY, 1)
    play(cs)
    assert cs.player.block == int((5 + 2 + 1) * 0.75)

def test_adroit_is_a_separate_gain_with_its_own_dexterity_and_frail():
    cs = make_state([enchanted(defend(), E.ADROIT, 3)], enemy_count=1)
    play(cs)
    assert cs.player.block == 8
    cs = make_state([enchanted(defend(), E.ADROIT, 3)], enemy_count=1)
    cs.player.apply_status(StatusId.FRAIL, 1)
    play(cs)
    assert cs.player.block == int(5 * 0.75) + int(3 * 0.75)          # 3 + 2, as captured
    cs = make_state([enchanted(defend(), E.ADROIT, 3)], enemy_count=1)
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    play(cs)
    assert cs.player.block == 7 + 5

def test_adroit_triggers_juggernaut_a_second_time():
    cs = make_state([enchanted(defend(), E.ADROIT, 3)], enemy_count=1, enemy_hp=100)
    cs.player.apply_status(StatusId.JUGGERNAUT, 5)
    play(cs)
    assert hps(cs) == [90]

def test_adroit_on_an_attack_blocks_after_the_damage():
    cs = make_state([enchanted(strike(), E.ADROIT, 4)], enemy_count=1)
    play(cs)
    assert cs.player.block == 4 and hps(cs) == [34]

# ------------------------------------------------------------ on play
def test_corrupted_loses_two_hp_after_the_card():
    cs = make_state([enchanted(strike(), E.CORRUPTED, 1)], enemy_count=1)
    play(cs)
    assert cs.player.current_hp == 48

def test_corrupted_rupture_does_not_help_its_own_card():
    cs = make_state([enchanted(bash(), E.CORRUPTED, 1)], enemy_count=1)
    cs.player.apply_status(StatusId.RUPTURE, 2)
    play(cs)
    assert hps(cs) == [28]                                  # 8 * 1.5, not 10 * 1.5
    assert cs.player.status_amount(StatusId.STRENGTH) == 2   # later cards benefit

def test_swift_draws_then_is_lost():
    cs = make_state([enchanted(strike(), E.SWIFT, 2)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), strike()]
    play(cs)
    assert len(cs.player.hand) == 2
    assert cs.player.discard_pile[0].enchant_amount == 0

def test_sown_gives_one_energy_then_is_lost():
    cs = make_state([enchanted(strike(), E.SOWN, 1)], enemy_count=1)
    play(cs)
    assert cs.energy == 3                                   # 3 - 1 + 1
    assert cs.player.discard_pile[0].enchant_amount == 0

def test_sown_is_blocked_by_no_energy_gain():
    cs = make_state([enchanted(strike(), E.SOWN, 1)], enemy_count=1)
    cs.player.apply_status(StatusId.NO_ENERGY_GAIN, 1)
    play(cs)
    assert cs.energy == 2

def test_cards_without_a_combat_effect_play_normally():
    for e in (E.CLONE, E.GOOPY, E.IMBUED, E.INKY, E.SOULS_POWER, E.SPIRAL, E.STEADY, E.PERFECT_FIT, E.SLITHER):
        assert damage_of(enchanted(strike(), e, 1)) == 6


# ------------------------------------------------------------ draw and shuffle
def test_slither_rerolls_the_cost_on_every_draw():
    costs = set()
    for _ in range(80):
        cs = make_state([], enemy_count=1)
        cs.player.draw_pile = [enchanted(strike(), E.SLITHER, 1)]
        card = cs.player.draw_card()
        costs.add(card.energy_cost)
    assert costs == {0, 1, 2, 3}

def test_slither_leaves_x_and_unplayable_costs_alone():
    x = enchanted(make_card(CardId.WHIRLWIND, "Whirlwind", CardType.Attack, "X", TargetType.AllEnemies), E.SLITHER, 1)
    cs = make_state([], enemy_count=1)
    cs.player.draw_pile = [x]
    assert cs.player.draw_card().energy_cost == "X"

def test_perfect_fit_goes_on_top_when_shuffled():
    for _ in range(20):
        cs = make_state([], enemy_count=1)
        cs.player.discard_pile = [strike() for _ in range(6)] + [enchanted(defend(), E.PERFECT_FIT, 1)]
        cs.player.shuffle_discard_into_draw()
        assert cs.player.draw_pile[-1].enchantment == E.PERFECT_FIT and cs.player.known_top == 1
        assert cs.player.draw_card().enchantment == E.PERFECT_FIT

def test_ordinary_shuffles_learn_nothing():
    cs = make_state([], enemy_count=1)
    cs.player.discard_pile = [strike() for _ in range(5)]
    cs.player.shuffle_discard_into_draw()
    assert cs.player.known_top == 0


# ------------------------------------------------------------ captures
def test_capture_corrupted_bash_matches_the_game():
    before, after = capture("corrupted_before_play"), capture("corrupted_after_play")
    cs = CombatState.from_dict(before)
    bash_index = next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.BASH)
    assert cs.player.hand[bash_index].enchantment == E.CORRUPTED
    CombatSimulator(cs).play_card(bash_index, 0)
    assert compare(cs, CombatState.from_dict(after)) == []

def test_capture_adroit_with_frail_gives_three_and_two():
    cs = CombatState.from_dict(capture("adroit"))
    index = next(i for i, c in enumerate(cs.player.hand) if c.enchantment == E.ADROIT)
    CombatSimulator(cs).play_card(index, 0)
    assert cs.player.block == 3 + 2

def test_capture_nimble_defend_gives_seven():
    cs = CombatState.from_dict(capture("corrupted_after_play"))
    index = next(i for i, c in enumerate(cs.player.hand) if c.enchantment == E.NIMBLE)
    CombatSimulator(cs).play_card(index, 0)
    assert cs.player.block == 7

def test_capture_glam_inferno_has_replay():
    cs = CombatState.from_dict(capture("glam"))
    glam = cs.player.hand[0]
    assert glam.enchantment == E.GLAM and CardKeyword.REPLAY in glam.keywords

def test_verify_notices_a_missing_enchantment():
    a = CombatState.from_dict(capture("adroit"))
    b = CombatState.from_dict(capture("adroit"))
    next(c for c in b.player.hand if c.enchantment == E.ADROIT).enchantment = None
    assert any("hand" in d for d in compare(a, b))

def test_capture_momentum_strike_matches_the_game():
    cs = CombatState.from_dict(capture("momentum_before"))
    index = next(i for i, c in enumerate(cs.player.hand) if c.enchantment == E.MOMENTUM)
    assert cs.player.hand[index].enchant_bonus == 0
    CombatSimulator(cs).play_card(index, 0)
    assert compare(cs, CombatState.from_dict(capture("momentum_after"))) == []

def test_capture_momentum_bonus_is_read_back_from_the_card_text():
    cs = CombatState.from_dict(capture("momentum_after"))
    cards = [c for c in cs.player.hand + cs.player.discard_pile if c.enchantment == E.MOMENTUM]
    assert cards and any(c.enchant_bonus == 5 for c in cards)

def test_capture_glam_replay_is_spent_but_enchantment_stays():
    cs = CombatState.from_dict(capture("glam_before"))
    index = next(i for i, c in enumerate(cs.player.hand) if c.enchantment == E.GLAM)
    assert CardKeyword.REPLAY in cs.player.hand[index].keywords
    CombatSimulator(cs).play_card(index, 0)
    played = [c for c in cs.player.discard_pile if c.enchantment == E.GLAM]
    assert played and CardKeyword.REPLAY not in played[0].keywords

def test_spent_vigorous_adds_nothing_on_the_second_play():
    cs = make_state([enchanted(strike(), E.VIGOROUS, 4)], enemy_count=1)
    play(cs)
    cs.player.hand.append(cs.player.discard_pile.pop())
    cs.energy = 3
    play(cs)
    assert hps(cs) == [24]                                  # 6 + 4 (first play), then plain 6 (2 here)

def test_goopy_defend_exhausts_and_grows_by_one_per_play():
    cs = make_state([enchanted(defend(), E.GOOPY, 1)], enemy_count=1)
    play(cs)
    assert cs.player.block == 5
    grown = cs.player.exhaust_pile[0]
    assert grown.enchant_amount == 2
    cs.player.hand.append(grown)
    cs.player.block, cs.energy = 0, 3
    play(cs)
    assert cs.player.block == 6

def test_capture_goopy_block_matches_the_card_text():
    cs = CombatState.from_dict(capture("goopy"))
    goopy = [c for c in cs.player.hand if c.enchantment == E.GOOPY]
    assert goopy and CardKeyword.EXHAUST in goopy[0].keywords
    index, block = cs.player.hand.index(goopy[0]), cs.player.block
    CombatSimulator(cs).play_card(index, 0)
    assert cs.player.block - block == 5 + 0

def test_capture_glam_shrug_it_off_matches_the_game():
    cs = CombatState.from_dict(capture("glam_before"))
    index = next(i for i, c in enumerate(cs.player.hand) if c.enchantment == E.GLAM)
    cs.player.draw_pile.sort(key=lambda c: c.card_id.name)      # the draw order is hidden; the draws are checked as a random step
    CombatSimulator(cs).play_card(index, 0)
    assert compare(cs, CombatState.from_dict(capture("glam_after")), random_step=True) == []
    assert cs.player.block == 16 and cs.energy == 2

def test_glam_replays_the_card_once_and_only_once():
    cs = make_state([enchanted(strike(), E.GLAM, 1)], enemy_count=1)
    cs.player.hand[0]._keywords = cs.player.hand[0]._mask | 128
    play(cs)
    assert hps(cs) == [28]                                  # 6 twice (40 hp)
    spent = cs.player.discard_pile[0]
    assert CardKeyword.REPLAY not in spent.keywords
    cs.player.hand.append(spent)
    cs.energy = 3
    play(cs)
    assert hps(cs) == [22]                                  # once
