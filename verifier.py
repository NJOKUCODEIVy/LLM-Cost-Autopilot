"""
Phase 3, Steps 2 and 3: the background verifier and auto-escalation.

After the user already has their answer, a background worker:
  1. sends the same prompt to the top model to get a reference answer,
  2. checks the cheap answer against it with quality.evaluate(), and
  3. saves the verdict to that request's row in autopilot.db.

A failed check is a "routing failure": the router sent the prompt to a
model that wasn't good enough. When that happens, the request is escalated:
re-run on the stronger model from routing.yaml, with the original model,
stronger model, extra cost, and quality gap all logged. The prompt is also
saved to routing_failures.csv, so the classifier can learn from it later.

Only a sample of requests is checked, to save free-tier quota.
"""

import csv
import os
import queue
import random
import threading
from dataclasses import dataclass

from logger import record_escalation, record_quality
from paths import ROUTING_FAILURES
from providers import Response, send_request
from quality import BACKUP_JUDGE, JUDGE_MODEL, QualityResult, evaluate
from registry import MODEL_REGISTRY
from router import ROUTING

SAMPLE_RATE = 0.33  # Check about 1 in 3 eligible requests
FAILURES_FILE = str(ROUTING_FAILURES)  # Training examples for the classifier (Phase 3, Step 4)

# The reference answer comes from the top model (tier 3), or its backup if it's down
REFERENCE_MODELS = (JUDGE_MODEL, BACKUP_JUDGE)

MODEL_BY_ID = {m.model_id: m for m in MODEL_REGISTRY.values()}
TIER_OF_MODEL = {name: tier for tier, name in ROUTING["tiers"].items()}


@dataclass
class VerificationJob:
    request_id: int
    prompt: str
    answer: str
    model_id: str  # The model that produced the answer being checked
    tier: int      # The tier the classifier predicted


_jobs: "queue.Queue[VerificationJob]" = queue.Queue()


def _get_reference(prompt: str, skip_model_id: str) -> tuple[str, Response] | None:
    """Get the top model's answer. Never use the model being checked as its own reference."""
    for model in REFERENCE_MODELS:
        if model.model_id == skip_model_id:
            continue
        try:
            return model.name, send_request(prompt, model)
        except Exception:
            continue  # Model unavailable: try the next one
    return None


def _save_failure(job: VerificationJob, corrected_tier: int, detail: str) -> None:
    """Append a routing failure to the CSV that retraining will learn from."""
    is_new = not os.path.exists(FAILURES_FILE)
    with open(FAILURES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["prompt", "predicted_tier", "corrected_tier", "failed_model", "detail"])
        writer.writerow([job.prompt, job.tier, corrected_tier, job.model_id, detail])


def _escalate(job: VerificationJob, result: QualityResult,
              reference_model: str, reference: Response) -> Response | None:
    """Re-run a failed request on the stronger model and log the escalation."""
    original = MODEL_BY_ID[job.model_id]
    target_name = ROUTING["escalation"].get(original.name)
    if target_name is None:
        return None  # Already the strongest model; nothing to escalate to

    if target_name == reference_model:
        # The stronger model already answered this prompt as the reference: reuse it.
        # It's the yardstick the cheap answer was measured against, so it scores 5.
        # Its cost is already counted as verification cost, so there's nothing extra.
        better, better_score, extra_cost = reference, 5.0, 0.0
    else:
        better = send_request(job.prompt, MODEL_REGISTRY[target_name])
        check = evaluate(job.prompt, better.text, reference.text)
        better_score, extra_cost = check.score, better.cost + check.cost

    record_escalation(job.request_id, target_name, extra_cost, better_score)
    _save_failure(job, TIER_OF_MODEL.get(target_name, 3), result.detail)

    gap = f"{result.score:.0f} -> {better_score:.0f}" if better_score is not None else "unknown"
    note = " (reused the reference answer)" if extra_cost == 0.0 else ""
    print(f"    Escalated request #{job.request_id}: {original.name} -> {target_name} | "
          f"quality {gap} out of 5 | extra cost ${extra_cost:.7f}{note}")
    return better


def verify_now(job: VerificationJob) -> Response | None:
    """Check one request right away. Returns the better answer if it was escalated."""
    found = _get_reference(job.prompt, skip_model_id=job.model_id)
    if found is None:
        record_quality(job.request_id, "unknown", None, None, "no reference model available")
        return None
    reference_model, reference = found
    result = evaluate(job.prompt, job.answer, reference.text)
    # Checking isn't free: the reference answer and any judge calls are part of the real bill
    record_quality(job.request_id, result.task_type, result.score, result.passed,
                   f"{result.detail} (reference: {reference_model})",
                   verification_cost=reference.cost + result.cost)
    if result.passed is False:
        print(f"    Routing failure on request #{job.request_id} ({job.model_id}): {result.detail}")
        return _escalate(job, result, reference_model, reference)
    return None


def _worker() -> None:
    """Runs forever in the background, checking one queued request at a time."""
    while True:
        job = _jobs.get()
        try:
            verify_now(job)
        except Exception as error:
            print(f"    Verifier error on request #{job.request_id}: {error}")
        finally:
            _jobs.task_done()


# daemon=True means this thread stops automatically when the main program ends
threading.Thread(target=_worker, daemon=True).start()


def should_check(model_id: str, always: bool = False) -> bool:
    """Skip answers from the top model (nothing stronger to compare with); sample the rest."""
    if model_id == JUDGE_MODEL.model_id:
        return False
    return always or random.random() <= SAMPLE_RATE


def submit(job: VerificationJob, always: bool = False) -> bool:
    """Queue a request for a background check. Returns True if it was queued."""
    if not should_check(job.model_id, always):
        return False
    _jobs.put(job)
    return True


def wait_until_done() -> None:
    """Block until every queued check has finished."""
    _jobs.join()
