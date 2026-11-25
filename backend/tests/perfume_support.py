"""Shared test plumbing for the two-mode work.

The real perfume catalog is written by a scraper and changes; tests run
against tests/fixtures/perfume_catalog.json instead, and against knowledge
base documents rendered from it by the same code the build script uses.
"""
import json
import shutil
from pathlib import Path

import pytest

from app.catalogs import catalog
from app.integrations import bus
from app.knowledge import graph
from app.orchestrator.llm_client import LLMTurn
from app.rag import ingest, perfume_docs, retriever

FIXTURE = Path(__file__).parent / "fixtures" / "perfume_catalog.json"


@pytest.fixture
def perfume_catalog(tmp_path, monkeypatch):
    catalog.set_path("perfume", FIXTURE)
    docs = tmp_path / "docs_perfume"
    perfume_docs.write(json.loads(FIXTURE.read_text(encoding="utf-8")), docs)
    shutil.copy(ingest.DOCS_PERFUME_DIR / "boutique_faq.md", docs / "boutique_faq.md")
    monkeypatch.setitem(ingest.DOCS_DIRS, "perfume", docs)
    retriever.reset_index()
    yield docs
    catalog.set_path("perfume", catalog.CATALOG_DIR / "perfume.json")
    retriever.reset_index()
    graph.reset()


class BusRecorder:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def __call__(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))

    def of(self, event: str) -> list[dict]:
        return [payload for name, payload in self.events if name == event]


@pytest.fixture
def bus_events(monkeypatch):
    recorder = BusRecorder()
    monkeypatch.setattr(bus, "emit", recorder)
    return recorder


class RecordingLLM:
    """Scripted turns, recording the system prompt and tools of every hop."""

    def __init__(self, turns):
        self._turns = list(turns)
        self.systems: list[str] = []
        self.tools: list[list[dict]] = []

    def create_turn(self, *, system, messages, tools):
        self.systems.append(system)
        self.tools.append(tools)
        return self._turns.pop(0) if self._turns else LLMTurn(text="Okay.")
