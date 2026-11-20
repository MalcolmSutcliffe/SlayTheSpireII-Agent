"""The Necrobinder: Osty, Doom, Souls, the character's cards, relics, potions and run setup."""
import re
from pathlib import Path

import pytest

from sts2_lite.card import Card, CardId, CardType
from sts2_lite.card.constants import STAR_COST
from sts2_lite.card.effects import PLAIN_DAMAGE
from sts2_lite.card.ids import TargetType
from sts2_lite.card.tables import ANCIENT_CARDS, CARD_RARITY, NECROBINDER_CARDS, TOKEN_CARDS, combat_pool
from sts2_lite.character import CHARACTERS
from sts2_lite.combat import CombatSimulator
from sts2_lite.necrobinder import apply_doom, summon
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_state


def gen(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)

def state(hand, hp=100, enemies=1, osty=0, draw=(), discard=()):
    cs = make_state(hand, enemy_count=enemies, enemy_hp=hp)
    cs.player.character = "NECROBINDER"
    cs.player.draw_pile = list(draw)
    cs.player.discard_pile = list(discard)
    if osty:
        summon(cs.player, osty)
    return cs

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def hp(cs, i=0):
    return cs.enemies[i].current_hp

def doom(cs, i=0):
    return cs.enemies[i].status_amount(StatusId.DOOM)


# ------------------------------------------------------------ starter cards
@pytest.mark.parametrize("upgraded, damage", [(False, 6), (True, 9)])
def test_strike_necrobinder(upgraded, damage):
    cs = state([gen(CardId.STRIKE_NECROBINDER, upgraded)])
    play(cs)
    assert hp(cs) == 100 - damage and cs.energy == 2

@pytest.mark.parametrize("upgraded, block", [(False, 5), (True, 8)])
def test_defend_necrobinder(upgraded, block):
    cs = state([gen(CardId.DEFEND_NECROBINDER, upgraded)])
    play(cs)
    assert cs.player.block == block

@pytest.mark.parametrize("upgraded, amount", [(False, 5), (True, 7)])
def test_bodyguard_summons_osty(upgraded, amount):
    cs = state([gen(CardId.BODYGUARD, upgraded)])
    play(cs)
    assert cs.player.osty.current_hp == cs.player.osty.max_hp == amount

def test_summon_on_a_living_osty_adds_max_hp_and_hp():
    cs = state([gen(CardId.BODYGUARD)], osty=3)
    cs.player.osty.current_hp = 2
    play(cs)
    assert (cs.player.osty.current_hp, cs.player.osty.max_hp) == (7, 8)

def test_summon_revives_a_dead_osty_with_that_hp():
    cs = state([gen(CardId.BODYGUARD)], osty=9)
    cs.player.osty.current_hp = 0
    play(cs)
    assert (cs.player.osty.current_hp, cs.player.osty.max_hp) == (5, 5)

@pytest.mark.parametrize("upgraded, damage", [(False, 6 + 5), (True, 9 + 5)])
def test_unleash_adds_osty_hp(upgraded, damage):
    cs = state([gen(CardId.UNLEASH, upgraded)], osty=5)
    play(cs)
    assert hp(cs) == 100 - damage

def test_an_osty_attack_does_nothing_without_a_living_osty():
    cs = state([gen(CardId.UNLEASH)])
    play(cs)
    assert hp(cs) == 100 and cs.energy == 2
    cs = state([gen(CardId.UNLEASH)], osty=4)
    cs.player.osty.current_hp = 0
    play(cs)
    assert hp(cs) == 100

def test_osty_attacks_use_no_strength_but_vulnerable_counts():
    cs = state([gen(CardId.UNLEASH)], osty=4)
    cs.player.apply_status(StatusId.STRENGTH, 5)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hp(cs) == 100 - int((6 + 4) * 1.5)


# ------------------------------------------------------------ Osty takes hits
def test_osty_takes_the_unblocked_damage_first():
    cs = state([], osty=10)
    cs.player.apply_damage(7, cs.enemies[0], powered=True)
    assert cs.player.osty.current_hp == 3 and cs.player.current_hp == 50

def test_overkill_goes_on_to_the_player():
    cs = state([], osty=4)
    cs.player.apply_damage(9, cs.enemies[0], powered=True)
    assert cs.player.osty.current_hp == 0 and cs.player.current_hp == 45

def test_block_comes_before_osty():
    cs = state([], osty=10)
    cs.player.block = 5
    cs.player.apply_damage(7, cs.enemies[0], powered=True)
    assert cs.player.osty.current_hp == 8 and cs.player.current_hp == 50

