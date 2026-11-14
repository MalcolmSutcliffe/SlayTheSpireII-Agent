import json
from pathlib import Path

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState

FIXTURE = Path(__file__).parent / "fixtures" / "headbutt_kill_gremlin_horn.json"


def test_a_kill_draws_for_gremlin_horn_before_headbutt_asks_for_its_card():
    """Game capture: Headbutt+ kills the Punch Construct, Gremlin Horn draws 1 card (from the old draw pile), and only then is the card
    put on top of the draw pile. The sim drew after the pick, so it drew the card that had just been put on top."""
    capture = json.loads(FIXTURE.read_text())
    for seed in range(20):
        rng.seed(seed)
        cs = CombatState.from_dict(capture["before"])
        sim = CombatSimulator(cs)
        for action in capture["actions"]:
            sim.perform_action(action)
        names = lambda pile: [c.card_id.name for c in pile]
        assert "BREAKTHROUGH" not in names(cs.player.hand)
        assert names(cs.player.draw_pile)[0] == "BREAKTHROUGH" or "BREAKTHROUGH" in names(cs.player.draw_pile)
        assert len(cs.player.hand) == 5 and len(cs.player.draw_pile) == 2
        assert {n for n in names(cs.player.hand)} & {"BULLY", "DEFEND_IRONCLAD"}
