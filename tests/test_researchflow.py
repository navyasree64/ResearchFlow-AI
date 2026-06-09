"""
ResearchFlow AI — Test Suite (20 test cases)
Run with:  pytest tests/test_researchflow.py -v
"""
import os
import json
import hashlib
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# ── ensure .env loads before imports ─────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from modules.schemas import ResearchPaper, ExtractedInsights, EvolvingSummary
from modules.memento import MementoDB
from modules.crawler import WebCrawler
from modules.extractor import InsightExtractor
from modules.synthesizer import KnowledgeSynthesizer


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def make_paper(title="Test Paper", url="https://example.com/paper1") -> ResearchPaper:
    return ResearchPaper(
        title=title,
        authors=["Alice Smith", "Bob Jones"],
        publication_date="2024-01-15",
        journal="Nature Medicine",
        doi="10.1234/test.2024",
        url=url,
        abstract="This paper studies X and finds Y.",
        full_summary="A detailed summary of X.",
        insights=ExtractedInsights(
            core_findings=["Finding A", "Finding B"],
            methodology="RCT with n=500",
            limitations=["Small sample", "Short duration"],
            keywords=["genomics", "CRISPR"],
            future_work=["Larger cohort needed"],
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1-4 — SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════
class TestSchemas:
    def test_01_research_paper_defaults(self):
        """ResearchPaper initialises with correct default values."""
        p = ResearchPaper(
            title="Minimal Paper",
            url="https://example.com",
            abstract="Abstract.",
            insights=ExtractedInsights(),
        )
        assert p.authors == []
        assert p.doi == ""
        assert p.journal == ""
        assert p.insights.core_findings == []

    def test_02_added_at_auto_populated(self):
        """added_at is automatically set at creation time."""
        p = make_paper()
        assert p.added_at != ""
        assert len(p.added_at) >= 10  # at least "YYYY-MM-DD"

    def test_03_extracted_insights_fields(self):
        """ExtractedInsights stores all provided fields correctly."""
        ins = ExtractedInsights(
            core_findings=["F1", "F2"],
            methodology="Meta-analysis",
            limitations=["Bias"],
            keywords=["AI", "health"],
            future_work=["More data"],
        )
        assert ins.methodology == "Meta-analysis"
        assert "AI" in ins.keywords
        assert len(ins.core_findings) == 2

    def test_04_evolving_summary_defaults(self):
        """EvolvingSummary has sensible empty defaults."""
        s = EvolvingSummary(
            summary="Summary text",
            novel_contributions=["C1"],
            conflicts_or_agreements="Agrees with prior work.",
        )
        assert s.open_questions == []
        assert s.field_trajectory == ""


# ═══════════════════════════════════════════════════════════════════════════════
# 5-9 — MEMENTO DB
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def memdb():
    """Isolated in-memory MementoDB — fresh collection per test."""
    import uuid
    import chromadb
    from modules.memento import MementoDB
    db = MementoDB.__new__(MementoDB)
    db.client = chromadb.EphemeralClient()
    db.collection = db.client.get_or_create_collection(
        name=f"test_{uuid.uuid4().hex}",
        metadata={"hnsw:space": "cosine"},
    )
    return db


class TestMementoDB:
    def test_05_save_and_count(self, memdb):
        """Saving a paper increments the count."""
        assert memdb.count() == 0
        memdb.save_paper(make_paper())
        assert memdb.count() == 1

    def test_06_paper_exists_after_save(self, memdb):
        """paper_exists returns True after saving."""
        paper = make_paper()
        assert not memdb.paper_exists(paper.url)
        memdb.save_paper(paper)
        assert memdb.paper_exists(paper.url)

    def test_07_get_all_papers_returns_list(self, memdb):
        """get_all_papers returns a list with saved papers."""
        memdb.save_paper(make_paper("Paper A", "https://example.com/a"))
        memdb.save_paper(make_paper("Paper B", "https://example.com/b"))
        papers = memdb.get_all_papers()
        assert len(papers) == 2
        titles = {p["title"] for p in papers}
        assert "Paper A" in titles
        assert "Paper B" in titles

    def test_08_get_paper_by_id(self, memdb):
        """get_paper_by_id retrieves the correct paper."""
        paper = make_paper()
        memdb.save_paper(paper)
        pid = hashlib.md5(paper.url.encode()).hexdigest()
        result = memdb.get_paper_by_id(pid)
        assert result is not None
        assert result["title"] == paper.title

    def test_09_retrieve_context_empty(self, memdb):
        """retrieve_context_for_topic returns baseline message when empty."""
        ctx = memdb.retrieve_context_for_topic("CRISPR")
        assert "No prior knowledge" in ctx


# ═══════════════════════════════════════════════════════════════════════════════
# 10-13 — CRAWLER
# ═══════════════════════════════════════════════════════════════════════════════
class TestWebCrawler:
    def test_10_not_ready_without_key(self):
        """WebCrawler is not ready when FIRECRAWL_API_KEY is missing."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": ""}):
            crawler = WebCrawler()
            assert crawler.ready is False

    def test_11_not_ready_with_placeholder_key(self):
        """WebCrawler is not ready when key is the placeholder string."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "your_firecrawl_api_key_here"}):
            crawler = WebCrawler()
            assert crawler.ready is False

    def test_12_scrape_returns_error_when_not_ready(self):
        """scrape_article returns an ERROR: string when not configured."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": ""}):
            crawler = WebCrawler()
            result = crawler.scrape_article("https://example.com")
            assert result.startswith("ERROR:")

    def test_13_ready_with_valid_key(self):
        """WebCrawler.ready is True when a non-placeholder key is set."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-validkeyxxx123"}):
            with patch("modules.crawler.Firecrawl", MagicMock(), create=True):
                # Force the import path used inside crawler
                import importlib, modules.crawler as c
                importlib.reload(c)
                crawler = c.WebCrawler()
                assert crawler.ready is True