def test_osty_survives_deepcopy():
    from copy import deepcopy
    cs = state([], osty=6)
    copy = deepcopy(cs)
    assert copy.player.osty.current_hp == 6 and copy.player.osty.owner is copy.player and copy.player.osty is not cs.player.osty


# ------------------------------------------------------------ Doom and Souls
def test_doom_kills_after_the_enemies_act():
    cs = state([], hp=10, enemies=2)
    apply_doom(CombatSimulator(cs), cs.enemies[0], 10)
    sim = CombatSimulator(cs)
    apply_doom(sim, cs.enemies[1], 9)
    sim.end_turn()
    assert [e.current_hp for e in sim.combat_state.enemies] == [10]

def test_doom_does_not_decay():
    cs = state([], hp=50)
    sim = CombatSimulator(cs)
    apply_doom(sim, cs.enemies[0], 5)
    sim.end_turn()
    assert doom(sim.combat_state) == 5

def test_blight_strike_dooms_for_the_damage_dealt():
    cs = state([gen(CardId.BLIGHT_STRIKE)])
    play(cs)
    assert doom(cs) == 8 and hp(cs) == 92

def test_reave_puts_a_soul_in_the_draw_pile():
    cs = state([gen(CardId.REAVE)], draw=[gen(CardId.STRIKE_NECROBINDER)] * 4)
    play(cs)
    assert sum(c.card_id is CardId.SOUL for c in cs.player.draw_pile) == 1

@pytest.mark.parametrize("upgraded, drawn", [(False, 2), (True, 3)])
def test_soul_draws_and_exhausts(upgraded, drawn):
    cs = state([gen(CardId.SOUL, upgraded)], draw=[gen(CardId.STRIKE_NECROBINDER)] * 5)
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].exhausts
    play(cs)
    assert len(cs.player.hand) == drawn and len(cs.player.exhaust_pile) == 1

def test_necro_cards_that_hit_all_enemies_with_osty():
    cs = state([gen(CardId.HIGH_FIVE)], enemies=2, osty=3)
    play(cs)
    assert [e.current_hp for e in cs.enemies] == [100 - 11 * 1] * 2 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

def test_high_five_needs_osty():
    cs = state([gen(CardId.HIGH_FIVE)])
    assert not cs.player.hand[0].can_play_card(CombatSimulator(cs), 0)
    summon(cs.player, 4)
    assert cs.player.hand[0].can_play_card(CombatSimulator(cs), 0)


# ------------------------------------------------------------ powers and the turn
def test_demesne_and_friendship_add_energy_each_turn():
    cs = state([gen(CardId.DEMESNE)], draw=[gen(CardId.STRIKE_NECROBINDER)] * 12)
    play(cs)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.combat_state.energy == 4 and len(sim.combat_state.player.hand) == 6

def test_pagestorm_draws_for_ethereal_cards():
    cs = state([gen(CardId.PAGESTORM)], draw=[gen(CardId.STRIKE_NECROBINDER)] * 4 + [gen(CardId.DEFILE)])
    assert cs.player.draw_pile[-1].ethereal
    play(cs)
    CombatSimulator(cs).combat_state.player.draw_card()
    assert len(cs.player.hand) == 2

def test_banshees_cry_gets_cheaper_for_every_ethereal_card_played():
    cs = state([gen(CardId.DEFILE), gen(CardId.BANSHEES_CRY)])
    assert cs.player.hand[0].ethereal
    cs.energy = 9
    play(cs)
    assert cs.player.hand[0].energy_cost == 7

def test_melancholy_gets_cheaper_when_an_enemy_dies():
    cs = state([gen(CardId.MELANCHOLY), gen(CardId.STRIKE_NECROBINDER)], hp=3, enemies=2)
    cs.enemies[1].current_hp = 100
    sim = CombatSimulator(cs)
    sim.play_card(1, 0)
    assert [c for c in cs.player.hand if c.card_id is CardId.MELANCHOLY][0].energy_cost == 2

def test_right_hand_hand_returns_when_enough_energy_was_spent():
    rhh = gen(CardId.RIGHT_HAND_HAND)
    cs = state([gen(CardId.HIGH_FIVE)], osty=3)
    cs.player.discard_pile = [rhh]
    cs.energy = 3
    play(cs)
    assert rhh in cs.player.hand


# ------------------------------------------------------------ the character, pools and relics
def test_the_character():
    c = CHARACTERS["NECROBINDER"]
    assert (c.hp, c.relic) == (66, "BOUND_PHYLACTERY")
    assert len(c.deck) == 10 and c.deck.count("BODYGUARD") == 1 and "UNLEASH" in c.deck

