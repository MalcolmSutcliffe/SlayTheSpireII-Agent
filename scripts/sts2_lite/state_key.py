"""A hashable fingerprint of a CombatState for a transposition table: two states with equal keys play out identically
(in distribution), so a search can share one node between them.

What is ignored on purpose:
  - the order of the hand, discard pile, exhaust pile and of the part of the draw pile the agent cannot see
    (the search shuffles that part before anything random happens, see Player.shuffle_draw_pile)
  - pure accounting that nothing reads between actions: cards_drawn, unknown_draws, damage_taken, block_play(_gains)
What is kept in order: the known top of the draw pile (it is drawn in that order) and the enemies (targets are positions).

A missed difference merges states that are not the same, which is a bug; an extra difference only costs a merge.
Anything added to Player, Enemy, Creature, CombatState or RelicInstance that changes how a fight plays needs a line here;
test_state_key.test_every_copied_field_is_in_the_key lists the fields so a new one is noticed."""
from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.combat import CombatState
    from sts2_lite.status import StatusInstance


def _multiset(cards) -> frozenset:
    return frozenset(Counter(c.signature() for c in cards).items())

def _statuses(status : dict[object, StatusInstance]) -> tuple:
    return tuple(sorted(((s.value if hasattr(s, "value") else s.name), inst.amount, tuple(tuple(r) for r in inst.records))
                        for s, inst in status.items()))

def _opt_sig(card : Card | None):
    return None if card is None else card.signature()

def _relics(relics) -> tuple:
    return tuple(sorted(((r.relic_id.value, r.counter if r.counter is not None else -1, r.used, r.value, _opt_sig(r.triggering))
                        for r in relics.values()), key=repr))

def _choice(cs) -> tuple | None:
    """A pending pick names positions in a pile; two states that differ only in the order of that pile offer the same
    cards, so the options are described by the cards at those positions. A pick from the draw pile also keeps the
    pile's order: its positions reach into the part the agent cannot see."""
    pc, p = cs.pending_choice, cs.player
    if pc is None:
        return None
    pile = {"hand": p.hand, "discard": p.discard_pile, "draw": p.draw_pile, "offer": pc.offers}.get(pc.pile, p.hand)
    order = tuple(c.signature() for c in p.draw_pile) if pc.pile == "draw" else None
    return (pc.kind, _multiset(pile[i] for i in pc.indices if i < len(pile)), pc.pile, pc.amount, pc.hidden,
            _multiset(p.hand[i] for i in pc.picked if i < len(p.hand)), _opt_sig(pc.source), _multiset(pc.offers), order)

def _enemy(e) -> tuple:
    candidates = None if e.damage_candidates is None else tuple(sorted(e.damage_candidates))
    return (e.enemy_id, e.slot, e.current_hp, e.max_hp, e.block, e.is_minion, _statuses(e.status),
            e.attack_damage, e.num_attacks, candidates, e.move_id, e.move_streak, tuple(sorted(e.used_moves)),
            e.has_been_attacked_this_turn, e.lost_hp_this_turn, e.hp_loss_events, e.after_stun, e.off_balance, e.counter)

def _player(p) -> tuple:
    n = p.known_top
    split = max(0, len(p.draw_pile) - n)
    unseen, known = p.draw_pile[:split], p.draw_pile[split:]
    return (p.current_hp, p.max_hp, p.block, _statuses(p.status),
            _multiset(p.hand), _multiset(unseen), tuple(c.signature() for c in known), _multiset(p.discard_pile), _multiset(p.exhaust_pile),
            _relics(p.relics),
            p.inferno_plays, p.cards_played_total, p.crimson_mantle_plays, p.attacks_played_this_turn, p.plays_started_this_turn,
            tuple(sorted(p.returning, key=repr)), p.card_blocks_this_turn, p.cards_exhausted_this_turn, p.gold,
            p.has_been_attacked_this_turn, p.lost_hp_this_turn, p.hp_loss_events, tuple(p.hp_lost_log), p.is_minion, p.binding, p.bound_cards, p.bound_played, p.smogged)

def _continuations(cs) -> tuple:
    """What the cards waiting for a pick still have to do."""
    return tuple((k, a[0].signature(), *a[1:]) if k == "finish" else (k, tuple(c.signature() for c in a[0])) for k, *a in cs.continuations)

def state_key(cs : CombatState) -> tuple:
    """Hashable fingerprint of `cs`; equal for states reached by playing the same cards in a different order."""
    return (cs.energy, cs.max_energy, cs.turn_number, cs.extra_turns, cs.ascension, cs.cards_played, cs.won,
            tuple(sorted(cs.revivals, key=repr)), tuple(_enemy(e) for e in cs.dormant), _continuations(cs), _choice(cs),
            _player(cs.player), tuple(_enemy(e) for e in cs.enemies))
