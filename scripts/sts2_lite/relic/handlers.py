from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from sts2_lite.events import EventType, HandlerTable

from sts2_lite.relic.card_hooks import _art_of_war_turn, _attack_seen, _burning_sticks, _charons_ashes, _count_card, _count_scarf, _daughter_of_the_wind, _diamond_diadem, _forgotten_soul, _game_piece, _iron_club, _joss_paper_ethereal, _joss_paper_exhausted, _kunai, _kusarigama, _letter_opener, _lost_wisp, _mummified_hand, _music_box, _new_turn_flag, _new_turn_rainbow, _nunchaku, _on_attack, _on_power, _on_skill, _ornamental_fan, _pen_nib_played, _permafrost, _pocketwatch_played, _pocketwatch_turn, _pollinous_core_turn, _rainbow_ring, _reset_counter, _ring_of_the_drake_turn, _ripple_basin_end, _shuriken, _tuning_fork
from sts2_lite.relic.ids import RelicId
from sts2_lite.relic.turn_hooks import _abacus, _biiig_hug, _brimstone, _candelabra, _captains_wheel, _centennial_puzzle, _chandelier, _cloak_clasp, _crossbow, _demon_tongue, _demon_tongue_reset, _gremlin_horn, _happy_flower, _history_course, _history_course_record, _horn_cleat, _mercury_hourglass, _mr_struggles, _orichalcum, _orichalcum_check, _paels_eye_exhaust, _paels_legion_turn, _paels_tears, _paels_tears_check, _parrying_shield, _pendulum, _red_skull, _sai, _screaming_flagon, _seal_of_gold, _self_forming_clay, _sparkling_rouge, _stone_calendar, _toasty_mittens, _unceasing_top

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature

