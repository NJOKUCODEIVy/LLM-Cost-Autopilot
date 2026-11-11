"""
Phase 6, Step 1c: the 1,000-prompt load test, run in daily batches.

Sends the Dolly prompts through the full Autopilot, like real traffic. Results
go to their own database, loadtest.db, so they stay separate from your earlier
experiments. Progress is saved after every prompt, so you can stop at any time
(Ctrl+C) and the next run picks up where this one left off.

    python load_test.py               # run the next batch (250 prompts)
    python load_test.py --batch 100   # run a smaller batch
    python load_test.py --status      # show progress without sending anything

See the results with:
    AUTOPILOT_DB=loadtest.db streamlit run dashboard.py
"""

import os

# Must be set before importing anything that uses logger.py
os.environ.setdefault("AUTOPILOT_DB", "loadtest.db")

import csv  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

from autopilot import handle  # noqa: E402
from verifier import wait_until_done  # noqa: E402

PROMPTS_FILE = "load_test_prompts.csv"
PROGRESS_FILE = "load_test_progress.txt"
DEFAULT_BATCH = 250
PAUSE_SECONDS = 2            # Space out requests to stay within free-tier rate limits
MAX_FAILURES_IN_A_ROW = 5    # Stop early if a provider is down or today's free quota is used up


def load_prompts() -> list[str]:
    with open(PROMPTS_FILE, newline="", encoding="utf-8") as f:
        return [row["prompt"] for row in csv.DictReader(f)]


def read_progress() -> int:
    """Index of the next prompt to send (0 if the test hasn't started)."""
    if not os.path.exists(PROGRESS_FILE):
        return 0
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        return int(f.read().strip() or 0)


def save_progress(next_index: int) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        f.write(str(next_index))


def main() -> None:
    prompts = load_prompts()
    start = read_progress()

    if "--status" in sys.argv or start >= len(prompts):
        print(f"Load test progress: {start}/{len(prompts)} prompts sent.")
        if start >= len(prompts):
            print("The load test is complete.")
        return

    batch = int(sys.argv[sys.argv.index("--batch") + 1]) if "--batch" in sys.argv else DEFAULT_BATCH
    end = min(start + batch, len(prompts))
    print(f"Sending prompts {start + 1} to {end} of {len(prompts)} (results go to {os.environ['AUTOPILOT_DB']})\n")

    answered, failed, failures_in_a_row = 0, 0, 0
    streak_start = None  # Where the current run of failures began
    for i in range(start, end):
        prompt = prompts[i]
        try:
            response = handle(prompt)
            answered += 1
            failures_in_a_row, streak_start = 0, None
            print(f"[{i + 1}/{len(prompts)}] {response.model_id:<22} ${response.cost:.7f} "
                  f"| {prompt[:45].replace(chr(10), ' ')}")
        except Exception as error:
            failed += 1
            failures_in_a_row += 1
            streak_start = i if streak_start is None else streak_start
            print(f"[{i + 1}/{len(prompts)}] FAILED ({type(error).__name__}) | {prompt[:45].replace(chr(10), ' ')}")
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                # Don't skip these prompts: the next run retries them
                save_progress(streak_start)
                print(f"\n{MAX_FAILURES_IN_A_ROW} failures in a row: a provider may be down, or today's "
                      f"free quota may be used up. Stopping here. The next run resumes at prompt "
                      f"{streak_start + 1}.")
                break
        save_progress(i + 1)
        time.sleep(PAUSE_SECONDS)

    print("\nWaiting for background quality checks to finish...")
    wait_until_done()
    print(f"\nBatch done: {answered} answered, {failed} failed. "
          f"Progress: {read_progress()}/{len(prompts)} prompts sent.")


if __name__ == "__main__":
    main()
    