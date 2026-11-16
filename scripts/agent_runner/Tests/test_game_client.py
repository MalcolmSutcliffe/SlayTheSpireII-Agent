"""Reading the game: straight from the bridge mod when the CLI's package can be imported, through the CLI otherwise. Run from scripts/."""
import subprocess

from agent_runner import game_client
from agent_runner.game_client import GameClient


def fake_cli(monkeypatch, stdout='{"decision": "from the CLI"}'):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=stdout)
    monkeypatch.setattr(game_client.subprocess, "run", run)
    return calls


def test_a_state_read_in_process_starts_no_process(monkeypatch):
    calls = fake_cli(monkeypatch)
    client = GameClient(in_process=False)
    client.read_in_process = lambda: {"decision": "in process"}
    assert client.get_state() == {"decision": "in process"} and calls == []

def test_a_failed_in_process_read_falls_back_to_the_cli(monkeypatch):
    calls = fake_cli(monkeypatch)
    client = GameClient(in_process=False)
    def refuse():
        raise OSError("the bridge did not answer")
    client.read_in_process = refuse
    assert client.get_state() == {"decision": "from the CLI"} and calls == [[game_client.CLI, "state"]]

def test_without_the_cli_package_the_reads_go_through_the_cli(monkeypatch):
    calls = fake_cli(monkeypatch)
    monkeypatch.setitem(game_client.sys.modules, "cli_anything.slay_the_spire_ii.core.state_adapter", None)     # an import of it now fails
    assert game_client.in_process_reader() is None
    client = GameClient()
    assert client.read_in_process is None and client.get_state() == {"decision": "from the CLI"}

def test_the_in_process_read_is_what_the_cli_prints(monkeypatch):
    """normalize_state, then the JSON round trip: the tuples and other non-JSON values come out as the CLI's output parses to."""
    reader = game_client.in_process_reader()
    if reader is None:
        return          # the CLI package is not on this machine
    from cli_anything.slay_the_spire_ii.utils import sts2_backend
    monkeypatch.setattr(sts2_backend.Sts2RawClient, "get_state", lambda self, format="json": {"state_type": "map", "run": {"act": 1, "floor": 3}, "player": {"hp": 70}})
    state = GameClient().get_state()
    assert state["context"]["floor"] == 3 and state["player"]["hp"] == 70
