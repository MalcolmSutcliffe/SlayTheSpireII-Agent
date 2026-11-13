import pytest
import re
from sts2_lite.card import Card, CardId, CardType, TargetType, CARD_RARITY, RARE_CARDS, CardRarity, CardKeyword, EnchantmentId, UPGRADE_COST_CHANGE
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.enemy import Enemy
from sts2_lite.player import Player
from sts2_lite.status import StatusId, StatusInstance
from pathlib import Path
from sts2_lite.relic import RelicId


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
                        CardId.DISCOVERY, CardId.ENTROPY, CardId.HIDDEN_GEM, CardId.ALCHEMIZE, CardId.LUMINESCE,
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


DECOMPILED = Path(__file__).resolve().parents[4] / "sts2_decompiled" / "MegaCrit.Sts2.Core.Models.Cards"

def _pascal(card_id : CardId) -> str:
    return "".join(part.capitalize() for part in card_id.name.split("_"))

def test_every_card_has_a_rarity():
    assert set(CARD_RARITY) == set(CardId)

def test_rarity_values_are_rarities():
    assert all(isinstance(r, CardRarity) for r in CARD_RARITY.values())

@pytest.mark.parametrize("cid,rarity", [(CardId.STRIKE_IRONCLAD, CardRarity.Basic), (CardId.DEFEND_IRONCLAD, CardRarity.Basic),
                                        (CardId.BASH, CardRarity.Basic), (CardId.ANGER, CardRarity.Common),
                                        (CardId.INFLAME, CardRarity.Uncommon), (CardId.BARRICADE, CardRarity.Rare),
                                        (CardId.ENTROPY, CardRarity.Rare), (CardId.HIDDEN_GEM, CardRarity.Rare),
                                        (CardId.DAZED, CardRarity.Status), (CardId.WRITHE, CardRarity.Curse),
                                        (CardId.NEOWS_FURY, CardRarity.Ancient), (CardId.TORIC_TOUGHNESS, CardRarity.Event)])
def test_known_rarities(cid, rarity):
    assert CARD_RARITY[cid] == rarity

def test_rare_cards_derive_from_the_table():
    assert RARE_CARDS == {c for c, r in CARD_RARITY.items() if r == CardRarity.Rare}
    assert {CardId.ENTROPY, CardId.HIDDEN_GEM, CardId.BARRICADE} <= RARE_CARDS
    assert not {CardId.BASH, CardId.NEOWS_FURY, CardId.CORRUPTION, CardId.BREAK} & RARE_CARDS

# cards that are in the game but have no class in the decompiled sources (like some potions), so their rarity cannot be checked against it
NOT_IN_DECOMPILED = {CardId.NOT_IMPLEMENTED, CardId.ABUNDANCE}

@pytest.mark.skipif(not DECOMPILED.is_dir(), reason="decompiled sources not present")
def test_matches_decompiled_source():
    missing, wrong = [], []
    for cid, rarity in CARD_RARITY.items():
        path = DECOMPILED / f"{_pascal(cid)}.cs"
        if not path.exists():
            if cid not in NOT_IN_DECOMPILED:
                missing.append(cid.name)
            continue
        found = re.search(r"CardRarity\.(\w+)", path.read_text())
        if not (found and found.group(1) == rarity.name):
            wrong.append((cid.name, rarity.name, found and found.group(1)))
    assert not missing, f"no class in the decompiled sources: {missing}"       # all reported at once, not just the first
    assert not wrong, f"rarity differs from the decompiled source (card, ours, game): {wrong}"


def make(card_id=CardId.STRIKE_IRONCLAD, cost=1):
    c = Card()
    c.card_id, c.name, c.type = card_id, card_id.name, CardType.Attack
    c.energy_cost, c.target_type = cost, TargetType.AnyEnemy
    c.is_upgraded = c.is_unplayable = False
    c.restore_cost = None
    c.enchantment = None
    return c

def test_separate_copies_of_a_card_share_a_signature():
    assert make().signature() == make().signature()

def test_create_copy_keeps_the_signature():
    c = make()
    c.bonus_damage, c.replay, c.restore_cost = 3, 1, 2
    assert Card.create_copy(c).signature() == c.signature()

def test_the_signature_can_be_hashed():
    assert len({make().signature(), make().signature()}) == 1

