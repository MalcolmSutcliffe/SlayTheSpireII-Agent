"""The ancients: what each offers, who turns up in which act, and the heal."""
import random

from sts2_lite.campaign import ancients
from sts2_lite.campaign.Tests.test_sandbox import RandomFighter, sim_of
from sts2_lite.event import card_entry
from sts2_lite.run import new_run


def run_of(act=1, ascension=0):
    r = new_run(ascension)
    r.act = act
    return r


def many(name, n=300, **kw):
    out = []
    for i in range(n):
        out.append(ancients.generate(name, run_of(**kw), random.Random(i)))
    return out


def test_every_ancient_offers_three_distinct_relics():
    for name in ancients.GENERATORS:
        for act in (2, 3):
            for offered in many(name, act=act):
                assert len(offered) == 3
                relics = [o.relic for o in offered if o.relic]
                assert len(set(relics)) == len(relics)


def test_neow_offers_two_boons_and_a_curse_last():
    for offered in many("NEOW"):
        assert offered[2].relic in ancients.NEOW_CURSES
        assert all(o.relic not in ancients.NEOW_CURSES for o in offered[:2])
        paired = ancients.NEOW_PAIRED.get(offered[2].relic)
        assert paired not in [o.relic for o in offered[:2]]
    seen = {o.relic for offered in many("NEOW", 600) for o in offered[:2]}
    assert {"LAVA_ROCK", "SMALL_CAPSULE", "NUTRITIOUS_OYSTER", "STONE_HUMIDIFIER", "NEOWS_TALISMAN", "POMANDER"} <= seen


def test_large_capsule_curse_takes_away_the_capsule_boon():
    for offered in many("NEOW", 600):
        if offered[2].relic == "LARGE_CAPSULE":
            assert offered[0].relic != "SMALL_CAPSULE" and offered[1].relic != "SMALL_CAPSULE"


def test_orobas_third_slot_depends_on_the_starter_relic_and_card():
    assert all(o[2].relic in ("TOUCH_OF_OROBAS", "ARCHAIC_TOOTH") for o in many("OROBAS"))
    r = run_of(2)
    r.relics = [{"id": "CIRCLET", "name": "Circlet"}]
    r.deck = [c for c in r.deck if c["id"] != "BASH"]
    offered = ancients.generate("OROBAS", r, random.Random(0))
    assert offered[2].locked
    sea = [o for offered in many("OROBAS", 600) for o in offered if o.relic == "SEA_GLASS"]
    assert sea and all(o.setup["character"] != "IRONCLAD" for o in sea)


def test_pael_options_follow_the_deck():
    r = run_of(2)
    r.relics.append({"id": "BYRDPIP", "name": "Byrdpip"})
    assert all(o[2].relic != "PAELS_LEGION" for o in [ancients.generate("PAEL", r, random.Random(i)) for i in range(100)])
    assert any(o.relic == "PAELS_CLAW" for offered in many("PAEL", act=2) for o in offered)           # four Defends can take Goopy
    assert any(o.relic == "PAELS_TOOTH" for offered in many("PAEL", act=2) for o in offered)           # ten cards can be removed
    small = run_of(2)
    small.deck = small.deck[:4]
    assert all(o.relic not in ("PAELS_TOOTH", "PAELS_CLAW") for i in range(100) for o in ancients.generate("PAEL", small, random.Random(i)))


def test_darv_offers_the_act_relics_and_sometimes_dusty_tome():
    for act, pair in ((2, {"ECTOPLASM", "SOZU"}), (3, {"PHILOSOPHERS_STONE", "VELVET_CHOKER"})):
        relics = {o.relic for offered in many("DARV", act=act) for o in offered}
        assert pair <= relics and "DUSTY_TOME" in relics
        other = {"PHILOSOPHERS_STONE", "VELVET_CHOKER"} if act == 2 else {"ECTOPLASM", "SOZU"}
        assert not relics & other
    tomes = [o for offered in many("DARV", act=2) for o in offered if o.relic == "DUSTY_TOME"]
    assert tomes and all(o.setup["card"] == "CORRUPTION" for o in tomes)


def test_tezcatara_offers_soup_only_with_a_basic_strike():
    r = run_of(2)
    r.deck = [c for c in r.deck if "STRIKE" not in c["id"]]
    assert all(o.relic != "NUTRITIOUS_SOUP" for i in range(100) for o in ancients.generate("TEZCATARA", r, random.Random(i)))
    assert any(o.relic == "NUTRITIOUS_SOUP" for offered in many("TEZCATARA", act=2) for o in offered)


def test_shared_ancient_is_dealt_to_act_two_half_the_time_and_act_three_a_quarter():
    sim = sim_of(RandomFighter(), seed=0)
    counts = {1: 0, 2: 0}
    for seed in range(400):
        sim.game = type(sim.game)(seed)
        sim.deal_shared_ancients()
        for act in (1, 2):
            counts[act] += bool(sim.shared_ancients[act])
        assert not (sim.shared_ancients[1] and sim.shared_ancients[2])
    assert 0.4 < counts[1] / 400 < 0.6 and 0.15 < counts[2] / 400 < 0.35


def test_a_run_starts_at_neow_and_takes_a_relic_from_every_ancient():
    for seed in range(6):
        sim = sim_of(RandomFighter(), seed=seed)
        result = sim.run()
        visits = [v.id for v in result.history if v.room == "Ancient"]
        assert visits[0] == "NEOW" and len(visits) <= 3
        assert len(result.relics) >= 1 + len(visits)         # the starter relic and one from each ancient


def test_later_ancients_heal_and_ascension_two_heals_less():
    sim = sim_of(RandomFighter(), seed=1, ascension=2)
    r = sim.run_state
    r.max_hp, r.hp = 80, 20
    sim.ancient("TANX")
    assert r.hp == 20 + int(60 * 0.8)
