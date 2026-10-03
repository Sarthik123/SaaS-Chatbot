from app.rag.chunking import (
    chunk_markdown,
    chunk_section_text,
    embedding_input,
    estimate_tokens,
    split_sections,
)

ARTICLE = """# Late fees

Late fees are off by default.

## Grace period
The grace period is 3 days.

## The cap
Fees are capped at 25% of the invoice.
"""


def long_text(paragraphs: int = 12, words_per_paragraph: int = 90) -> str:
    """Many paragraphs of numbered words, so we can see exactly which words each chunk holds."""
    counter = 0
    blocks = []
    for _ in range(paragraphs):
        words = []
        for _ in range(words_per_paragraph):
            counter += 1
            words.append(f"w{counter}")
        blocks.append(" ".join(words) + ".")
    return "\n\n".join(blocks)


def test_estimate_tokens_counts_words_and_punctuation():
    assert estimate_tokens("") == 0
    assert estimate_tokens("one two three") == 3
    assert estimate_tokens("Hello, world!") == 4


def test_article_is_split_at_headings_and_each_chunk_keeps_its_heading():
    chunks = chunk_markdown(ARTICLE)
    assert [c.heading for c in chunks] == [
        "Late fees",
        "Late fees > Grace period",
        "Late fees > The cap",
    ]
    assert "3 days" in chunks[1].text
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_token_count_includes_the_heading():
    for chunk in chunk_markdown(ARTICLE):
        assert chunk.token_count == estimate_tokens(embedding_input(chunk.heading, chunk.text))


def test_text_before_any_heading_uses_the_fallback_title():
    chunks = chunk_markdown("Just a plain note with no headings.", fallback_title="My note")
    assert len(chunks) == 1
    assert chunks[0].heading == "My note"


def test_a_hash_inside_a_code_block_is_not_a_heading():
    text = "# Title\n\nSteps:\n\n```\n# not a heading\nrun it\n```\n"
    sections = split_sections(text)
    assert len(sections) == 1
    assert "# not a heading" in sections[0].body


def test_empty_and_heading_only_input_gives_no_chunks():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n\n  ") == []
    assert chunk_markdown("# Only a title\n\n## And an empty section\n") == []


def test_long_section_is_split_and_no_chunk_is_too_big():
    chunks = chunk_section_text(long_text(), target_tokens=350, overlap_tokens=50)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert estimate_tokens(chunk) <= 350


def test_no_words_are_lost_when_splitting():
    text = long_text()
    chunks = chunk_section_text(text, target_tokens=350, overlap_tokens=50)
    seen = {word for chunk in chunks for word in chunk.split()}
    assert {word for word in text.split()} <= seen


def test_consecutive_chunks_overlap_by_about_50_tokens():
    chunks = chunk_section_text(long_text(), target_tokens=350, overlap_tokens=50)
    for before, after in zip(chunks, chunks[1:], strict=False):
        before_words, after_words = before.split(), after.split()
        shared = 0
        for size in range(1, min(len(before_words), len(after_words)) + 1):
            if before_words[-size:] == after_words[:size]:
                shared = size
        # Words here are one token each, so the overlap is between 25 and 50 tokens.
        assert 25 <= shared <= 50


def test_overlap_never_crosses_a_heading():
    text = f"# A\n\n## One\n{long_text(6)}\n\n## Two\nfresh start here."
    chunks = chunk_markdown(text)
    two = [c for c in chunks if c.heading.endswith("Two")]
    assert len(two) == 1
    assert two[0].text == "fresh start here."


def test_a_huge_sentence_without_full_stops_is_still_split():
    text = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_section_text(text, target_tokens=350, overlap_tokens=50)
    assert len(chunks) >= 3
    assert all(estimate_tokens(chunk) <= 350 for chunk in chunks)


def test_chunking_is_repeatable():
    assert chunk_markdown(ARTICLE + long_text()) == chunk_markdown(ARTICLE + long_text())