def mutate_upgrade(c): c.is_upgraded = True
def mutate_cost(c): c.energy_cost = 0
def mutate_unplayable(c): c.is_unplayable = True
def mutate_restore(c): c.restore_cost = 1
def mutate_bonus(c): c.bonus_damage = 2
def mutate_replay(c): c.replay = 1
def mutate_enchant(c): c.enchantment = next(iter(EnchantmentId))
def mutate_enchant_amount(c): c.enchant_amount = 2
def mutate_enchant_bonus(c): c.enchant_bonus = 1
def mutate_keywords(c): c._keywords = c._mask ^ next(iter(CardKeyword)).value
def mutate_id(c): c.card_id = CardId.DEFEND_IRONCLAD

@pytest.mark.parametrize("mutate", [mutate_upgrade, mutate_cost, mutate_unplayable, mutate_restore, mutate_bonus,
                                    mutate_replay, mutate_enchant, mutate_enchant_amount, mutate_enchant_bonus,
                                    mutate_keywords, mutate_id])
def test_every_field_that_changes_how_a_card_plays_changes_the_signature(mutate):
    a, b = make(), make()
    mutate(b)
    assert a.signature() != b.signature()

def test_create_copy_fields_are_all_in_the_signature():
    """A field create_copy carries over but the signature ignores would let different cards be culled as identical."""
    import inspect
    src = inspect.getsource(Card.create_copy)
    copied = {line.split("new_card.")[1].split(" =")[0].split(",")[0] for line in src.splitlines() if "new_card." in line and "=" in line}
    not_in_signature = {"type", "name", "target_type", "guessed_cost"}    # follow from card_id; guessed_cost only says how the cost was read, it never changes a play
    sig_src = inspect.getsource(Card.signature)
    for field in copied - not_in_signature:
        assert field.lstrip("_") in sig_src or field == "_keywords", field


def strike(upgraded=False):
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy, upgraded)

def power(card_id, cost):
    return make_card(card_id, card_id.name.title(), CardType.Power, cost, TargetType.Self)


def test_upgraded_copy_is_marked_and_renamed():
    up = strike().upgraded_copy()
    assert up.is_upgraded and up.name == "Strike+"

def test_upgraded_copy_leaves_the_original_alone():
    c = strike()
    c.upgraded_copy()
    assert not c.is_upgraded and c.name == "Strike"

def test_upgraded_copy_keeps_the_rest_of_the_card():
    c = strike()
    up = c.upgraded_copy()
    assert (up.card_id, up.type, up.target_type, up.energy_cost, up.is_unplayable) == \
        (c.card_id, c.type, c.target_type, 1, False)

def test_name_does_not_gain_a_second_plus():
    c = strike()
    c.name = "Strike+"
    assert c.upgraded_copy().name == "Strike+"

def test_upgraded_card_hits_harder_when_played():
    cs = make_state([strike()], enemy_count=1, enemy_hp=100)
    cs.player.upgrade_card(cs.player.hand[0])
    play(cs)
    assert hps(cs) == [91]

@pytest.mark.parametrize("card_id", sorted(UPGRADE_COST_CHANGE, key=lambda c: c.name))
def test_cards_that_get_cheaper_when_upgraded(card_id):
    base = {CardId.BARRICADE: 3, CardId.CORRUPTION: 3, CardId.DARK_EMBRACE: 2, CardId.STAMPEDE: 2, CardId.UNMOVABLE: 2, CardId.HAVOC: 1,
            CardId.EXPECT_A_FIGHT: 2, CardId.INFERNAL_BLADE: 1, CardId.BODY_SLAM: 1, CardId.HELLRAISER: 2, CardId.MIND_BLAST: 1,
            CardId.AUTOMATION: 1, CardId.MAYHEM: 2, CardId.NOSTALGIA: 1, CardId.CALAMITY: 3,
                CardId.APOTHEOSIS: 2, CardId.ABUNDANCE: 1, CardId.ALCHEMIZE: 1}[card_id]
    assert power(card_id, base).upgraded_copy().energy_cost == base - 1

def test_cost_never_goes_below_zero():
    assert power(CardId.UNMOVABLE, 0).upgraded_copy().energy_cost == 0

def test_x_cost_stays_x():
    c = make_card(CardId.WHIRLWIND, "Whirlwind", CardType.Attack, "X", TargetType.AllEnemies)
    assert c.upgraded_copy().energy_cost == "X"

