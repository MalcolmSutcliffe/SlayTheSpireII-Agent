"""Things the agent met that the engine does not model (a Neow relic, an event whose options do not match). The agent notes them here and the run
manager writes them to the run's findings file (run_mismatches.jsonl) with the screen they came from, so they can be added to the engine later."""

_pending : list[tuple[str, str, str]] = []


def note(kind : str, key : str, message : str):
    """`kind` names the sort of thing ("ancient_relic", "event"), `key` identifies it (so one finding per thing), `message` says what."""
    _pending.append((kind, key, message))


def drain() -> list[tuple[str, str, str]]:
    taken = list(_pending)
    _pending.clear()
    return taken