EVENT_HANDLERS : dict[tuple[RelicId, EventType], Callable] = HandlerTable({
    (RelicId.PEN_NIB, EventType.CARD_PLAYED) : _pen_nib_played,
    (RelicId.NUNCHAKU, EventType.CARD_PLAYED) : _on_attack(_nunchaku),
    (RelicId.KUNAI, EventType.CARD_PLAYED) : _on_attack(_kunai),
    (RelicId.SHURIKEN, EventType.CARD_PLAYED) : _on_attack(_shuriken),
    (RelicId.KUSARIGAMA, EventType.CARD_PLAYED) : _on_attack(_kusarigama),
    (RelicId.ORNAMENTAL_FAN, EventType.CARD_PLAYED) : _on_attack(_ornamental_fan),
    (RelicId.LETTER_OPENER, EventType.CARD_PLAYED) : _on_skill(_letter_opener),
    (RelicId.TUNING_FORK, EventType.CARD_PLAYED) : _on_skill(_tuning_fork),
    (RelicId.RAINBOW_RING, EventType.CARD_PLAYED) : _rainbow_ring,
    (RelicId.POCKETWATCH, EventType.CARD_PLAYED) : _pocketwatch_played,
    (RelicId.ART_OF_WAR, EventType.CARD_PLAYED) : _on_attack(_attack_seen),
    (RelicId.RIPPLE_BASIN, EventType.CARD_PLAYED) : _on_attack(_attack_seen),
    (RelicId.PERMAFROST, EventType.CARD_PLAYED) : _on_power(_permafrost),
    (RelicId.GAME_PIECE, EventType.CARD_PLAYED) : _on_power(_game_piece),
    (RelicId.MUMMIFIED_HAND, EventType.CARD_PLAYED) : _on_power(_mummified_hand),
    (RelicId.DAUGHTER_OF_THE_WIND, EventType.CARD_PLAYED) : _daughter_of_the_wind,
    (RelicId.JOSS_PAPER, EventType.CARD_EXHAUSTED) : _joss_paper_exhausted,
    (RelicId.JOSS_PAPER, EventType.ETHEREAL_EXHAUSTED) : _joss_paper_ethereal,
    (RelicId.BURNING_STICKS, EventType.CARD_EXHAUSTED) : _burning_sticks,
    (RelicId.CHARONS_ASHES, EventType.CARD_EXHAUSTED) : _charons_ashes,
    (RelicId.FORGOTTEN_SOUL, EventType.CARD_EXHAUSTED) : _forgotten_soul,
    (RelicId.LOST_WISP, EventType.CARD_PLAYED) : _on_power(_lost_wisp),
    (RelicId.IRON_CLUB, EventType.CARD_PLAYED) : _iron_club,
    (RelicId.MUSIC_BOX, EventType.CARD_PLAYED) : _music_box,
    (RelicId.BRILLIANT_SCARF, EventType.CARD_PLAYED) : _count_scarf,
    (RelicId.VELVET_CHOKER, EventType.CARD_PLAYED) : _count_card,
    (RelicId.DIAMOND_DIADEM, EventType.CARD_PLAYED) : _count_card,
    (RelicId.DIAMOND_DIADEM, EventType.END_TURN) : _diamond_diadem,
    (RelicId.MUSIC_BOX, EventType.BEFORE_PLAYER_TURN) : _new_turn_flag,
    (RelicId.BRILLIANT_SCARF, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.VELVET_CHOKER, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    # the start of the turn, after the hand is drawn
    (RelicId.CANDELABRA, EventType.PLAYER_TURN_START) : _candelabra,
    (RelicId.CHANDELIER, EventType.PLAYER_TURN_START) : _chandelier,
    (RelicId.HAPPY_FLOWER, EventType.PLAYER_TURN_START) : _happy_flower,
    (RelicId.MERCURY_HOURGLASS, EventType.PLAYER_TURN_START) : _mercury_hourglass,
    (RelicId.BRIMSTONE, EventType.PLAYER_TURN_START) : _brimstone,
    (RelicId.FAKE_HAPPY_FLOWER, EventType.PLAYER_TURN_START) : _happy_flower,
    (RelicId.SAI, EventType.PLAYER_TURN_START) : _sai,
    (RelicId.TOASTY_MITTENS, EventType.BEFORE_PLAYER_TURN) : _toasty_mittens,
    (RelicId.HISTORY_COURSE, EventType.CARD_PLAYED) : _history_course_record,
    (RelicId.HISTORY_COURSE, EventType.AUTO_PRE_PLAY) : _history_course,
    (RelicId.CROSSBOW, EventType.PLAYER_TURN_START) : _crossbow,
    (RelicId.MR_STRUGGLES, EventType.PLAYER_TURN_START) : _mr_struggles,
    (RelicId.PAELS_TEARS, EventType.PLAYER_TURN_START) : _paels_tears,
    (RelicId.SEAL_OF_GOLD, EventType.PLAYER_TURN_START) : _seal_of_gold,
    (RelicId.PAELS_LEGION, EventType.PLAYER_TURN_START) : _paels_legion_turn,
    # after block is cleared, before the hand draw
    (RelicId.HORN_CLEAT, EventType.BLOCK_CLEARED) : _horn_cleat,
    (RelicId.CAPTAINS_WHEEL, EventType.BLOCK_CLEARED) : _captains_wheel,
    (RelicId.SPARKLING_ROUGE, EventType.BLOCK_CLEARED) : _sparkling_rouge,
    # the end of the player's turn
    (RelicId.ORICHALCUM, EventType.PLAY_PHASE_END) : _orichalcum_check,
    (RelicId.ORICHALCUM, EventType.END_TURN) : _orichalcum,
    (RelicId.FAKE_ORICHALCUM, EventType.PLAY_PHASE_END) : _orichalcum_check,
    (RelicId.FAKE_ORICHALCUM, EventType.END_TURN) : _orichalcum,
    (RelicId.PAELS_TEARS, EventType.END_TURN) : _paels_tears_check,
    (RelicId.PAELS_EYE, EventType.TURN_END_EARLY) : _paels_eye_exhaust,
    (RelicId.CLOAK_CLASP, EventType.END_TURN) : _cloak_clasp,
    (RelicId.SCREAMING_FLAGON, EventType.END_TURN) : _screaming_flagon,
    (RelicId.STONE_CALENDAR, EventType.END_TURN) : _stone_calendar,
    (RelicId.PARRYING_SHIELD, EventType.PLAYER_TURN_ENDED) : _parrying_shield,
    (RelicId.RIPPLE_BASIN, EventType.END_TURN) : _ripple_basin_end,
    (RelicId.KUSARIGAMA, EventType.END_TURN) : _reset_counter,
    # the start of the next turn, before the hand is drawn
    (RelicId.KUNAI, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.SHURIKEN, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.ORNAMENTAL_FAN, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.LETTER_OPENER, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.RAINBOW_RING, EventType.BEFORE_PLAYER_TURN) : _new_turn_rainbow,
    (RelicId.POCKETWATCH, EventType.BEFORE_PLAYER_TURN) : _pocketwatch_turn,
    (RelicId.RING_OF_THE_DRAKE, EventType.BEFORE_PLAYER_TURN) : _ring_of_the_drake_turn,
    (RelicId.POLLINOUS_CORE, EventType.BEFORE_PLAYER_TURN) : _pollinous_core_turn,
    (RelicId.ART_OF_WAR, EventType.BEFORE_PLAYER_TURN) : _art_of_war_turn,
    (RelicId.RIPPLE_BASIN, EventType.BEFORE_PLAYER_TURN) : _new_turn_flag,
})

EVENT_HANDLERS.update({
    (RelicId.CENTENNIAL_PUZZLE, EventType.HP_LOST) : _centennial_puzzle,
    (RelicId.GREMLIN_HORN, EventType.CREATURE_KILLED) : _gremlin_horn,
    (RelicId.PENDULUM, EventType.PLAYER_TURN_START) : _pendulum,
    (RelicId.THE_ABACUS, EventType.SHUFFLED) : _abacus,
    (RelicId.BIIIG_HUG, EventType.SHUFFLED) : _biiig_hug,
    (RelicId.UNCEASING_TOP, EventType.HAND_EMPTIED) : _unceasing_top,
    (RelicId.DEMON_TONGUE, EventType.HP_LOST) : _demon_tongue,
    (RelicId.DEMON_TONGUE, EventType.BEFORE_PLAYER_TURN) : _demon_tongue_reset,
    (RelicId.RED_SKULL, EventType.HP_CHANGED) : _red_skull,
    (RelicId.SELF_FORMING_CLAY, EventType.HP_LOST) : _self_forming_clay,
})

def fire_relics(combat : CombatSimulator, event : EventType, *args):
    handlers = EVENT_HANDLERS.by_event.get(event)
    if handlers is None:
        return
    for relic_id, relic in list(combat.combat_state.player.relics.items()):
        handler = handlers.get(relic_id)
        if handler is not None:
            handler(combat, relic, *args)

# ---
# A card play that fails is undone: the counters and the block go back.
# ---
def snapshot(owner : Creature):
    return owner.block, {relic_id : (relic.counter, relic.used, relic.value, relic.triggering) for relic_id, relic in owner.relics.items()}

def restore(owner : Creature, saved):
    owner.block = saved[0]
    for relic_id, (counter, used, value, triggering) in saved[1].items():
        relic = owner.relics[relic_id]
        relic.counter, relic.used, relic.value, relic.triggering = counter, used, value, triggering
