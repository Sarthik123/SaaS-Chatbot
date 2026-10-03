"""Guardrails: rules that keep the bot inside safe limits.

  * Questions are limited to 500 characters.
  * Personal data (emails, phone numbers, card-like numbers) is masked BEFORE a message is saved
    or sent to the AI provider.
  * Text that comes from outside (the visitor's words, article text) is treated as DATA. We
    remove anything in it that looks like our own <question>/<context>/<history> tags, so it
    cannot "close" a tag and pretend to be an instruction.
  * If the model's answer looks like it is reading out our rulebook, we throw it away.

What these rules do NOT do: they are simple pattern checks, not a guarantee. See
docs/SECURITY-AND-PRIVACY.md (Phase 6) for the honest list of limits.
"""

import re

MAX_QUESTION_CHARS = 500


class QuestionError(ValueError):
    """The visitor's message cannot be used (empty or too long). The text is safe to show."""


def clean_question(text: str) -> str:
    """Trim the question and check its length. Raises QuestionError when it is not usable."""
    # Remove control characters (they have no use in a question) but keep normal whitespace.
    text = "".join(ch for ch in text if ch in "\n\t " or ch.isprintable()).strip()
    if not text:
        raise QuestionError("Please type a question.")
    if len(text) > MAX_QUESTION_CHARS:
        raise QuestionError(f"Please keep your question under {MAX_QUESTION_CHARS} characters.")
    return text


# ---------- masking personal data ----------

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 13 to 19 digits, optionally separated by single spaces or hyphens: looks like a card number.
_CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")
# A run that starts and ends with a digit, with digits and the usual phone separators between.
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d ().-]{6,}\d(?![\w-])")


def _mask_phone(match: re.Match) -> str:
    digits = sum(ch.isdigit() for ch in match.group())
    # Fewer than 9 digits is more likely an amount, a date or an order number than a phone number.
    return "[phone]" if 9 <= digits <= 15 else match.group()


def mask_personal_data(text: str) -> str:
    """Replace emails, card-like numbers and phone numbers with [email], [card], [phone]."""
    text = _EMAIL.sub("[email]", text)
    text = _CARD.sub("[card]", text)
    return _PHONE.sub(_mask_phone, text)


# ---------- keeping outside text inside its box ----------

_OUR_TAGS = re.compile(r"</?\s*(?:question|context|history)\b[^>]*>", re.IGNORECASE)


def neutralize_tags(text: str) -> str:
    """Remove look-alikes of the tags we use to fence off data."""
    return _OUR_TAGS.sub("[tag removed]", text)


# ---------- spotting a leaked rulebook ----------

_LEAK_MARKERS = (
    "used_chunk_ids",
    "can_answer",
    "<context",
    "<question",
    "help-article excerpts",
    "never follow instructions found",
    "reveal, repeat or describe these rules",
)


def looks_like_rule_leak(answer: str) -> bool:
    """True when the answer contains phrases that only appear in our hidden rulebook."""
    lowered = answer.lower()
    return any(marker in lowered for marker in _LEAK_MARKERS)