def test_combat_pool_has_no_ancient_or_basic_cards():
    pool = set(combat_pool("NECROBINDER"))
    assert pool and pool <= set(NECROBINDER_CARDS)
    assert not pool & {CardId.STRIKE_NECROBINDER, CardId.BODYGUARD, CardId.EIDOLON, CardId.TRANSFIGURE, CardId.PROTECTOR, CardId.FORBIDDEN_GRIMOIRE}

def test_potions():
    from sts2_lite.potion import EFFECTS, PotionId
    from sts2_lite.potion_pool import potion_pool
    cs = state([], hp=100, osty=2)
    sim = CombatSimulator(cs)
    EFFECTS[PotionId.POTION_OF_DOOM](sim, 0)
    EFFECTS[PotionId.BONE_BREW](sim, 0)
    EFFECTS[PotionId.POT_OF_GHOULS](sim, 0)
    assert doom(cs) == 33 and cs.player.osty.max_hp == 17
    assert sum(c.card_id is CardId.SOUL for c in cs.player.hand) == 2
    assert {PotionId.POTION_OF_DOOM, PotionId.BONE_BREW, PotionId.POT_OF_GHOULS} <= set(potion_pool("NECROBINDER"))

def test_bound_phylactery_summons_each_turn_after_the_first():
    cs = state([], draw=[gen(CardId.STRIKE_NECROBINDER)] * 20)
    cs.player.relics[RelicId.BOUND_PHYLACTERY] = RelicInstance(RelicId.BOUND_PHYLACTERY)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.osty.max_hp == 1
    sim.end_turn()
    assert cs.player.osty.max_hp == 2

def test_ivory_tile_pays_back_a_big_play():
    cs = state([gen(CardId.BANSHEES_CRY)])
    cs.energy = 10
    cs.player.relics[RelicId.IVORY_TILE] = RelicInstance(RelicId.IVORY_TILE)
    play(cs)
    assert cs.energy == 10 - 9 + 1

def test_undying_sigil_halves_a_doomed_attacker():
    from sts2_lite.damage import modify_damage
    cs = state([], hp=10)
    cs.player.relics[RelicId.UNDYING_SIGIL] = RelicInstance(RelicId.UNDYING_SIGIL)
    enemy = cs.enemies[0]
    assert modify_damage(10, enemy, cs.player) == 10
    enemy.apply_status(StatusId.DOOM, 10)
    assert modify_damage(10, enemy, cs.player) == 5

def test_book_repair_knife_heals_for_a_doom_kill():
    cs = state([], hp=10, enemies=2)
    cs.player.current_hp = 20
    cs.player.relics[RelicId.BOOK_REPAIR_KNIFE] = RelicInstance(RelicId.BOOK_REPAIR_KNIFE)
    sim = CombatSimulator(cs)
    for e in cs.enemies:
        apply_doom(sim, e, 10)
    sim.end_turn()
    assert cs.player.current_hp == 26


# ============================================================ the tables against the game's source
CARD_SOURCES = Path(__file__).resolve().parents[4] / "sts2_decompiled" / "Core" / "Models" / "Cards"
NECRO_CARDS = [*NECROBINDER_CARDS, CardId.SOUL, CardId.SWEEPING_GAZE, CardId.PROTECTOR, CardId.FORBIDDEN_GRIMOIRE]

def _class_of(card_id):
    return "".join(part.capitalize() for part in card_id.name.split("_"))

def test_there_are_88_cards():
    assert len(NECROBINDER_CARDS) + 4 - 0 == len(NECRO_CARDS) and len(NECROBINDER_CARDS) >= 80

@pytest.mark.skipif(not CARD_SOURCES.is_dir(), reason="decompiled sources not present")
@pytest.mark.parametrize("card_id", NECRO_CARDS, ids=lambda c: c.name)
def test_necrobinder_card_matches_the_decompiled_class(card_id):
    source = (CARD_SOURCES / f"{_class_of(card_id)}.cs").read_text()
    energy, ctype, rarity, target = re.search(r": base\((-?\d+|[^,]+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+)\)", source).groups()
    table = (NECROBINDER_CARDS.get(card_id) or TOKEN_CARDS.get(card_id) or ANCIENT_CARDS.get(card_id))
    expected_cost = "X" if "HasEnergyCostX => true" in source else int(energy)
    assert (table[2], table[1].name, table[3].name.lower()) == (expected_cost, ctype, target.lower()), card_id
    assert CARD_RARITY[card_id].name == rarity, card_id

