"""The playable characters: what a run starts with and which pools it draws from (Models.Characters, the character card / relic / potion pools).

A character's card pool is its table in card.tables (CHARACTER_CARDS); its relic pool is the relics of pool_data tagged with `relic_pool`; its potions
are potion_pool.CHARACTER[name]. Adding a character: an entry here, its card table and plays/<character>.py, its relics and potions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Character:
    name : str              # the id runs use ("SILENT")
    title : str             # what the bridge shows as player.character ("The Silent")
    hp : int
    gold : int
    potion_slots : int
    relic : str             # starter relic id
    relic_name : str
    deck : tuple[str, ...]

    @property
    def relic_pool(self) -> str:
        """The tag of its relics in relic.pool_data."""
        return self.name.lower()


CHARACTERS = {
    "IRONCLAD": Character("IRONCLAD", "The Ironclad", 80, 99, 3, "BURNING_BLOOD", "Burning Blood",
                          ("STRIKE_IRONCLAD",) * 5 + ("DEFEND_IRONCLAD",) * 4 + ("BASH",)),
    "SILENT": Character("SILENT", "The Silent", 70, 99, 3, "RING_OF_THE_SNAKE", "Ring of the Snake",
                        ("STRIKE_SILENT",) * 5 + ("DEFEND_SILENT",) * 5 + ("NEUTRALIZE", "SURVIVOR")),       # Silent.StartingDeck; captured in silent-a0-1
    "REGENT": Character("REGENT", "The Regent", 75, 99, 3, "DIVINE_RIGHT", "Divine Right",
                        ("STRIKE_REGENT",) * 4 + ("DEFEND_REGENT",) * 4 + ("FALLING_STAR", "VENERATE")),       # Regent.StartingDeck
    "NECROBINDER": Character("NECROBINDER", "The Necrobinder", 66, 99, 3, "BOUND_PHYLACTERY", "Bound Phylactery",
                             ("STRIKE_NECROBINDER",) * 4 + ("DEFEND_NECROBINDER",) * 4 + ("BODYGUARD", "UNLEASH")),       # Necrobinder.StartingDeck
    "DEFECT": Character("DEFECT", "The Defect", 75, 99, 3, "CRACKED_CORE", "Cracked Core",
                        ("STRIKE_DEFECT",) * 4 + ("DEFEND_DEFECT",) * 4 + ("ZAP", "DUALCAST")),       # Defect.StartingDeck
}


def character(name : str) -> Character:
    try:
        return CHARACTERS[name.upper()]
    except KeyError:
        raise NotImplementedError(f"{name}: not modelled (characters: {', '.join(CHARACTERS)})") from None


def character_of_title(title : str | None) -> str:
    """The character id for the bridge's player.character ("The Silent" -> "SILENT"); the Ironclad when it is not given."""
    for c in CHARACTERS.values():
        if title and title.lower() in (c.title.lower(), c.name.lower()):
            return c.name
    return "IRONCLAD"
