"""Checks on the fake company's help articles in data/demo_kb/ and docs/KB-COVERAGE.md."""

import re
from pathlib import Path

import pytest

from app.db.memory import InMemoryRepository
from app.providers.fake import FakeEmbeddingProvider
from app.rag.ingest import ingest_directory

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "data" / "demo_kb"
ARTICLES = sorted(KB.glob("*.md"))

# Words that must NOT appear in any article, grouped by the topic they belong to. These are the
# topics docs/KB-COVERAGE.md says the knowledge base does not cover, so a question about them
# must be refused. If someone adds an article about one of them, this test fails on purpose.
NOT_COVERED_WORDS = {
    "payroll": ["payroll"],
    "cryptocurrency payments": ["crypto", "bitcoin", "ethereum"],
    "phone support": ["phone support", "telephone", "call us", "hotline"],
    "on-premise hosting": ["on-premise", "on-premises", "self-hosted", "own servers"],
    "dark mode": ["dark mode", "dark theme"],
    "inventory management": ["inventory", "stock level"],
    "shipping labels": ["shipping label"],
    "time tracking": ["time tracking", "timesheet"],
    "purchase orders": ["purchase order"],
    "expense reports": ["expense"],
    "online store integrations": ["shopify", "woocommerce", "online store", "e-commerce"],
    "reselling": ["white-label", "white label", "reseller", "resell"],
    # near-miss gaps: the article exists but this specific fact must be absent
    "minimum phone software version": [
        "ios version",
        "android version",
        "operating system",
        "minimum",
    ],
    "charity or student pricing": ["nonprofit", "non-profit", "charit", "student", "discount"],
    "waiving a late fee": ["waive", "waiver", "cancel a late fee", "remove a late fee"],
}


def test_there_are_about_25_articles():
    assert len(ARTICLES) == 25


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_each_article_has_a_title_several_headings_and_a_sensible_length(path):
    text = path.read_text(encoding="utf-8")
    assert re.match(r"# .+", text), "must start with a '# Title' line"
    assert len(re.findall(r"^## ", text, re.MULTILINE)) >= 3
    words = len(text.split())
    assert 150 <= words <= 500, f"{path.name} has {words} words"


@pytest.mark.parametrize("topic", sorted(NOT_COVERED_WORDS))
def test_topics_that_must_stay_uncovered_do_not_appear_in_any_article(topic):
    for path in ARTICLES:
        text = path.read_text(encoding="utf-8").lower()
        for word in NOT_COVERED_WORDS[topic]:
            assert word not in text, f"{path.name} mentions '{word}' (topic: {topic})"


def test_the_export_article_does_not_say_how_long_the_download_link_lasts():
    text = (KB / "export-your-data.md").read_text(encoding="utf-8").lower()
    assert "expire" not in text
    assert "available for" not in text


def test_the_coverage_file_lists_twelve_uncovered_topics():
    text = (ROOT / "docs" / "KB-COVERAGE.md").read_text(encoding="utf-8")
    section = text.split("## B.")[1].split("## C.")[0]
    rows = re.findall(r"^\| (\d+) \|", section, re.MULTILINE)
    assert len(rows) == 12
    assert "## A." in text


def test_no_article_mentions_a_real_company():
    # The demo is fake. These well-known names must not slip in.
    names = ["quickbooks", "xero", "stripe", "paypal", "freshbooks", "shopify", "wave"]
    for path in ARTICLES:
        words = set(re.findall(r"[a-z]+", path.read_text(encoding="utf-8").lower()))
        for name in names:
            assert name not in words, f"{path.name} mentions {name}"


def test_the_whole_knowledge_base_can_be_ingested_and_re_ingested():
    repo = InMemoryRepository(32)
    embedder = FakeEmbeddingProvider(dim=32)
    first = ingest_directory(KB, repo, embedder)
    assert first.articles == 25
    assert first.skipped == []
    assert first.chunks >= 25
    counts = (repo.count_articles(), repo.count_chunks())
    ingest_directory(KB, repo, embedder)
    assert (repo.count_articles(), repo.count_chunks()) == counts