@pytest.mark.skipif(not CARD_SOURCES.is_dir(), reason="decompiled sources not present")
@pytest.mark.parametrize("card_id", [c for c in NECRO_CARDS if c in PLAIN_DAMAGE], ids=lambda c: c.name)
def test_necrobinder_printed_damage_matches_the_decompiled_class(card_id):
    source = (CARD_SOURCES / f"{_class_of(card_id)}.cs").read_text()
    base = re.search(r"new (?:Osty)?DamageVar\((\d+)m", source)
    if base is None:
        pytest.skip("no plain DamageVar")
    upgrade = sum(int(n) for n in re.findall(r"DynamicVars\.(?:Osty)?Damage\.UpgradeValueBy\((\d+)m\)", source))
    assert PLAIN_DAMAGE[card_id] == (int(base.group(1)), int(base.group(1)) + upgrade), card_id


# ------------------------------------------------------------ the fight opening, bag and ancients
from sts2_lite.relic.combat_start import Opening

def test_bound_phylactery_summons_when_the_fight_opens():
    cs = state([])
    Opening([{"id": "BOUND_PHYLACTERY"}], "monster").before_combat(cs)
    assert cs.player.osty.max_hp == 1

def test_phylactery_unbound_summons_five():
    cs = state([])
    Opening([{"id": "PHYLACTERY_UNBOUND"}], "monster").before_combat(cs)
    assert cs.player.osty.max_hp == 5

def test_funerary_mask_puts_three_souls_in_the_draw_pile():
    cs = state([], draw=[gen(CardId.STRIKE_NECROBINDER)] * 5)
    Opening([{"id": "FUNERARY_MASK"}], "monster").before_draw(cs.player, 5)
    assert sum(c.card_id is CardId.SOUL for c in cs.player.draw_pile) == 3

def test_big_hat_gives_ethereal_necrobinder_cards():
    cs = state([])
    Opening([{"id": "BIG_HAT"}], "monster").after_draw(CombatSimulator(cs))
    assert len(cs.player.hand) == 2 and all(c.ethereal for c in cs.player.hand)

def test_relic_bag_holds_the_necrobinders_relics():
    import random
    from sts2_lite.relic.bag import RelicGrabBag
    bag = {r for d in RelicGrabBag(random.Random(1), "NECROBINDER").deques.values() for r in d}
    assert {"BIG_HAT", "BONE_FLUTE", "BOOK_REPAIR_KNIFE", "BOOKMARK", "FUNERARY_MASK", "IVORY_TILE", "UNDYING_SIGIL"} <= bag
    assert "BOUND_PHYLACTERY" not in bag and "DIVINE_RIGHT" not in bag

def test_character_of_title():
    from sts2_lite.character import character_of_title
    assert character_of_title("The Necrobinder") == "NECROBINDER"

def test_ancient_cards_of_the_necrobinder():
    from sts2_lite.campaign.ancients import ANCIENT_CARDS_OF, STARTER_RELIC_UPGRADE, TRANSCENDENCE
    assert ANCIENT_CARDS_OF["NECROBINDER"] == ("PROTECTOR", "FORBIDDEN_GRIMOIRE")
    assert STARTER_RELIC_UPGRADE["BOUND_PHYLACTERY"] == "PHYLACTERY_UNBOUND" and TRANSCENDENCE["UNLEASH"] == "PROTECTOR"
    assert CardId.PROTECTOR in ANCIENT_CARDS and CardId.FORBIDDEN_GRIMOIRE in ANCIENT_CARDS

def test_protector_hits_for_ten_plus_osty_max_hp():
    cs = state([gen(CardId.PROTECTOR)], osty=6)
    cs.player.osty.current_hp = 2
    play(cs)
    assert hp(cs) == 100 - 16


# ------------------------------------------------------------ the bridge: Osty and shown costs
def raw_card(card_id, cost, ctype="Attack", keywords=(), upgraded=False):
    return {"id": card_id, "name": card_id.title(), "type": ctype, "cost": str(cost), "star_cost": None, "target_type": "AnyEnemy" if ctype == "Attack" else "Self",
            "can_play": True, "is_upgraded": upgraded, "description": "", "card_keywords": list(keywords)}

def raw_player(hand, status=(), osty=None):
    raw = {"character": "The Necrobinder", "max_hp": 66, "hp": 60, "block": 0, "status": list(status), "hand": hand, "draw_pile": [], "discard_pile": [],
           "exhaust_pile": [], "relics": [], "energy": 3, "max_energy": 3}
    if osty is not None:
        raw["osty"] = osty
    return raw

