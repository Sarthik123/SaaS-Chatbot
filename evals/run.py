#!/usr/bin/env python3
"""Eval runner: runs 30 questions through the RAG pipeline and writes a report.

Run from the repo root (api/ and evals/ must be siblings):

    cd api
    LLM_PROVIDER=fake python ../evals/run.py

Or against real AI keys (make sure the demo articles are ingested first):

    LLM_PROVIDER=cloudflare python ../evals/run.py

The script writes two files:
  evals/results/latest.json   — raw data (JSON)
  docs/EVALS.md               — human-readable summary (Markdown)

What is measured (see AGENTS.md and docs/EVALS.md for explanations):
  answered_correctly  — should_answer=true AND abstained=false
  abstained_correctly — should_answer=false AND abstained=true
  false_positive      — should_answer=false but the bot gave an answer
  false_negative      — should_answer=true but the bot abstained

The script does NOT measure answer quality (right vs wrong facts). That needs a
human evaluator or a separate LLM judge and is out of scope for Phase 5. Only
answer/no-answer decisions are checked automatically.
"""

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Add the api/ folder to the path so we can import app.* regardless of CWD.
API_DIR = Path(__file__).resolve().parent.parent / "api"
EVALS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(API_DIR))

from app.config import get_settings
from app.db import build_repository
from app.providers import build_embedding_provider, build_llm_provider
from app.rag.answer import answer_question

QUESTIONS_FILE = EVALS_DIR / "questions.json"
RESULTS_DIR = EVALS_DIR / "results"
EVALS_DOC = Path(__file__).resolve().parent.parent / "docs" / "EVALS.md"


def run_eval() -> dict:
    settings = get_settings()
    repo = build_repository(settings)
    embedder = build_embedding_provider(settings)
    llm = build_llm_provider(settings)

    questions = json.loads(QUESTIONS_FILE.read_text())
    results = []

    for q in questions:
        start = time.perf_counter()
        try:
            result = answer_question(
                q["question"],
                [],
                repo,
                embedder,
                llm,
                min_similarity=settings.min_similarity,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            results.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "should_answer": q["should_answer"],
                    "source_article": q["source_article"],
                    "abstained": result.abstained,
                    "answer": result.answer if not result.abstained else "",
                    "reason": result.reason,
                    "citations": [c.as_dict() for c in result.citations],
                    "latency_ms": latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "model": result.model,
                }
            )
        except Exception as error:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - start) * 1000)
            results.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "should_answer": q["should_answer"],
                    "source_article": q["source_article"],
                    "abstained": True,
                    "answer": "",
                    "reason": f"exception: {error}",
                    "citations": [],
                    "latency_ms": latency_ms,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "model": None,
                }
            )

    # Compute summary metrics
    total = len(results)
    answered_correctly = sum(
        1 for r in results if r["should_answer"] and not r["abstained"]
    )
    abstained_correctly = sum(
        1 for r in results if not r["should_answer"] and r["abstained"]
    )
    false_positives = sum(
        1 for r in results if not r["should_answer"] and not r["abstained"]
    )
    false_negatives = sum(
        1 for r in results if r["should_answer"] and r["abstained"]
    )
    should_answer_total = sum(1 for r in results if r["should_answer"])
    should_not_answer_total = sum(1 for r in results if not r["should_answer"])

    latencies = [r["latency_ms"] for r in results if r["latency_ms"] is not None]
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[int(len(latencies_sorted) * 0.50)] if latencies_sorted else None
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else None

    provider = settings.llm_provider
    model = next((r["model"] for r in results if r["model"]), "unknown")

    summary = {
        "ran_at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model,
        "min_similarity": settings.min_similarity,
        "total_questions": total,
        "should_answer": should_answer_total,
        "should_not_answer": should_not_answer_total,
        "answered_correctly": answered_correctly,
        "abstained_correctly": abstained_correctly,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "answer_recall": answered_correctly / should_answer_total if should_answer_total else 0,
        "abstain_precision": abstained_correctly / should_not_answer_total if should_not_answer_total else 0,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
    }

    return {"summary": summary, "results": results}


