"""Keyword-search helpers shared by both repositories.

Postgres does keyword search itself (its "full-text search"). The in-memory fake needs a small
imitation of it so that tests behave the same way. Both use the same rules:

  * words are matched after "stemming", so "invoices" matches "invoice" and "recurring"
    matches "recur";
  * very common words ("the", "how", "do", ...) are ignored (these are Postgres' own English
    stop words);
  * a hyphenated code such as ERR-5003 is treated as one exact term, so error codes can be found.
"""

import re
from collections import Counter

from snowballstemmer import stemmer as _make_stemmer

# Postgres' English stop-word list (tsearch_data/english.stop).
STOPWORDS = frozenset(
    """i me my myself we our ours ourselves you your yours yourself yourselves he him his himself
    she her hers herself it its itself they them their theirs themselves what which who whom this
    that these those am is are was were be been being have has had having do does did doing a an
    the and but if or because as until while of at by for with about against between into
    through during before after above below to from up down in out on off over under again
    further then once here there when where why how all any both each few more most other some
    such no nor not only own same so than too very s t can will just don should now""".split()
)

_QUERY_WORD = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
_PIECE = re.compile(r"[a-z0-9]+")
_STEMMER = _make_stemmer("english")
MAX_QUERY_WORDS = 40


def query_words(text: str) -> list[str]:
    """The words of a question, lower-case, without duplicates.

    "ERR-5003" stays one word. The word "or" is dropped because Postgres' web-search syntax
    treats it as an operator.
    """
    words: list[str] = []
    seen: set[str] = set()
    for match in _QUERY_WORD.findall(text):
        word = match.lower()
        if word == "or" or word in seen:
            continue
        seen.add(word)
        words.append(word)
        if len(words) >= MAX_QUERY_WORDS:
            break
    return words


def web_query(words: list[str]) -> str:
    """Words joined with OR, for Postgres' websearch_to_tsquery: 'late or fee or err-5003'."""
    return " or ".join(words)


def _stems(text: str) -> list[str]:
    pieces = [p for p in _PIECE.findall(text.lower()) if p not in STOPWORDS]
    return _STEMMER.stemWords(pieces)


def index_terms(text: str) -> Counter:
    """How often each stemmed word appears in a chunk (used by the in-memory fake)."""
    return Counter(_stems(text))


def keyword_score(chunk_terms: Counter, words: list[str]) -> float:
    """0 when the chunk matches none of the words. Otherwise bigger = better match.

    A query word matches when all of its stemmed pieces are in the chunk (so ERR-5003 needs both
    "err" and "5003"). Each matching word adds 1, plus a little for repeated mentions.
    """
    score = 0.0
    for word in words:
        pieces = _stems(word)
        if pieces and all(piece in chunk_terms for piece in pieces):
            score += 1.0 + 0.1 * min(min(chunk_terms[piece] for piece in pieces), 5)
    return score
