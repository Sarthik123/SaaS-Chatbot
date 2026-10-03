"""A terminal tool for testing the bot by hand.

    python -m app.cli ask "How do I set up recurring invoices?"
    python -m app.cli ask --demo "Do you support payroll?"

It prints, in plain text: the chunks that were found with their scores, the decision (answer or
"I don't know" and why), and the final answer with its citations. Nothing is saved.

  * Without --demo it searches the database named in DATABASE_URL (load it first with
    `python -m app.rag.ingest ../data/demo_kb`).
  * With --demo it loads the demo articles into memory first, so no database is needed.
    (With a real AI provider this still costs a few embedding calls.)
"""

import argparse
import sys

from app.config import REPO_ROOT, get_settings
from app.db import InMemoryRepository, build_repository
from app.providers import (
    ProviderError,
    build_embedding_provider,
    build_llm_provider,
)
from app.rag.answer import answer_question
from app.rag.guardrails import QuestionError, clean_question, mask_personal_data
from app.rag.ingest import ingest_directory


def _print_result(question: str, result, min_similarity: float) -> None:
    retrieval = result.retrieval
    print(f"QUESTION: {question}\n")
    print(f"FOUND (best {len(retrieval.chunks)}, MIN_SIMILARITY = {min_similarity}):")
    if not retrieval.chunks:
        print("  nothing")
    for number, chunk in enumerate(retrieval.chunks, start=1):
        hit = chunk.hit
        verdict = "PASS" if chunk.passes else "below threshold"
        print(
            f"  {number}. [{verdict}] similarity={hit.similarity:.3f} "
            f"keyword={hit.keyword_score:.3f} fused={chunk.rrf_score:.4f}\n"
            f"     {hit.heading}  (chunk {hit.chunk_id}, article '{hit.article_slug}')"
        )
    print()
    if result.abstained:
        print(f"DECISION: ABSTAIN (reason: {result.reason})")
    else:
        print("DECISION: ANSWER")
    print(f"AI model called: {'yes' if result.llm_calls else 'no'} ({result.llm_calls} call(s))")
    print(f"\nANSWER:\n  {result.answer}\n")
    if result.citations:
        print("CITATIONS:")
        for citation in result.citations:
            print(f"  - {citation.title} ({citation.url}), chunk {citation.chunk_id}")
            print(f'    "{citation.quote}"')
    if result.llm_calls:
        print(
            f"\nTokens: input {result.input_tokens}, output {result.output_tokens}, "
            f"model {result.model}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="ask the bot one question")
    ask.add_argument("question")
    ask.add_argument(
        "--demo",
        action="store_true",
        help="load data/demo_kb into memory first (no database needed)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    embedder = build_embedding_provider(settings)
    llm = build_llm_provider(settings)
    try:
        question = mask_personal_data(clean_question(args.question))
        if args.demo:
            repo = InMemoryRepository(settings.embedding_dim)
            report = ingest_directory(REPO_ROOT / "data" / "demo_kb", repo, embedder)
            print(
                f"(demo: loaded {report.articles} articles, {report.chunks} chunks into memory)\n"
            )
        else:
            if not settings.database_url.get_secret_value():
                print(
                    "DATABASE_URL is not set. Either set it (and run the ingest command first) "
                    "or add --demo.",
                    file=sys.stderr,
                )
                return 2
            repo = build_repository(settings)
        result = answer_question(
            question,
            [],
            repo,
            embedder,
            llm,
            min_similarity=settings.min_similarity,
            max_output_tokens=settings.max_output_tokens,
        )
    except QuestionError as error:
        print(str(error), file=sys.stderr)
        return 2
    except ProviderError as error:
        print(f"AI provider problem: {error}", file=sys.stderr)
        return 1
    _print_result(question, result, settings.min_similarity)
    return 0


if __name__ == "__main__":
    sys.exit(main())