def test_upgraded_cheaper_card_is_playable_with_less_energy():
    cs = make_state([power(CardId.BARRICADE, 3)], enemy_count=1)
    cs.energy = 2
    sim = CombatSimulator(cs)
    assert sim.get_available_actions() == [{"action": "end_turn"}]
    cs.player.upgrade_card(cs.player.hand[0])
    assert sim.get_available_actions()[0]["action"] == "play_card"

def test_cards_that_cannot_be_upgraded():
    assert not strike(upgraded=True).is_upgradable
    assert not Card.create_dazed().is_upgradable
    assert not Card.create_slimed().is_upgradable
    with pytest.raises(ValueError):
        strike(upgraded=True).upgraded_copy()
    with pytest.raises(ValueError):
        Card.create_wound().upgraded_copy()

def test_player_upgrade_replaces_the_card_where_it_sits():
    cs = make_state([strike(), strike()], enemy_count=1)
    p = cs.player
    p.draw_pile = [strike()]
    p.discard_pile = [strike()]
    p.exhaust_pile = [strike()]
    targets = [p.hand[1], p.draw_pile[0], p.discard_pile[0], p.exhaust_pile[0]]
    for t in targets:
        new = p.upgrade_card(t)
        assert new.is_upgraded and new is not t
    assert [c.is_upgraded for c in p.hand] == [False, True]
    assert p.draw_pile[0].is_upgraded and p.discard_pile[0].is_upgraded and p.exhaust_pile[0].is_upgraded

def test_upgrade_returns_none_for_unupgradable_or_missing_cards():
    cs = make_state([strike(upgraded=True)], enemy_count=1)
    assert cs.player.upgrade_card(cs.player.hand[0]) is None
    assert cs.player.upgrade_card(strike()) is None

def test_upgrade_does_not_leak_into_a_copied_state():
    cs = make_state([strike()], enemy_count=1)
    other = CombatState.deepcopy(cs)
    cs.player.upgrade_card(cs.player.hand[0])
    assert cs.player.hand[0].is_upgraded and not other.player.hand[0].is_upgraded