# ═══════════════════════════════════════════════════════════════════════════════
# 14-17 — EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════════════
class TestInsightExtractor:
    def test_14_not_ready_without_key(self):
        """InsightExtractor is not ready without a Gemini key."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            ext = InsightExtractor()
            assert ext.ready is False

    def test_15_returns_error_paper_when_not_ready(self):
        """extract_paper_details returns an error paper when key missing."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            ext = InsightExtractor()
            paper = ext.extract_paper_details("https://x.com", "some content")
            assert "[ERROR]" in paper.title

    def test_16_returns_error_paper_on_scrape_error_input(self):
        """extract_paper_details handles ERROR: prefixed content gracefully."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaFake123"}):
            ext = InsightExtractor()
            ext.ready = True
            paper = ext.extract_paper_details("https://x.com", "ERROR:SCRAPE_FAILED:timeout")
            assert "[ERROR]" in paper.title

    def test_17_json_parse_failure_returns_error_paper(self):
        """If LLM returns bad JSON, an error paper is returned (not a crash)."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaFake123"}):
            ext = InsightExtractor()
            ext.ready = True
            mock_model = MagicMock()
            mock_model.generate_content.return_value.text = "not valid json {{{"
            ext.model = mock_model
            paper = ext.extract_paper_details("https://x.com", "markdown content here")
            assert "[ERROR]" in paper.title


# ═══════════════════════════════════════════════════════════════════════════════
# 18-20 — SYNTHESIZER
# ═══════════════════════════════════════════════════════════════════════════════
class TestKnowledgeSynthesizer:
    def test_18_not_ready_without_key(self):
        """KnowledgeSynthesizer is not ready without a Gemini key."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            synth = KnowledgeSynthesizer()
            assert synth.ready is False

    def test_19_returns_placeholder_summary_when_not_ready(self):
        """generate_evolving_summary returns a helpful message when not configured."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            synth = KnowledgeSynthesizer()
            result = synth.generate_evolving_summary("CRISPR", "no context", [])
            assert "API key" in result.summary or "not configured" in result.summary.lower()

    def test_20_parses_valid_llm_json_response(self):
        """generate_evolving_summary parses a valid JSON LLM response correctly."""
        fake_response = json.dumps({
            "summary": "The field has advanced significantly.",
            "novel_contributions": ["Contribution 1", "Contribution 2"],
            "conflicts_or_agreements": "Broadly consistent with prior work.",
            "open_questions": ["What about long-term effects?"],
            "field_trajectory": "Heading toward clinical translation.",
        })
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaFake123"}):
            synth = KnowledgeSynthesizer()
            synth.ready = True
            mock_model = MagicMock()
            mock_model.generate_content.return_value.text = fake_response
            synth.model = mock_model
            result = synth.generate_evolving_summary("CRISPR", "no prior context", [make_paper()])
            assert result.summary == "The field has advanced significantly."
            assert len(result.novel_contributions) == 2
            assert result.open_questions[0].startswith("What about")
