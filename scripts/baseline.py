"""
Phase 1, Step 3: baseline test.

Sends every test prompt to every model in the registry and saves the results
to data/baseline_results.csv, so you can compare answers, tokens, latency, and cost.

    python -m scripts.baseline
"""

import csv
import time

from paths import BASELINE_RESULTS
from providers import send_request
from registry import MODEL_REGISTRY
from scripts.test_prompts import TEST_PROMPTS

OUTPUT_FILE = BASELINE_RESULTS
PAUSE_SECONDS = 2  # Short pause between calls to stay within free-tier rate limits

FIELDS = ["prompt_id", "tier", "model", "input_tokens", "output_tokens",
          "latency", "cost", "error", "answer"]


def run_baseline():
    total_calls = len(TEST_PROMPTS) * len(MODEL_REGISTRY)
    call_number = 0

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for item in TEST_PROMPTS:
            for model in MODEL_REGISTRY.values():
                call_number += 1
                print(f"[{call_number}/{total_calls}] Prompt {item['id']} "
                      f"(tier {item['tier']}) -> {model.name}")

                row = {"prompt_id": item["id"], "tier": item["tier"], "model": model.name}
                try:
                    r = send_request(item["prompt"], model)
                    row.update({
                        "input_tokens": r.input_tokens,
                        "output_tokens": r.output_tokens,
                        "latency": round(r.latency, 3),
                        "cost": round(r.cost, 8),
                        "error": "",
                        "answer": r.text,
                    })
                except Exception as e:
                    row.update({
                        "input_tokens": "", "output_tokens": "", "latency": "", "cost": "",
                        "error": str(e)[:200], "answer": "",
                    })
                    print(f"    FAILED: {e}")

                writer.writerow(row)
                f.flush()  # Save each row right away, so nothing is lost if you stop early
                time.sleep(PAUSE_SECONDS)

    print(f"\nDone. Saved {call_number} results to {OUTPUT_FILE}")


if __name__ == "__main__":
    run_baseline()
