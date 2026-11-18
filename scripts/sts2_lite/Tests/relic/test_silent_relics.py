"""The Silent's relics (SilentRelicPool): Helical Dart, Snecko Skull, Tingsha, Tough Bandages (in combat); Ninja Scroll, Twisted Funnel (a fight's opening)."""
import pytest

from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.relic.combat_start import Opening
from sts2_lite.status import StatusId
from sts2_lite.Tests.relic.test_always_on import state


def gen(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim


@pytest.mark.parametrize("bridge_id", ["HELICAL_DART", "SNECKO_SKULL", "TINGSHA", "TOUGH_BANDAGES"])
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id}).relic_id is RelicId[bridge_id]


# ------------------------------------------------------------ Helical Dart
def test_helical_dart_gives_dexterity_for_the_turn_per_shiv():
    cs = state([gen(CardId.SHIV), gen(CardId.SHIV), gen(CardId.SLICE), gen(CardId.DEFEND_SILENT)], RelicId.HELICAL_DART)
    sim = play(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)                     # Slice: no Dexterity
    assert cs.player.status_amount(StatusId.DEXTERITY) == 2
    sim.play_card(0, 0)
    assert cs.player.block == 7
    cs.player.draw_pile = [gen(CardId.DEFEND_SILENT) for _ in range(10)]
    sim.end_turn()
    assert cs.player.status_amount(StatusId.DEXTERITY) == 0 and StatusId.HELICAL_DART not in cs.player.status


# ------------------------------------------------------------ Snecko Skull
@pytest.mark.parametrize("relics, poison", [((), 5), ((RelicId.SNECKO_SKULL,), 6)])
def test_snecko_skull_adds_one_poison(relics, poison):
    cs = state([gen(CardId.DEADLY_POISON)], *relics)
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.POISON) == poison

def test_snecko_skull_counts_once_per_application():
    cs = state([gen(CardId.BOUNCING_FLASK)], RelicId.SNECKO_SKULL)
    cs.energy = 2
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.POISON) == 3 * 4

def test_snecko_skull_before_the_lamp_doubles():
    cs = state([gen(CardId.SNAKEBITE)], RelicId.SNECKO_SKULL, RelicId.UNSETTLING_LAMP)
    cs.energy = 2
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.POISON) == (7 + 1) * 2

def test_snecko_skull_on_power_poison():
    cs = state([gen(CardId.NOXIOUS_FUMES)], RelicId.SNECKO_SKULL, enemies=2)
    sim = play(cs)
    cs.player.draw_pile = [gen(CardId.DEFEND_SILENT) for _ in range(10)]
    sim.end_turn()
    assert all(e.status_amount(StatusId.POISON) == 3 for e in cs.enemies)     # 2 + 1, applied after the enemies' Poison ticked


# ------------------------------------------------------------ Tingsha / Tough Bandages
def test_tingsha_and_tough_bandages_trigger_per_discard():
    cs = state([gen(CardId.SURVIVOR), gen(CardId.STRIKE_SILENT)], RelicId.TINGSHA, RelicId.TOUGH_BANDAGES)
    sim = play(cs)
    assert cs.player.block == 8 + 3
    assert cs.enemies[0].current_hp == 97

def test_end_of_turn_discard_does_not_trigger_tingsha():
    cs = state([gen(CardId.STRIKE_SILENT)], RelicId.TINGSHA)
    cs.player.draw_pile = [gen(CardId.DEFEND_SILENT) for _ in range(10)]
    hp = cs.enemies[0].current_hp
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].current_hp == hp


# ------------------------------------------------------------ the opening of a fight built from a deck
def open_fight(*relic_ids, enemies=1):
    cs = state([], enemies=enemies)
    cs.player.draw_pile = [gen(CardId.DEFEND_SILENT) for _ in range(10)]
    cs.player.relics = {RelicId[r]: RelicInstance(RelicId[r]) for r in relic_ids if r in RelicId.__members__}
    opening = Opening([{"id": r} for r in relic_ids], "monster")
    opening.before_combat(cs)
    opening.before_turn(cs)
    cs.player.opening_hook = opening.before_draw
    sim = CombatSimulator(cs)
    sim._start_player_turn(enemies_start=False)
    opening.after_draw(sim)
    return cs

def test_ninja_scroll_adds_three_shivs_before_the_draw():
    cs = open_fight("NINJA_SCROLL")
    assert [c.card_id for c in cs.player.hand].count(CardId.SHIV) == 3 and len(cs.player.hand) == 8

@pytest.mark.parametrize("relics, poison", [(("TWISTED_FUNNEL",), 4), (("TWISTED_FUNNEL", "SNECKO_SKULL"), 5)])
def test_twisted_funnel_poisons_every_enemy(relics, poison):
    cs = open_fight(*relics, enemies=2)
    assert [e.status_amount(StatusId.POISON) for e in cs.enemies] == [poison, poison]
