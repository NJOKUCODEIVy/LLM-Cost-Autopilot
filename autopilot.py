"""
The LLM Cost Autopilot: one function that does everything.

handle() routes a prompt to the cheapest suitable model, returns the answer,
and checks a sample of answers in the background. For important requests,
wait_for_check=True checks the answer before returning it, and returns the
stronger model's answer if the cheap one fails ("if latency permits").
"""

import sys

from providers import Response
from router import route
from verifier import VerificationJob, should_check, submit, verify_now, wait_until_done


def handle(prompt: str, wait_for_check: bool = False) -> Response:
    request_id, tier, response = route(prompt)
    job = VerificationJob(request_id, prompt, response.text, response.model_id, tier)

    if wait_for_check:
        # Slower, but the user gets the escalated answer if the cheap one fails
        if should_check(response.model_id, always=True):
            better = verify_now(job)
            if better is not None:
                return better
        return response

    submit(job)  # Background check on a sample of requests; the user doesn't wait
    return response


if __name__ == "__main__":
    if "--demo-escalation" in sys.argv:
        # Simulate a routing failure: pretend gpt-oss-20b gave Qwen's real wrong answer.
        # Uses separate demo files, so your real log and training data stay clean.
        import logger
        import verifier
        from registry import MODEL_REGISTRY

        logger.DB_FILE = "demo.db"
        logger.init_db()
        verifier.FAILURES_FILE = "demo_failures.csv"

        prompt = ("A train leaves at 9:40 a.m. and travels 210 km at 84 km/h. It then waits "
                  "25 minutes, and travels another 96 km at 64 km/h. What time does it arrive?")
        cheap = MODEL_REGISTRY["gpt-oss-20b"]
        wrong_answer = "The train arrives at 3:45 p.m."
        request_id = logger.log_request(prompt, 1, cheap.name, 60, 200, cheap.cost(60, 200), 1.0)

        print(f"Cheap answer from {cheap.name}: {wrong_answer}\n")
        better = verify_now(VerificationJob(request_id, prompt, wrong_answer, cheap.model_id, 1))
        if better is not None:
            print(f"\nAnswer the user gets instead (from {better.model_id}):\n{better.text}")
    else:
        prompt = "Convert 9 kilometers to miles. Reply with the number only."
        answer = handle(prompt)
        print(f"{answer.model_id}: {answer.text}")
        wait_until_done()  # Let any background check finish before the program exits
        