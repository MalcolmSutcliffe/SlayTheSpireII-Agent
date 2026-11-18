"""How a finished (or unfinished) rollout is scored: the reward the search maximizes.

A won fight scores `reward.win_base` plus the HP it ended with (potions kept and max HP gained counted in HP, each turn costing a little)
as a share of the HP the fight started with. A lost or unfinished one scores minus the share of the enemies' HP still left, so the
search can tell losing lines apart by how close they came. The numbers are RewardParams (params.py)."""
from __future__ import annotations

from sts2_lite.combat import CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves.act3_glory import subject_respawns
from sts2_lite.enemy_moves.core import tough
from sts2_lite.enemy_moves.spawns import SPAWN_HP
from sts2_lite.relic import RelicId
from sts2_lite.status import INFESTED_SPAWNS, StatusId

from agents.sts2_MCTS.params import RewardParams


def is_win(state : CombatState) -> bool:
    """The player is alive and every enemy that counts (minions do not) is dead."""
    return state.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in state.enemies)

def rate_outcome(state : CombatState, reward : RewardParams, starting_hp : int, starting_max_hp : int, expected_total_hp : float) -> float:
    """The reward of the fight as it stands in `state`. `starting_hp`, `starting_max_hp` and `expected_total_hp` describe the fight's start."""
    current_hp = state.player.current_hp
    num_turns = state.turn_number
    won = is_win(state)
    max_hp_delta = state.player.max_hp - starting_max_hp
    # if won fight: outcome is best max hp with slight bias towards less turns
    if won:
        hp_score = current_hp
        if not state.final_fight:        # in the last fight a kept potion is of no use later: drinking one costs nothing
            hp_score += sum(reward.potion_bonus.get(p.potion_id, reward.default_potion_bonus) for p in state.player.potions)
            hp_score += reward.max_hp_scaling * max_hp_delta
            tail = state.player.relics.get(RelicId.LIZARD_TAIL)
            if tail is not None and not tail.used:
                hp_score += reward.lizard_tail_share * state.player.max_hp
        hp_score += -reward.turn_cost * num_turns
        return reward.win_base + hp_score / starting_hp         # linear in HP

    # lost or unfinished: minimize the enemy HP that is left, with a small preference for lasting longer
    progress_left = enemy_progress_left(state, expected_total_hp)
    held = 0.0
    if current_hp > 0 and not state.final_fight:      # a potion still held is worth something in a line that is not (yet) won
        held = reward.loss_potion_bonus * len(state.player.potions)
    if progress_left == 0:     # every enemy died and so did the player: no better than a plain loss
        return -1.0
    return -progress_left + reward.loss_turn_bonus * num_turns + held

def enemy_progress_left(state : CombatState, expected_total_hp : float) -> float:
    """The share of the fight's enemy HP that is still to be removed: 1.0 at the start of the fight, 0.0 when nothing is left.

    Counts what the living enemies still carry (`effective_hp`: a Phrog Parasite counts the Wrigglers it will release) and what
    the dead will bring back (`dormant_hp`: a killed Decimillipede segment is not progress, it is back at 25 HP in two turns)."""
    remaining = sum(effective_hp(e, state.ascension) for e in state.enemies) + dormant_hp(state)
    return remaining / max(1, expected_total_hp)

# A Phrog Parasite releases Wrigglers when it dies (Infested): its HP is not the end of the fight. They count at the mean of their base HP roll.
_WRIGGLER_MIN, _WRIGGLER_MAX = SPAWN_HP["WRIGGLER"][:2]
PHROG_RELEASE_HP = INFESTED_SPAWNS * (_WRIGGLER_MIN + _WRIGGLER_MAX) / 2


def expected_total_hp(state : CombatState) -> float:
    """The enemy HP there is to remove in the fight at its start (what `enemy_progress_left` is a share of)."""
    total = 0
    for e in state.enemies:
        if e.is_minion:
            continue
        total += e.max_hp
        if e.enemy_id.startswith("PHROG_PARASITE"):
            total += PHROG_RELEASE_HP
        total += later_forms_hp(e, state.ascension)
    return total

def later_forms_hp(enemy : Enemy, ascension : int) -> float:
    """The HP of the lives an Axebot (Stock) or the forms a Test Subject still has to come back as (212 and 313 at the tougher ascensions): killing one is not the end of the fight, it respawns.
    The form is read off its powers (`subject_respawns`: a dead one keeps the powers that tell which it was)."""
    stock = enemy.status.get(StatusId.STOCK)
    if stock is not None and stock.amount > 0:
        return stock.amount * enemy.max_hp      # an Axebot with Stock left comes back in full as often as the power says
    if not enemy.enemy_id.startswith("TEST_SUBJECT"):
        return 0
    forms = (tough(ascension, 200, 212), tough(ascension, 300, 313))
    return sum(forms[subject_respawns(enemy):])

def effective_hp(enemy : Enemy, ascension : int = 0) -> float:
    if enemy.is_minion:
        return 0
    hp = enemy.current_hp
    if enemy.enemy_id.startswith("PHROG_PARASITE"):
        hp += PHROG_RELEASE_HP
    return hp + later_forms_hp(enemy, ascension)

def dormant_hp(state : CombatState) -> float:
    """The HP that enemies lying dead (`state.dormant`) will bring back with them.

    A killed Decimillipede segment (ReattachPower) revives with its Reattach amount, but only while another segment is still alive:
    once the last living one is killed the fight is over and the dormant ones count for nothing."""
    subjects = sum(later_forms_hp(d, state.ascension) for d in state.dormant if StatusId.ADAPTABLE in d.status)      # a dead Test Subject has all its forms still to go
    if not any(not e.is_minion and e.current_hp > 0 for e in state.enemies):
        return subjects
    return subjects + sum(min(d.max_hp, d.status[StatusId.REATTACH].amount) for d in state.dormant if StatusId.REATTACH in d.status)
