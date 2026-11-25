"""Graphify facts at answer time: seeding, 1-hop edges, the EXTRACTED/INFERRED
labels, and the specialist being told to treat the two differently."""
import json
import re

import pytest

from app.knowledge import graph
from app.sessions.models import SessionState
from app.specialists import solutions
from app.specialists.solutions import SolutionsAnswer
from app.tools import executor

LINE = re.compile(r"^.+ --[a-z_]+--> .+ \[(EXTRACTED|INFERRED|AMBIGUOUS), .+\]$")


@pytest.fixture
def tiny_graph(tmp_path):
    data = {
        "nodes": [
            {"id": "sauvage", "label": "Sauvage Eau de Parfum", "file_type": "concept", "source_file": "fragrance.md", "community": 0},
            {"id": "bergamot", "label": "Calabrian Bergamot", "file_type": "concept", "source_file": "fragrance.md", "community": 0},
            {"id": "engraving", "label": "Complimentary Engraving", "file_type": "concept", "source_file": "boutique_faq.md", "community": 1},
            {"id": "code", "label": "Sauvage parser function", "file_type": "code", "source_file": "x.py", "community": 2},
        ],
        "links": [
            {"source": "sauvage", "target": "engraving", "relation": "conceptually_related_to", "confidence": "INFERRED", "confidence_score": 0.8, "source_file": "boutique_faq.md"},
            {"source": "sauvage", "target": "bergamot", "relation": "has_note", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "fragrance.md"},
            {"source": "code", "target": "sauvage", "relation": "calls", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "x.py"},
        ],
    }
    path = tmp_path / "perfume.graph.json"
    path.write_text(json.dumps(data))
    graph.set_path("perfume", path)
    yield path
    graph.reset()


def test_facts_are_one_hop_extracted_first_and_skip_code(tiny_graph):
    facts = graph.facts_for("what's in Sauvage?", "perfume")
    assert facts == [
        "Sauvage Eau de Parfum --has_note--> Calabrian Bergamot [EXTRACTED, fragrance.md]",
        "Sauvage Eau de Parfum --conceptually_related_to--> Complimentary Engraving [INFERRED, boutique_faq.md]",
    ]


def test_stopwords_alone_seed_nothing(tiny_graph):
    assert graph.facts_for("what is the of and for", "perfume") == []


def test_limit_and_missing_graph(tiny_graph, tmp_path):
    assert len(graph.facts_for("sauvage", "perfume", limit=1)) == 1
    graph.set_path("perfume", tmp_path / "nope.json")
    assert graph.facts_for("sauvage", "perfume") == []
    assert graph.stats("perfume") is None


def test_real_apple_graph_answers_with_labelled_lines():
    facts = graph.facts_for("Does Apple Business Manager work with Jamf?", "apple")
    assert 0 < len(facts) <= 10
    assert all(LINE.match(f) for f in facts)
    labels = [f.split("[")[1].split(",")[0] for f in facts]
    assert labels == sorted(labels, key=lambda c: c != "EXTRACTED")
    assert any("Jamf" in f for f in facts)
    assert not any("ingest.py" in f for f in graph.facts_for("chunk markdown products", "apple"))


def test_stats_counts_the_graph():
    stats = graph.stats("apple")
    assert stats == {"nodes": 43, "links": 53, "extracted": 42, "inferred": 11, "communities": 7}


def test_the_engineer_gets_graph_facts_and_the_rule(monkeypatch):
    seen = {}

    class Stub:
        def complete(self, *, system, prompt):
            seen["system"], seen["prompt"] = system, prompt
            return json.dumps(SolutionsAnswer(answer="ok", confidence="high").model_dump())

    real = solutions.consult
    monkeypatch.setattr(solutions, "consult", lambda **kw: real(**{**kw, "client": Stub()}))
    result = executor.dispatch(
        "ask_solutions_engineer",
        {"question": "Does Apple Business Manager work with Jamf?"},
        SessionState(session_id="sess-graph"),
    )
    assert result["graph_facts"] > 0
    assert "[graphify knowledge graph]" in seen["prompt"]
    assert "INFERRED facts are connections Graphify resolved" in seen["system"]
    assert "open_questions" in seen["system"]


def test_both_specialist_prompts_carry_the_graph_rule():
    for prompt in (solutions.SOLUTIONS_SYSTEM_PROMPT, solutions.FRAGRANCE_SPECIALIST_SYSTEM_PROMPT):
        assert "EXTRACTED facts are stated in our documents" in prompt
        assert "never turn one into a promise" in prompt


def test_perfume_mode_uses_the_fragrance_specialist(monkeypatch, tiny_graph):
    seen = {}

    class Stub:
        def complete(self, *, system, prompt):
            seen["system"] = system
            return "{}"

    real = solutions.consult
    monkeypatch.setattr(solutions, "consult", lambda **kw: real(**{**kw, "client": Stub()}))
    result = executor.dispatch(
        "ask_solutions_engineer", {"question": "how long does Sauvage last?"},
        SessionState(session_id="sess-frag", mode="perfume"),
    )
    assert seen["system"] == solutions.FRAGRANCE_SPECIALIST_SYSTEM_PROMPT
    assert result["graph_facts"] == 2