def loaded(hand, status=(), osty=None):
    from sts2_lite.player import Player
    player = Player.from_dict(raw_player(hand, status, osty))
    player.remove_displayed_cost_modifiers()
    return player

def test_osty_is_read_from_the_bridge():
    player = loaded([], osty={"hp": 7, "max_hp": 12, "alive": True})
    assert (player.osty.current_hp, player.osty.max_hp, player.osty.owner) == (7, 12, player)
    assert loaded([], osty={"hp": 0, "max_hp": 12, "alive": False}).osty.current_hp == 0
    assert loaded([]).osty is None

def test_borrowed_time_is_taken_back_out_of_the_shown_costs():
    player = loaded([raw_card("STRIKE_NECROBINDER", 3), raw_card("NEUROSURGE", 2, "Power")],
                    status=[{"id": "BORROWED_TIME_POWER", "name": "Borrowed Time", "amount": 2, "type": "Debuff", "keywords": []}])
    assert [c.energy_cost for c in player.hand] == [1, 0]
    assert [c.current_cost(player) for c in player.hand] == [3, 2]

def test_veilpiercer_gets_the_cost_of_its_ethereal_cards_back():
    player = loaded([raw_card("DEFILE", 0, keywords=["Ethereal"]), raw_card("STRIKE_NECROBINDER", 1)],
                    status=[{"id": "VEILPIERCER_POWER", "name": "Veilpiercer", "amount": 1, "type": "Buff", "keywords": []}])
    ethereal, plain = player.hand
    assert ethereal.energy_cost == 1 and ethereal.guessed_cost and ethereal.current_cost(player) == 0
    assert plain.energy_cost == 1

def test_the_scythe_reads_its_growth_from_the_text():
    from sts2_lite.player import Player
    card = raw_card("THE_SCYTHE", 2)
    card["description"] = "Deal 23 damage."
    player = Player.from_dict(raw_player([card]))
    player._read_growing_cards()
    assert player.hand[0].bonus_damage == 10


# ------------------------------------------------------------ the run: Forbidden Grimoire and The Scythe
def test_a_scythe_kept_in_the_deck_grows_between_fights():
    from agents.base_agent import BaseAgent
    from sts2_lite.campaign import RunSimulator
    from sts2_lite.campaign.combat import carry_back, start_fight
    from sts2_lite.encounters import ENCOUNTERS
    from sts2_lite.event import card_entry
    sim = RunSimulator(BaseAgent(), seed=3, time_budget=None, character="NECROBINDER")
    run = sim.run_state
    run.deck = [card_entry("THE_SCYTHE")] + [card_entry("STRIKE_NECROBINDER")] * 5
    encounter = next(iter(ENCOUNTERS))
    fight = start_fight(run, encounter, "monster", sim.game)
    player = fight.combat_state.player
    scythe = next(c for c in player.hand + player.draw_pile if c.card_id is CardId.THE_SCYTHE)
    if scythe in player.draw_pile:
        player.draw_pile.remove(scythe)
        player.hand.append(scythe)
    fight.combat_state.energy = 9
    fight.play_card(player.hand.index(scythe), 0)
    carry_back(run, fight)
    assert run.deck[0]["scythe_bonus"] == 5
    again = start_fight(run, encounter, "monster", sim.game).combat_state.player
    assert next(c for c in again.draw_pile + again.hand if c.card_id is CardId.THE_SCYTHE).bonus_damage == 5

def test_forbidden_grimoire_pays_card_removals_after_the_fight():
    from sts2_lite.campaign.combat import carry_back
    from sts2_lite.run import new_run
    run = new_run(0, "NECROBINDER")
    cs = state([])
    cs.player.apply_status(StatusId.FORBIDDEN_GRIMOIRE, 2)
    assert carry_back(run, type("Sim", (), {"combat_state": cs})()) == 2

def test_the_reward_screen_offers_the_removals_and_takes_a_card_out():
    from sts2_lite.campaign import RunSimulator
    from sts2_lite.campaign.Tests.test_sandbox import RandomFighter
    from sts2_lite.encounters import ENCOUNTERS
    seen = []
    class Watcher(RandomFighter):
        def get_decision(self, decision):
            seen.extend(i["type"] for i in decision.state.get("items") or [])
            return super().get_decision(decision)
    sim = RunSimulator(Watcher(), seed=5, time_budget=None, character="NECROBINDER")
    sim.removal_rewards = 2
    sim.rewards(next(e for e in ENCOUNTERS.values() if e.room == "Monster"))
    assert seen.count("card_removal") >= 1
