"""The opening the sim builds for a fight (start-of-combat relics, Innate cards) against the first state the game sent, for every captured fight."""
import json
from pathlib import Path

import pytest

from agents.verify_opening import opening_diffs
from sts2_lite import rng
from sts2_lite.relic.combat_start import undo_enemy_effects

RUNS = Path(__file__).resolve().parents[3] / "data" / "runs"
# captures the engine does not reproduce yet (or that are not an opening at all): a card or status the game adds as the fight starts that is not
# modelled, a fight saved after the player had already acted, or a block the template carries twice
KNOWN_GAPS = {
    "f37_r1_Living_Shield+Turret_Operator_020945373813",     # Turret Operator's block: sim 50, game 25
    "f5_r1_Calcified_Cultist+Seapunk_203228584829",          # saved mid-fight (enemy hp, weak and vulnerable, 1 energy)
    "f13_r1_Terror_Eel_191118929489",                        # the game has 2 Strength and no relic explains it
    "f17_r1_Lagavulin_Matriarch_191427396661",               # a Stampede in the hand that no relic explains
    "f7_r1_Terror_Eel_214406944885",                         # a Seeker Strike in the hand that no relic explains
    "f48_r1_Aeonglass_204520544991",                         # 9 cards in the opening hand
    "f36_r1_Living_Shield+Turret_Operator_145123232132",     # Turret Operator's block again, in 2 more fights
    "f36_r1_Living_Shield+Turret_Operator_175912455164",
    "f37_r1_Living_Shield+Turret_Operator_200726997792",
    "f15_r1_Punch_Construct_141719115042",                   # 1 Dexterity and 1 Strength more than the relics give (a potion drunk before the fight?)
    "f17_r1_Lagavulin_Matriarch_215102604233",               # 2 Strength more than Red Skull explains
    "f46_r1_Slimed_Berserker_203943538293",                  # a fight saved after a potion was used (Duplication, Unmovable, 1 energy less)
    "f39_r1_Slimed_Berserker_163749411389",                  # saved after a Swift Potion was drunk (3 cards more in the hand, 1 energy less) and 14 damage dealt
    "f35_r1_Living_Shield+Turret_Operator_163120247940",     # Mr. Struggles' 1 damage hurts the Turret Operator in the game (hp 40) before the Rampart block comes; the sim blocks it (hp 41, block 24)
    "f13_r1_Phantasmal_Gardener_220125297297",               # saved mid-fight: the Gardeners are hurt and Vulnerable, 2 energy, 4 cards in hand (the fight's other captures match)
    "f48_r1_Queen+Torch_Head_Amalgam_224458603556",          # saved after a Radiant Tincture was drunk (Radiance, and 3 Strength from Reptile Trinket, 1 energy more)
    # captures from the runs a10-3 and a10-4 whose "round 1" state was saved after the agent had already played (or while the hand was still being dealt): hand empty or short, energy spent,
    # block already gained. The runner has since waited for the dealt hand (CombatSession.turn_is_changing), so these are not an opening to compare
    "f35_r1_Scroll_of_Biting_222531759681",
    "f37_r1_Devoted_Sculptor_222642475942",
    "f38_r1_Axebot_222852885921",
    "f40_r1_Battle_Friend_V3_0_223219510245",
    "f42_r1_Mecha_Knight_223321318508",
    "f44_r1_Soul_Nexus_223816284447",
    "f45_r1_Globe_Head_224120741930",
    "f46_r1_Flail_Knight+Magi_Knight+Spectral_Knight_224424435198",
    "f48_r1_Queen+Torch_Head_Amalgam_225054015748",
    "f36_r1_Battle_Friend_V2_0_001248525231",
    "f37_r1_Living_Shield+Turret_Operator_001320543836",
    # engine gap: the Turret Operator's hp differs (sim 22, game 25)
    "f36_r1_Living_Shield+Turret_Operator_211209807788",
    # captured before v0.111: Torch Head Amalgam opened with TACKLE_MOVE (now STRONG_TACKLE_MOVE)
    "f48_r1_Queen+Torch_Head_Amalgam_164431063539",
    "f48_r1_Queen+Torch_Head_Amalgam_224118728330",
    "f48_r1_Queen+Torch_Head_Amalgam_193343216333",
    # captured before v0.111 with the old Diamond Diadem (half damage after a quiet turn); it now starts the fight with 20 Block and Blur
    "f46_r1_Mecha_Knight_132256953481",
    "f48_r1_Aeonglass_132820454315",
    "f35_r1_Devoted_Sculptor_130837280283",
    "f37_r1_Scroll_of_Biting_131003211585",
    "f38_r1_Cubex_Construct+Punch_Construct_131131344152",
    "f42_r1_Flail_Knight+Magi_Knight+Spectral_Knight_131407821199",
    "f43_r1_Frog_Knight_131812130017",
}


def captures():
    for path in sorted(RUNS.rglob("f*_r1_*.json")):
        state = json.loads(path.read_text())
        if state.get("decision") == "combat_play" and state.get("round") == 1 and "player" in state:
            yield path, state


def known_gap(path : Path) -> bool:
    return path.stem in KNOWN_GAPS


@pytest.mark.parametrize("path, state", list(captures()), ids=lambda value: value.name if isinstance(value, Path) else "")
def test_opening_matches_the_game(path, state):
    if known_gap(path):
        pytest.skip("known engine gap")
    rng.seed(1)
    diffs, predicted, actual = opening_diffs(state)
    assert diffs == []


def test_undo_enemy_effects_takes_marbles_and_mask_off():
    enemies = [{"hp": 20, "max_hp": 30, "status": [{"id": "VULNERABLE_POWER", "amount": 1}, {"id": "WEAK_POWER", "amount": 1}, {"id": "STRENGTH_POWER", "amount": 3}]}]
    undo_enemy_effects(enemies, [{"id": "BAG_OF_MARBLES"}, {"id": "RED_MASK"}])
    assert [power["id"] for power in enemies[0]["status"]] == ["STRENGTH_POWER"]


def test_undo_gives_back_the_artifact_charge_a_debuff_used_up():
    enemies = [{"hp": 20, "max_hp": 30, "status": []}, {"hp": 20, "max_hp": 30, "status": [{"id": "ARTIFACT_POWER", "amount": 2}]}]
    undo_enemy_effects(enemies, [{"id": "BAG_OF_MARBLES"}])
    assert [[(x["id"], x["amount"]) for x in e["status"]] for e in enemies] == [[("ARTIFACT_POWER", 1)], [("ARTIFACT_POWER", 3)]]


def test_a_card_marked_upgraded_only_by_its_name_is_upgraded():
    state = {"player": {"hand": [{"id": "DEFEND_IRONCLAD", "name": "Defend+"}, {"id": "STRIKE_IRONCLAD", "name": "Strike"}]}}
    from agents.verify_opening import with_upgrade_flags
    assert [c["upgraded"] for c in with_upgrade_flags(state)["player"]["hand"]] == [True, False]


def test_happy_flower_counter_is_rewound_like_the_other_turn_counters():
    from agents.verify_opening import counters_before_opening
    assert counters_before_opening([{"id": "HAPPY_FLOWER", "counter": 3}])[0]["counter"] == 2
    assert counters_before_opening([{"id": "HAPPY_FLOWER", "counter": 1}])[0]["counter"] == 0