def write_results(data: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = RESULTS_DIR / "latest.json"
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Wrote {output}")


def write_evals_md(data: dict) -> None:
    s = data["summary"]

    def pct(n: float) -> str:
        return f"{n * 100:.1f}%"

    def ms(n) -> str:
        return f"{n} ms" if n is not None else "not measured"

    lines = [
        "# Eval results",
        "",
        "> Auto-generated by `evals/run.py`. Do not edit by hand.",
        "",
        "## What this measures",
        "",
        "The eval set has 30 questions: 26 that the bot **should** answer (they are covered by the",
        "demo knowledge base) and 4 that it **should not** answer (off-topic or adversarial).",
        "",
        "Only the answer-or-abstain decision is checked automatically. Whether the answer is",
        "factually correct requires a human to read each reply.",
        "",
        "## Latest run",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Ran at | {s['ran_at']} |",
        f"| Provider | {s['provider']} |",
        f"| Model | {s['model']} |",
        f"| MIN_SIMILARITY | {s['min_similarity']} |",
        f"| Total questions | {s['total_questions']} |",
        f"| Should answer | {s['should_answer']} |",
        f"| Should NOT answer | {s['should_not_answer']} |",
        "",
        "## Results",
        "",
        f"| Metric | Count | Rate |",
        f"|---|---|---|",
        f"| Answered correctly (should_answer=true, not abstained) | {s['answered_correctly']} | {pct(s['answer_recall'])} of answerable questions |",
        f"| Abstained correctly (should_answer=false, abstained) | {s['abstained_correctly']} | {pct(s['abstain_precision'])} of off-topic questions |",
        f"| False positives (answered when should not have) | {s['false_positives']} | — |",
        f"| False negatives (abstained when should have answered) | {s['false_negatives']} | — |",
        "",
        "## Speed",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| p50 latency | {ms(s['p50_latency_ms'])} |",
        f"| p95 latency | {ms(s['p95_latency_ms'])} |",
        "",
        "## Per-question detail",
        "",
        "| ID | Question | Should answer | Abstained | Reason |",
        "|---|---|---|---|---|",
    ]
    for r in data["results"]:
        tick = "✓" if r["should_answer"] != r["abstained"] else "✗"
        lines.append(
            f"| {r['id']} {tick} | {r['question'][:60]} | {'yes' if r['should_answer'] else 'no'} | {'yes' if r['abstained'] else 'no'} | {r['reason']} |"
        )

    lines += [
        "",
        "## How to improve",
        "",
        "- **False negatives** (bot abstained on answerable questions): lower `MIN_SIMILARITY` or improve the demo articles.",
        "- **False positives** (bot answered off-topic questions): raise `MIN_SIMILARITY`.",
        "- **Answer quality** (factually wrong answers): improve the LLM prompt in `api/app/rag/answer.py` or add more detail to the articles.",
        "",
        "Run `evals/run.py` again after any change and compare `evals/results/latest.json` to the previous run.",
    ]

    EVALS_DOC.write_text("\n".join(lines) + "\n")
    print(f"Wrote {EVALS_DOC}")


def main() -> None:
    print("Running 30-question eval set…")
    data = run_eval()
    write_results(data)
    write_evals_md(data)

    s = data["summary"]
    print(f"\nSummary:")
    print(f"  Answered correctly:  {s['answered_correctly']}/{s['should_answer']} ({s['answer_recall']*100:.1f}%)")
    print(f"  Abstained correctly: {s['abstained_correctly']}/{s['should_not_answer']} ({s['abstain_precision']*100:.1f}%)")
    print(f"  False positives:     {s['false_positives']}")
    print(f"  False negatives:     {s['false_negatives']}")
    if s["p50_latency_ms"] is not None:
        print(f"  p50 latency: {s['p50_latency_ms']} ms   p95: {s['p95_latency_ms']} ms")
    print(f"\nProvider: {s['provider']}  Model: {s['model']}  MIN_SIMILARITY: {s['min_similarity']}")


if __name__ == "__main__":
    main()
