"""How a finished (or unfinished) rollout is scored: the reward the search maximizes.

A won fight scores `reward.win_base` plus the HP it ended with (potions kept and max HP gained counted in HP, each turn costing a little)
as a share of the HP the fight started with. A lost or unfinished one scores minus the share of the enemies' HP still left, so the
search can tell losing lines apart by how close they came. The numbers are RewardParams (params.py)."""
from __future__ import annotations

from sts2_lite.combat import CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.status import StatusId

from agents.sts2_MCTS.params import RewardParams


def rate_outcome(state : CombatState, reward : RewardParams, starting_hp : int, starting_max_hp : int, expected_total_hp : float) -> float:
    """The reward of the fight as it stands in `state`. `starting_hp`, `starting_max_hp` and `expected_total_hp` describe the fight's start."""
    current_hp = state.player.current_hp
    num_turns = state.turn_number
    won = current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in state.enemies)
    max_hp_delta = state.player.max_hp - starting_max_hp
    # if won fight: outcome is best max hp with slight bias towards less turns
    if won:
        hp_score = current_hp
        if not state.final_fight:        # in the last fight a kept potion is of no use later: drinking one costs nothing
            hp_score += sum(reward.potion_bonus.get(p.potion_id, reward.default_potion_bonus) for p in state.player.potions)
            hp_score += reward.max_hp_scaling * max_hp_delta
        hp_score += -reward.turn_cost * num_turns
        return reward.win_base + hp_score / starting_hp         # linear in HP

    # lost or unfinished: minimize the enemy HP that is left, with a small preference for lasting longer
    progress_left = enemy_progress_left(state, expected_total_hp)
    if progress_left == 0:     # every enemy died and so did the player: no better than a plain loss
        return -1.0
    return -progress_left + reward.loss_turn_bonus * num_turns

def enemy_progress_left(state : CombatState, expected_total_hp : float) -> float:
    """The share of the fight's enemy HP that is still to be removed: 1.0 at the start of the fight, 0.0 when nothing is left.

    Counts what the living enemies still carry (`effective_hp`: a Phrog Parasite counts the Wrigglers it will release) and what
    the dead will bring back (`dormant_hp`: a killed Decimillipede segment is not progress, it is back at 25 HP in two turns)."""
    remaining = sum(effective_hp(e) for e in state.enemies) + dormant_hp(state)
    return remaining / max(1, expected_total_hp)

def expected_total_hp(state : CombatState) -> float:
    """The enemy HP there is to remove in the fight at its start (what `enemy_progress_left` is a share of)."""
    total = 0
    for e in state.enemies:
        if e.is_minion:
            continue
        total += e.max_hp
        # edge cases, should probably implement better way to do this in future
        if e.enemy_id.startswith("PHROG_PARASITE"):
            total += 4*(17+21)/2
    return total

def effective_hp(enemy : Enemy) -> float:
    if enemy.is_minion:
        return 0
    hp = enemy.current_hp
    # edge cases
    if enemy.enemy_id.startswith("PHROG_PARASITE"):
        hp += 4 * (17 + 21) / 2
    return hp

def dormant_hp(state : CombatState) -> float:
    """The HP that enemies lying dead (`state.dormant`) will bring back with them.

    A killed Decimillipede segment (ReattachPower) revives with its Reattach amount, but only while another segment is still alive:
    once the last living one is killed the fight is over and the dormant ones count for nothing."""
    if not any(not e.is_minion and e.current_hp > 0 for e in state.enemies):
        return 0
    return sum(min(d.max_hp, d.status[StatusId.REATTACH].amount) for d in state.dormant if StatusId.REATTACH in d.status)
