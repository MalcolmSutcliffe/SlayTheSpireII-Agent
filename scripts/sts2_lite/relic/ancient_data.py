"""The relics Neow can offer (`Neow.AllPossibleOptions`), shared by the ancient screens and Neow's Bones."""
NEOW_CURSES = ("CURSED_PEARL", "DOWSING_ROD", "HEFTY_TABLET", "LARGE_CAPSULE", "LEAFY_POULTICE", "NEOWS_BONES", "NEOWS_SACRIFICE", "PRECARIOUS_SHEARS", "SILKEN_TRESS", "SILVER_CRUCIBLE")
NEOW_POSITIVE = ("ARCANE_SCROLL", "BOOMING_CONCH", "FISHING_ROD", "GOLDEN_PEARL", "KALEIDOSCOPE", "LEAD_PAPERWEIGHT", "LOST_COFFER", "MASSIVE_SCROLL", "NEOWS_TORMENT",
                 "NEW_LEAF", "PHIAL_HOLSTER", "PRECISE_SCISSORS", "SCROLL_BOXES", "WINGED_BOOTS")
NEOW_EXTRAS = ("LAVA_ROCK", "NEOWS_TALISMAN", "NUTRITIOUS_OYSTER", "POMANDER", "SMALL_CAPSULE", "STONE_HUMIDIFIER")
NOT_AT_NEOW = frozenset({"MASSIVE_SCROLL"})       # IsAllowedAtNeow is false: Massive Scroll is for multiplayer runs only


def neow_relics() -> list[str]:
    """Every relic Neow could offer that is allowed in a one-player run, Neow's Bones excepted."""
    return [r for r in NEOW_CURSES + NEOW_POSITIVE + NEOW_EXTRAS if r != "NEOWS_BONES" and r not in NOT_AT_NEOW]
