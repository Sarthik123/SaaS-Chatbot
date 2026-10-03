"""Cutting help articles into chunks.

Why chunks? Searching a whole article gives vague matches ("this article is somehow about
billing"). Searching small pieces finds the exact paragraph that answers the question.

Rules (see AGENTS.md "RAG rules" #1):
  1. Split the article at its headings.
  2. If a section is still longer than about 350 tokens, cut it into chunks of about 350 tokens.
  3. Consecutive chunks of the same section overlap by about 50 tokens, so an answer is never
     cut in half at a chunk border.
  4. Every chunk keeps its heading ("Article title > Section"), so a lone paragraph still
     says what it is about.

A "token" is a word-piece the AI model reads. We do not know the exact count without the model's
own tokenizer, so `estimate_tokens` counts words and punctuation marks. That is close enough for
sizing chunks and it is simple and repeatable.
"""

import re
from dataclasses import dataclass

TARGET_TOKENS = 350
OVERLAP_TOKENS = 50

_TOKEN = re.compile(r"\w+|[^\w\s]")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_BLANK_LINE = re.compile(r"\n\s*\n")


def estimate_tokens(text: str) -> int:
    """Rough token count: every word and every punctuation mark counts as one."""
    return len(_TOKEN.findall(text))


@dataclass(frozen=True)
class Section:
    heading: str  # e.g. "Late fees > Grace period"
    body: str


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    heading: str
    text: str
    token_count: int  # counts the heading too, because the heading is embedded with the text


def embedding_input(heading: str, text: str) -> str:
    """The exact text that is embedded and keyword-indexed: heading first, then the chunk."""
    return f"{heading}\n{text}" if heading else text


def split_sections(markdown: str, fallback_title: str = "") -> list[Section]:
    """Split Markdown at its headings. Heading-only sections (no body text) are dropped."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # the current heading path: (level, text)
    buffer: list[str] = []
    in_code_block = False

    def heading_path() -> str:
        return " > ".join(text for _, text in stack) or fallback_title

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append(Section(heading=heading_path(), body=body))
        buffer.clear()

    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block  # a "# comment" inside code is not a heading
        match = None if in_code_block else _HEADING.match(line)
        if match:
            flush()
            level, text = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
        else:
            buffer.append(line)
    flush()
    return sections


def _split_words(text: str, limit: int) -> list[str]:
    """Last resort for text with no sentence ends: cut between words."""
    pieces, current, used = [], [], 0
    for word in text.split():
        cost = estimate_tokens(word)
        if current and used + cost > limit:
            pieces.append(" ".join(current))
            current, used = [], 0
        current.append(word)
        used += cost
    if current:
        pieces.append(" ".join(current))
    return pieces


def _units(text: str, limit: int) -> list[str]:
    """Break text into small pieces, each at most `limit` tokens.

    Prefer paragraphs; if a paragraph is too big use its lines, then its sentences, then words.
    """
    units: list[str] = []
    for block in (b.strip() for b in _BLANK_LINE.split(text)):
        if not block:
            continue
        if estimate_tokens(block) <= limit:
            units.append(block)
            continue
        for line in (ln.strip() for ln in block.split("\n")):
            if not line:
                continue
            if estimate_tokens(line) <= limit:
                units.append(line)
                continue
            for sentence in _SENTENCE_END.split(line):
                if estimate_tokens(sentence) <= limit:
                    units.append(sentence)
                else:
                    units.extend(_split_words(sentence, limit))
    return units


def _tail(text: str, tokens: int) -> str:
    """The last words of `text`, worth about `tokens` tokens (used as the overlap)."""
    words, used, picked = text.split(), 0, []
    for word in reversed(words):
        used += estimate_tokens(word)
        if used > tokens:
            break
        picked.append(word)
    return " ".join(reversed(picked))


def chunk_section_text(body: str, target_tokens: int, overlap_tokens: int) -> list[str]:
    """Cut one section's text into chunks of at most `target_tokens`, overlapping."""
    # Each unit may be at most (target - overlap), so "overlap + unit" always fits in a chunk.
    units = _units(body, max(1, target_tokens - overlap_tokens))
    chunks: list[str] = []
    current: list[str] = []
    used = 0
    for unit in units:
        cost = estimate_tokens(unit)
        if current and used + cost > target_tokens:
            finished = "\n\n".join(current)
            chunks.append(finished)
            tail = _tail(finished, overlap_tokens)
            current = [tail] if tail else []
            used = estimate_tokens(tail)
        current.append(unit)
        used += cost
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_markdown(
    markdown: str,
    fallback_title: str = "",
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[TextChunk]:
    """Turn a whole article into chunks. An empty article gives an empty list."""
    chunks: list[TextChunk] = []
    for section in split_sections(markdown, fallback_title):
        for text in chunk_section_text(section.body, target_tokens, overlap_tokens):
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    heading=section.heading,
                    text=text,
                    token_count=estimate_tokens(embedding_input(section.heading, text)),
                )
            )
    return chunks