def card(card_id, cost=1, kind=CardType.Attack, target=TargetType.AnyEnemy, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def with_vigor(cs, amount=8):
    cs.player.apply_status(StatusId.VIGOR, amount)
    cs.player.draw_pile = [defend() for _ in range(10)]
    return cs

def lost(cs, i=0, hp=100):
    return hp - cs.enemies[i].current_hp

def bridge_card(card_id, kind="Attack", target="AnyEnemy", keywords=None):
    d = {"id": card_id, "type": kind, "name": card_id.title(), "can_play": True, "cost": "1", "is_upgraded": False,
         "target_type": target, "description": "", "keywords": []}
    if keywords is not None:
        d["card_keywords"] = keywords
    return d


# ---------------------------------------------------------------- Vigor (VigorPower)
def test_vigor_loads_from_the_bridge():
    assert StatusInstance.from_dict({"id": "VIGOR_POWER", "amount": 8}).status_id == StatusId.VIGOR

def test_vigor_adds_to_the_first_attack_and_is_spent():
    cs = with_vigor(make_state([strike(), strike()], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert lost(cs) == 14 and StatusId.VIGOR not in cs.player.status
    sim.play_card(0, 0)
    assert lost(cs) == 14 + 6

def test_vigor_applies_to_every_hit_of_the_command():
    cs = with_vigor(make_state([card(CardId.TWIN_STRIKE)], enemy_count=1, enemy_hp=100))
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == 2 * (5 + 8)

def test_vigor_applies_to_every_target_of_the_command():
    cs = with_vigor(make_state([card(CardId.THUNDERCLAP, target=TargetType.AllEnemies)], enemy_count=2, enemy_hp=100))
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs, 0) == 12 and lost(cs, 1) == 12

def test_vigor_is_added_before_vulnerable():
    cs = with_vigor(make_state([strike()], enemy_count=1, enemy_hp=100))
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == int((6 + 8) * 1.5)

def test_a_skill_does_not_spend_vigor():
    cs = with_vigor(make_state([defend()], enemy_count=1))
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.status_amount(StatusId.VIGOR) == 8

def test_one_two_punch_replay_is_a_new_command_without_vigor():
    cs = with_vigor(make_state([strike()], enemy_count=1, enemy_hp=100))
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == 14 + 6

def test_a_strike_hellraiser_plays_after_pommel_strike_gets_no_vigor():
    cs = with_vigor(make_state([card(CardId.POMMEL_STRIKE)], enemy_count=1, enemy_hp=100))
    cs.player.draw_pile = [strike()]
    cs.player.apply_status(StatusId.HELLRAISER, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == (9 + 8) + 6

def test_a_refused_attack_keeps_vigor():
    cs = with_vigor(make_state([strike()], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    with pytest.raises(ValueError):
        sim.play_card(0, 5)
    assert sim.vigor_pending is None and cs.player.status_amount(StatusId.VIGOR) == 8


# ---------------------------------------------------------------- keywords (CardKeyword)
def test_canonical_keywords():
    assert Card.create_dazed().ethereal and Card.create_dazed().unplayable
    assert Card.create_slimed().exhausts and not Card.create_slimed().unplayable
    assert Card.create_wound().unplayable
    assert strike().keywords == frozenset()

def test_keywords_load_from_the_bridge():
    c = Card.from_dict(bridge_card("STRIKE_IRONCLAD", keywords=["Ethereal", "Retain"]))
    assert c.keywords == {CardKeyword.ETHEREAL, CardKeyword.RETAIN}

def test_the_bridge_list_replaces_the_canonical_one():
    c = Card.from_dict(bridge_card("TREMBLE", kind="Skill", keywords=[]))
    assert not c.exhausts

def test_without_the_bridge_field_keywords_are_canonical():
    assert Card.from_dict(bridge_card("TREMBLE", kind="Skill")).exhausts

def test_with_keyword_copies_and_keeps_through_upgrade():
    base = strike()
    ethereal = base.with_keyword(CardKeyword.ETHEREAL)
    assert ethereal is not base and not base.ethereal and ethereal.ethereal
    assert ethereal.upgraded_copy().ethereal
    assert ethereal.with_keyword(CardKeyword.ETHEREAL) is ethereal

def test_an_ethereal_card_is_exhausted_at_end_of_turn():
    cs = make_state([strike().with_keyword(CardKeyword.ETHEREAL), strike()], enemy_count=1)
    CombatSimulator(cs).end_turn()
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.STRIKE_IRONCLAD]

def test_a_retained_card_stays_in_hand():
    kept, other = defend().with_keyword(CardKeyword.RETAIN), strike()
    cs = make_state([kept, other], enemy_count=1)
    cs.player.draw_pile = [defend() for _ in range(10)]
    CombatSimulator(cs).end_turn()
    assert kept in cs.player.hand and other in cs.player.discard_pile and len(cs.player.hand) == 6

def test_an_added_unplayable_keyword_blocks_the_card():
    cs = make_state([strike().with_keyword(CardKeyword.UNPLAYABLE)], enemy_count=1)
    sim = CombatSimulator(cs)
    assert sim.get_available_actions() == [{"action": "end_turn"}]

def test_havoc_skips_a_card_made_unplayable():
    cs = make_state([card(CardId.HAVOC, kind=CardType.Skill, target=TargetType.Self)], enemy_count=1, enemy_hp=100)
    cs.player.draw_pile = [strike().with_keyword(CardKeyword.UNPLAYABLE)]
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 and len(cs.player.exhaust_pile) == 1


# ---------------------------------------------------------------- Ghost Seed (GhostSeed.CanAffect)
def ghost_seed_player(keywords=None):
    return Player.from_dict({"max_hp": 80, "hp": 80, "block": 0, "status": [],
                             "hand": [bridge_card("STRIKE_IRONCLAD", keywords=keywords), bridge_card("BASH")],
                             "draw_pile": [bridge_card("DEFEND_IRONCLAD", "Skill", "Self")], "discard_pile": [],
                             "relics": [{"id": "GHOST_SEED", "counter": None, "status": "Normal"}]})

def test_ghost_seed_makes_basic_strikes_and_defends_ethereal():
    pl = ghost_seed_player()
    assert pl.hand[0].ethereal and pl.draw_pile[0].ethereal and not pl.hand[1].ethereal

def test_ghost_seed_agrees_with_bridge_keywords():
    assert ghost_seed_player(keywords=["Ethereal"]).hand[0].keywords == {CardKeyword.ETHEREAL}

def test_ghost_seed_strikes_exhaust_at_end_of_turn():
    cs = make_state([], enemy_count=1)
    cs.player = ghost_seed_player()
    cs.player.max_hp = cs.player.current_hp = 80
    CombatSimulator(cs).end_turn()
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.STRIKE_IRONCLAD]
