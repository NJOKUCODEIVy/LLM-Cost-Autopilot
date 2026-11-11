"""
Phase 3, Step 2: the background verifier.

After the user already has their answer, a background worker:
  1. sends the same prompt to the top model to get a reference answer,
  2. checks the cheap answer against it with quality.evaluate(), and
  3. saves the verdict to that request's row in autopilot.db.

A failed check is a "routing failure": the router sent the prompt to a
model that wasn't good enough. Only a sample of requests is checked, to
save free-tier quota.
"""

import queue
import random
import threading
from dataclasses import dataclass

from logger import record_quality
from providers import Response, send_request
from quality import BACKUP_JUDGE, JUDGE_MODEL, evaluate

SAMPLE_RATE = 0.33  # Check about 1 in 3 eligible requests

# The reference answer comes from the top model (tier 3), or its backup if it's down
REFERENCE_MODELS = (JUDGE_MODEL, BACKUP_JUDGE)


@dataclass
class VerificationJob:
    request_id: int
    prompt: str
    answer: str
    model_id: str  # The model that produced the answer being checked


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


def _verify(job: VerificationJob) -> None:
    found = _get_reference(job.prompt, skip_model_id=job.model_id)
    if found is None:
        record_quality(job.request_id, "unknown", None, None, "no reference model available")
        return
    reference_model, reference = found
    result = evaluate(job.prompt, job.answer, reference.text)
    record_quality(job.request_id, result.task_type, result.score, result.passed,
                   f"{result.detail} (reference: {reference_model})")
    if result.passed is False:
        print(f"    Routing failure on request #{job.request_id} ({job.model_id}): {result.detail}")


def _worker() -> None:
    """Runs forever in the background, checking one queued request at a time."""
    while True:
        job = _jobs.get()
        try:
            _verify(job)
        except Exception as error:
            print(f"    Verifier error on request #{job.request_id}: {error}")
        finally:
            _jobs.task_done()


# daemon=True means this thread stops automatically when the main program ends
threading.Thread(target=_worker, daemon=True).start()


def submit(request_id: int, prompt: str, answer: str, model_id: str,
           always: bool = False) -> bool:
    """Queue a request for checking. Returns True if it was queued.

    Answers from the top model are skipped, since there's nothing stronger to
    compare them with. Other answers are sampled at SAMPLE_RATE unless always=True.
    """
    if model_id == JUDGE_MODEL.model_id:
        return False
    if not always and random.random() > SAMPLE_RATE:
        return False
    _jobs.put(VerificationJob(request_id, prompt, answer, model_id))
    return True


def wait_until_done() -> None:
    """Block until every queued check has finished."""
    _jobs.join()


if __name__ == "__main__":
    from router import route

    prompts = [
        "Convert 9 kilometers to miles. Reply with the number only.",
        "Extract the date from: 'The invoice was issued on 2 March 2026.'",
        "Classify this review as positive, negative, or mixed: 'Fast shipping, but the box was damaged.'",
        "Summarize this in one sentence: 'Our team grew from 5 to 12 people this year, "
        "and we opened a second office in Abuja to serve clients in the north.'",
        "Count how many times the letter r appears in this text: 'strawberry raspberry'. "
        "Reply with the number only.",
        "Explain what a webhook is in two sentences.",
    ]

    print("Answering requests (each answer is ready before its check starts):\n")
    for prompt in prompts:
        request_id, tier, response = route(prompt)
        # always=True checks every request in this demo; normal traffic is sampled
        queued = submit(request_id, prompt, response.text, response.model_id, always=True)
        status = "queued for checking" if queued else "not checked (answered by the top model)"
        print(f"#{request_id} Tier {tier} -> {response.model_id:<22} {status}")

    print("\nWaiting for background checks to finish...\n")
    wait_until_done()
    print("Done. Run 'python logger.py' to see the quality scores.")