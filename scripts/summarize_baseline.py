"""
Phase 1, Step 3: summarize the baseline results.

Reads data/baseline_results.csv and prints two tables:
1. Per model: successful and failed calls, average latency, average output
   tokens, and total cost.
2. Per model: whether it got each question with one correct answer right.

    python -m scripts.summarize_baseline
"""

import csv
import re
from collections import defaultdict

from paths import BASELINE_RESULTS

INPUT_FILE = BASELINE_RESULTS

# Questions with one correct answer, and a pattern that matches that answer
CHECKABLE = {
    1: r"2025-03-07",
    2: r"dana\.reyes@brightpath\.io",
    3: r"\b1998\b",
    5: r"\bmixed\b",
    7: r"(?<!\d)(2:05|14:05)(?!\d)",  # Accepts "2:05pm" and "14:05", rejects "12:05"
}


def load_rows():
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def print_cost_and_speed(rows):
    stats = defaultdict(lambda: {"ok": 0, "failed": 0, "latency": 0.0, "out_tokens": 0, "cost": 0.0})
    for row in rows:
        s = stats[row["model"]]
        if row["error"]:
            s["failed"] += 1
            continue
        s["ok"] += 1
        s["latency"] += float(row["latency"])
        s["out_tokens"] += int(row["output_tokens"])
        s["cost"] += float(row["cost"])

    print(f"{'Model':<22} {'OK':>3} {'Fail':>5} {'Avg latency':>12} {'Avg out tokens':>15} {'Total cost':>12}")
    for model, s in stats.items():
        n = s["ok"] or 1  # Avoid dividing by zero if every call failed
        print(f"{model:<22} {s['ok']:>3} {s['failed']:>5} {s['latency'] / n:>11.2f}s "
              f"{s['out_tokens'] / n:>15.0f} {'$' + format(s['cost'], '.6f'):>12}")


def print_accuracy(rows):
    checks = defaultdict(dict)  # model -> {prompt_id: True or False}
    for row in rows:
        pid = int(row["prompt_id"])
        if pid in CHECKABLE:
            correct = bool(re.search(CHECKABLE[pid], row["answer"], re.IGNORECASE))
            checks[row["model"]][pid] = correct and not row["error"]

    header = "".join(f"Q{pid:<4}" for pid in CHECKABLE)
    print(f"{'Model':<22} {header} Score")
    for model, results in checks.items():
        marks = "".join(f"{'✓' if results.get(pid) else '✗':<5}" for pid in CHECKABLE)
        score = sum(results.values())
        print(f"{model:<22} {marks} {score}/{len(CHECKABLE)}")


if __name__ == "__main__":
    rows = load_rows()
    print(f"Loaded {len(rows)} results from {INPUT_FILE}\n")
    print_cost_and_speed(rows)
    print("\nCorrect answers on questions with one right answer (✗ also means the call failed):\n")
    print_accuracy(rows)
