"""IllusionPower: a monster that comes back keeps its buffs (the Strength The Obscura's Wail gave it) and loses its debuffs."""
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_enemy, make_state


def test_a_revived_parafright_keeps_its_strength_and_loses_its_vulnerable():
    cs = make_state([], enemy_count=0)
    parafright = Enemy.spawn("PARAFRIGHT", 0, 0)
    obscura = make_enemy(123, "THE_OBSCURA_0")
    cs.enemies = [parafright, obscura]
    parafright.apply_status(StatusId.STRENGTH, 3)
    parafright.apply_status(StatusId.VULNERABLE, 2)
    sim = CombatSimulator(cs)
    parafright.current_hp = 0
    sim.resolve_deaths()
    sim._revive()
    back = next(e for e in cs.enemies if e.enemy_id == "PARAFRIGHT_0")
    assert back.current_hp == back.max_hp
    assert back.status[StatusId.STRENGTH].amount == 3
    assert StatusId.VULNERABLE not in back.status
    assert StatusId.ILLUSION in back.status


def test_dampened_cards_are_matched_up_from_the_state_before():
    from sts2_lite.card import CardId
    from sts2_lite.status import downgrade_cards
    from sts2_lite.Tests.card.test_card import make_card, strike
    from sts2_lite.card import CardType, TargetType
    anger = lambda up: make_card(CardId.ANGER, "Anger", CardType.Attack, 0, TargetType.AnyEnemy, up)
    before = make_state([anger(True), strike()], enemy_count=1)
    after = CombatState.deepcopy(before)            # what the game shows once Dampen is on: every upgraded card plain, no memory of it
    after.player.hand = [anger(False), strike()]
    after.player.apply_status(StatusId.DAMPEN, 1)
    after.carry_dampened_cards(before)
    assert after.player.hand[0].dampened_from is before.player.hand[0]
    assert after.player.hand[1].dampened_from is None
