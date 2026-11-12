"""Card tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.enemy import Enemy
from sts2_lite.player import Player
from sts2_lite.status import StatusId


# ---------------------------------------------------------------- helpers
def make_card(card_id, name, card_type, cost, target, upgraded=False):
    c = Card()
    c.card_id, c.name, c.type = card_id, name, card_type
    c.energy_cost, c.target_type = cost, target
    c.is_upgraded = upgraded
    c.is_unplayable = False
    return c

def breakthrough(upgraded=False):
    return make_card(CardId.BREAKTHROUGH, "Breakthrough", CardType.Attack, 1, TargetType.AllEnemies, upgraded)

def thunderclap(upgraded=False):
    return make_card(CardId.THUNDERCLAP, "Thunderclap", CardType.Attack, 1, TargetType.AllEnemies, upgraded)

def make_enemy(hp=40, name="E"):
    e = Enemy()
    e.max_hp = e.current_hp = hp
    e.enemy_id = name
    e.attack_damage, e.num_attacks = 0, 0
    return e

def make_state(hand, enemy_count=2, enemy_hp=40):
    p = Player()
    p.max_hp = p.current_hp = 50
    p.hand = list(hand)
    cs = CombatState()
    cs.player = p
    cs.enemies = [make_enemy(enemy_hp, f"E{i}") for i in range(enemy_count)]
    cs.energy = cs.max_energy = 3
    cs.turn_number = 1
    return cs

def play(cs, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(0, target)
    return sim

def hps(cs):
    return [e.current_hp for e in cs.enemies]


# ---------------------------------------------------------------- Breakthrough
def test_breakthrough_hits_every_enemy():
    cs = make_state([breakthrough()], enemy_count=3)
    play(cs)
    assert hps(cs) == [31, 31, 31]

def test_breakthrough_upgraded_damage():
    cs = make_state([breakthrough(upgraded=True)])
    play(cs)
    assert hps(cs) == [27, 27]

def test_breakthrough_ignores_the_target_index():
    cs = make_state([breakthrough()])
    play(cs, target=1)
    assert hps(cs) == [31, 31]

def test_breakthrough_single_enemy():
    cs = make_state([breakthrough()], enemy_count=1)
    play(cs)
    assert hps(cs) == [31]

def test_breakthrough_costs_the_player_1_hp():
    cs = make_state([breakthrough()])
    play(cs)
    assert cs.player.current_hp == 49

def test_breakthrough_hp_loss_ignores_block():
    cs = make_state([breakthrough()])
    cs.player.block = 10
    play(cs)
    assert cs.player.current_hp == 49
    assert cs.player.block == 10

def test_breakthrough_computes_each_enemys_damage_separately():
    cs = make_state([breakthrough()])
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [40 - 13, 40 - 9]            # 9 * 1.5 = 13.5 -> 13

def test_breakthrough_vulnerable_on_the_second_enemy_only():
    cs = make_state([breakthrough()])
    cs.enemies[1].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [40 - 9, 40 - 13]

def test_breakthrough_applies_strength_once_per_enemy():
    cs = make_state([breakthrough()])
    cs.player.apply_status(StatusId.STRENGTH, 2)
    play(cs)
    assert hps(cs) == [29, 29]

def test_breakthrough_weak_applies_once_per_enemy():
    cs = make_state([breakthrough()], enemy_count=3)
    cs.player.apply_status(StatusId.WEAK, 1)
    play(cs)
    assert hps(cs) == [34, 34, 34]                 # 9 * 0.75 = 6.75 -> 6

def test_breakthrough_block_only_protects_its_own_enemy():
    cs = make_state([breakthrough()])
    cs.enemies[0].block = 5
    play(cs)
    assert hps(cs) == [36, 31]
    assert cs.enemies[0].block == 0

def test_breakthrough_skittish_triggers_on_each_enemy():
    cs = make_state([breakthrough()])
    for e in cs.enemies:
        e.apply_status(StatusId.SKITTISH, 4)
    play(cs)
    assert [e.block for e in cs.enemies] == [4, 4]

def test_breakthrough_killing_every_enemy_ends_combat():
    cs = make_state([breakthrough()], enemy_hp=9)
    sim = play(cs)
    assert cs.enemies == []
    assert sim.is_over

def test_breakthrough_killing_one_enemy_leaves_the_rest():
    cs = make_state([breakthrough()])
    cs.enemies[0].current_hp = 9
    sim = play(cs)
    assert [e.enemy_id for e in cs.enemies] == ["E1"]
    assert hps(cs) == [31]
    assert not sim.is_over

def test_breakthrough_costs_energy_and_is_discarded():
    card = breakthrough()
    cs = make_state([card])
    play(cs)
    assert cs.energy == 2
    assert cs.player.discard_pile == [card]


# ---------------------------------------------------------------- Thunderclap
def test_thunderclap_hits_every_enemy():
    cs = make_state([thunderclap()], enemy_count=3)
    play(cs)
    assert hps(cs) == [36, 36, 36]

def test_thunderclap_upgraded_damage():
    cs = make_state([thunderclap(upgraded=True)])
    play(cs)
    assert hps(cs) == [33, 33]

def test_thunderclap_ignores_the_target_index():
    cs = make_state([thunderclap()])
    play(cs, target=1)
    assert hps(cs) == [36, 36]

def test_thunderclap_applies_exactly_one_vulnerable_to_each_enemy():
    cs = make_state([thunderclap()], enemy_count=3)
    play(cs)
    assert [e.status_amount(StatusId.VULNERABLE) for e in cs.enemies] == [1, 1, 1]

def test_thunderclap_stacks_on_existing_vulnerable():
    cs = make_state([thunderclap()])
    cs.enemies[1].apply_status(StatusId.VULNERABLE, 2)
    play(cs)
    assert [e.status_amount(StatusId.VULNERABLE) for e in cs.enemies] == [1, 3]

def test_thunderclap_damage_is_dealt_before_vulnerable_is_applied():
    cs = make_state([thunderclap()])
    play(cs)
    assert hps(cs) == [36, 36]

def test_thunderclap_computes_each_enemys_damage_separately():
    cs = make_state([thunderclap()])
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [40 - 6, 40 - 4]

def test_thunderclap_applies_strength_once_per_enemy():
    cs = make_state([thunderclap()])
    cs.player.apply_status(StatusId.STRENGTH, 3)
    play(cs)
    assert hps(cs) == [33, 33]

def test_thunderclap_block_only_protects_its_own_enemy():
    cs = make_state([thunderclap()])
    cs.enemies[1].block = 3
    play(cs)
    assert hps(cs) == [36, 39]

def test_thunderclap_does_not_cost_the_player_hp():
    cs = make_state([thunderclap()])
    play(cs)
    assert cs.player.current_hp == 50

def test_thunderclap_killing_every_enemy_ends_combat():
    cs = make_state([thunderclap()], enemy_hp=4)
    sim = play(cs)
    assert cs.enemies == []
    assert sim.is_over

def test_thunderclap_costs_energy_and_is_discarded():
    card = thunderclap()
    cs = make_state([card])
    play(cs)
    assert cs.energy == 2
    assert cs.player.discard_pile == [card]


# ---------------------------------------------------------------- illegal plays
def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def test_bad_target_raises():
    cs = make_state([strike()], enemy_count=1)
    with pytest.raises(ValueError):
        play(cs, target=5)

def test_bad_card_index_raises():
    cs = make_state([strike()], enemy_count=1)
    with pytest.raises(IllegalActionError):
        CombatSimulator(cs).play_card(3, 0)

def test_negative_card_index_raises():
    cs = make_state([strike()], enemy_count=1)
    with pytest.raises(IllegalActionError):
        CombatSimulator(cs).play_card(-1, 0)

def test_unaffordable_card_raises():
    cs = make_state([bash()], enemy_count=1)
    cs.energy = 1
    with pytest.raises(IllegalActionError):
        play(cs)

def test_unplayable_card_raises():
    card = strike()
    card.is_unplayable = True
    cs = make_state([card], enemy_count=1)
    with pytest.raises(IllegalActionError):
        play(cs)

@pytest.mark.parametrize("setup", ["bad_target", "unaffordable"])
def test_illegal_play_leaves_state_untouched(setup):
    card = strike() if setup == "bad_target" else bash()
    cs = make_state([card], enemy_count=1)
    cs.player.apply_status(StatusId.FREE_ATTACK, 1) if setup == "bad_target" else setattr(cs, "energy", 1)
    energy = cs.energy
    with pytest.raises(ValueError):
        play(cs, target=5 if setup == "bad_target" else 0)
    assert cs.energy == energy
    assert cs.player.hand == [card]
    assert cs.player.discard_pile == []
    assert hps(cs) == [40]
    assert cs.player.status_amount(StatusId.FREE_ATTACK) == (1 if setup == "bad_target" else 0)

def test_illegal_play_does_not_fire_card_played(monkeypatch):
    cs = make_state([strike()], enemy_count=1)
    sim = CombatSimulator(cs)
    fired = []
    monkeypatch.setattr(sim, "fire", lambda *a: fired.append(a))
    with pytest.raises(ValueError):
        sim.play_card(0, 5)
    assert fired == []

def test_play_after_combat_is_over_is_ignored():
    cs = make_state([strike()], enemy_count=1, enemy_hp=1)
    sim = play(cs)
    assert sim.is_over
    sim.play_card(0, 0)

def test_successful_play_still_costs_energy():
    cs = make_state([strike()], enemy_count=1)
    play(cs, target=0)
    assert cs.energy == 2
    assert hps(cs) == [34]

def test_free_attack_makes_a_successful_attack_free():
    cs = make_state([strike()], enemy_count=1)
    cs.player.apply_status(StatusId.FREE_ATTACK, 1)
    play(cs, target=0)
    assert cs.energy == 3
    assert cs.player.status_amount(StatusId.FREE_ATTACK) == 0

def test_every_generated_action_is_legal():
    import random
    for seed in range(30):
        rng = random.Random(seed)
        cs = make_state([], enemy_count=rng.randint(1, 3))
        cs.player.draw_pile = [rng.choice([strike, defend, bash, breakthrough, thunderclap])()
                               for _ in range(40)]
        sim = CombatSimulator(cs)
        for _ in range(60):
            if sim.is_over:
                break
            sim.perform_action(rng.choice(sim.get_available_actions()))


NEW_POWER_CARDS = tuple(CardId[n] for n in (
    'BARRICADE', 'COLOSSUS', 'CORRUPTION', 'CRUELTY', 'DARK_EMBRACE', 'DEMON_FORM', 'FEEL_NO_PAIN', 'FLAME_BARRIER',
    'JUGGERNAUT', 'JUGGLING', 'ONE_TWO_PUNCH', 'PYRE', 'RAGE', 'RUPTURE', 'STAMPEDE', 'STONE_ARMOR', 'UNMOVABLE', 'VICIOUS',
    'AGGRESSION', 'ARMAMENTS', 'BURNING_PACT', 'HAVOC', 'TRUE_GRIT',
    'BATTLE_TRANCE', 'CASCADE', 'CONFLAGRATION', 'DRUM_OF_BATTLE', 'EXPECT_A_FIGHT', 'FORGOTTEN_RITUAL',
    'HOWL_FROM_BEYOND', 'INFERNAL_BLADE', 'NOT_YET', 'OFFERING', 'PACTS_END',
    'BRAND', 'HELLRAISER', 'INFERNO', 'PRIMAL_FORCE', 'STOKE', 'STOMP'))

UNTARGETED_EVENT = (CardId.EXTERMINATE, CardId.ENLIGHTENMENT, CardId.METAMORPHOSIS, CardId.TORIC_TOUGHNESS)
UNTARGETED_COLORLESS = (CardId.FINESSE, CardId.PRODUCTION, CardId.MASTER_OF_STRATEGY, CardId.DRAMATIC_ENTRANCE, CardId.SHOCKWAVE,
                        CardId.PROWESS, CardId.IMPATIENCE, CardId.RESTLESSNESS, CardId.SCRAWL, CardId.ETERNAL_ARMOR, CardId.PURITY,
                        CardId.ULTIMATE_DEFEND, CardId.VOLLEY, CardId.SECRET_TECHNIQUE, CardId.SECRET_WEAPON, CardId.THINKING_AHEAD,
                        CardId.EQUILIBRIUM, CardId.PANIC_BUTTON, CardId.PROLONG, CardId.FASTEN, CardId.PREP_TIME, CardId.AUTOMATION, CardId.PANACHE,
                        CardId.ROLLING_BOULDER, CardId.THE_BOMB, CardId.THE_GAMBIT, CardId.MAYHEM, CardId.NOSTALGIA,
                        CardId.CALAMITY, CardId.JACK_OF_ALL_TRADES, CardId.CATASTROPHE, CardId.BEAT_DOWN, CardId.ANOINTED,
                        CardId.DISCOVERY, CardId.ENTROPY, CardId.HIDDEN_GEM,
                        CardId.TOXIC, CardId.FRANTIC_ESCAPE, CardId.DISINTEGRATION, CardId.MIND_ROT, CardId.SLOTH, CardId.WASTE_AWAY)

def test_every_single_target_card_rejects_a_bad_target():
    from sts2_lite.card import GET_CARD_FUNCTION
    targeted = [cid for cid, f in GET_CARD_FUNCTION.items()
                if cid not in (CardId.DEFEND_IRONCLAD, CardId.BLOOD_WALL, CardId.SLIMED, CardId.BECKON, CardId.SPORE_MIND,
                               CardId.ABUNDANCE, CardId.APOTHEOSIS, CardId.APPARITION, CardId.BRIGHTEST_FLAME, CardId.RELAX, CardId.WISH,
                               CardId.BREAKTHROUGH, CardId.SHRUG_IT_OFF, CardId.THUNDERCLAP,
                               CardId.INFLAME, CardId.CRIMSON_MANTLE, CardId.IMPERVIOUS, CardId.EVIL_EYE,
                                   CardId.SECOND_WIND, CardId.BLOODLETTING, CardId.WHIRLWIND,
                                   CardId.SWORD_BOOMERANG, *NEW_POWER_CARDS, *UNTARGETED_COLORLESS, *UNTARGETED_EVENT)]
    assert len(targeted) >= 10
    for cid in targeted:
        cs = make_state([make_card(cid, cid.name, CardType.Attack, 1, TargetType.AnyEnemy)], enemy_count=1)
        for bad in (1, -1):
            with pytest.raises(ValueError):
                play(cs, target=bad)
            assert cs.energy == 3, (cid, bad)

def test_card_play_card_returns_nothing_on_success():
    cs = make_state([strike()], enemy_count=1)
    assert cs.player.hand[0].play_card(CombatSimulator(cs), 0) is None


# ---------------------------------------------------------------- hand changes during a play
def test_card_is_removed_by_identity_when_an_earlier_card_leaves_the_hand(monkeypatch):
    from sts2_lite import card as card_module
    first, second, third = strike(), defend(), strike()
    cs = make_state([first, second, third])

    def exhaust_first(card, combat, target_index, is_upgraded=False):
        combat.combat_state.player.exhaust_card(first)

    monkeypatch.setitem(card_module.GET_CARD_FUNCTION, CardId.DEFEND_IRONCLAD, exhaust_first)
    CombatSimulator(cs).play_card(1, 0)
    assert cs.player.hand == [third]
    assert cs.player.discard_pile == [second]

def test_card_is_removed_by_identity_when_cards_are_drawn(monkeypatch):
    from sts2_lite import card as card_module
    played, other = defend(), strike()
    drawn = strike()
    cs = make_state([other, played])
    cs.player.draw_pile = [drawn]

    def draw_one(card, combat, target_index, is_upgraded=False):
        combat.combat_state.player.draw_card()

    monkeypatch.setitem(card_module.GET_CARD_FUNCTION, CardId.DEFEND_IRONCLAD, draw_one)
    CombatSimulator(cs).play_card(1, 0)
    assert cs.player.hand == [other, drawn]
    assert cs.player.discard_pile == [played]

def test_self_exhausting_card_is_not_discarded():
    slimed = make_card(CardId.SLIMED, "Slimed", CardType.Status, 1, TargetType.Self)
    other, drawn = strike(), strike()
    cs = make_state([other, slimed])
    cs.player.draw_pile = [drawn]
    CombatSimulator(cs).play_card(1, 0)
    assert cs.player.hand == [other, drawn]
    assert cs.player.discard_pile == []


def test_a_card_the_player_cannot_afford_right_now_is_not_unplayable_for_good():
    """The bridge flags unaffordable cards (EnergyCostTooHigh); that flag followed them into the discard pile and the rollouts."""
    from sts2_lite.card import Card
    raw = {"id": "DEFEND_IRONCLAD", "name": "Defend", "type": "Skill", "cost": "1", "can_play": False, "unplayable_reason": "EnergyCostTooHigh",
           "is_upgraded": False, "target_type": "Self", "keywords": []}
    assert not Card.from_dict(raw).is_unplayable
    raw["unplayable_reason"] = "HasUnplayableKeyword"
    assert Card.from_dict(raw).is_unplayable
