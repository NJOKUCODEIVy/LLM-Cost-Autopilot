"""
Phase 3, Step 1: define "good enough".

Compares a cheap model's answer with a reference answer from the top model,
using a different check for each kind of request:

  extraction      -> did the cheap answer include every key field?
  classification  -> does its label match the reference label?
  summarization   -> does an LLM judge score it 4 or higher out of 5?
  open-ended      -> same judge check as summarization

The extraction and classification checks are fast and free, but they can
reject a correct answer that is worded differently. So when a fast check
fails, the judge gets the final say.

Every check reports a score from 1 to 5, so the dashboard can chart them together.
"""

import re
from dataclasses import dataclass

from providers import send_request
from registry import MODEL_REGISTRY
from router import ROUTING

JUDGE_PASS_SCORE = 4  # Judge scores of 4 or 5 pass; 1 to 3 fail

# The judge is the tier 3 model from routing.yaml; its fallback steps in if it's down
JUDGE_MODEL = MODEL_REGISTRY[ROUTING["tiers"][3]]
BACKUP_JUDGE = MODEL_REGISTRY[ROUTING["fallback"][JUDGE_MODEL.name]]

# Words that reveal what kind of request a prompt is (checked in this order)
TASK_KEYWORDS = {
    "classification": ["classify", "categorize", "sentiment", "fact or opinion", "spam"],
    # Extraction also covers simple reformatting, which has one correct answer too
    "extraction": ["extract", "pull out", "convert", "format", "reply with",
                   "based on this text", "based only on", "what is the", "how many",
                   "change", "translate", "sort", "put these", "remove", "replace",
                   "count", "capitalize", "abbreviate", "reverse"],
    "summarization": ["summarize", "summary", "main point", "main idea", "key facts"],
}

JUDGE_PROMPT = """You are grading an AI assistant's answer.

Question:
{prompt}

Reference answer from a stronger model:
{reference}

Answer to grade:
{answer}

Score the answer from 1 to 5 for correctness, completeness, and following the
question's instructions. The reference may be worded differently; judge the substance.
5 = as good as the reference, 4 = minor gaps, 3 = noticeable problems,
2 = mostly wrong, 1 = wrong or unusable.
Reply with only the number."""


@dataclass
class QualityResult:
    task_type: str         # extraction, classification, summarization, or open_ended
    method: str            # key_fields, label_match, or judge
    score: float | None    # 1 to 5; None if the judge couldn't be reached
    passed: bool | None    # None if the judge couldn't be reached
    detail: str            # Short explanation, useful when reading the log
    cost: float = 0.0      # USD spent on judge calls for this check (fast checks are free)


def detect_task_type(prompt: str) -> str:
    text = prompt.lower()
    for task_type, keywords in TASK_KEYWORDS.items():
        if any(k in text for k in keywords):
            return task_type
    return "open_ended"


def _normalize(text: str) -> str:
    """Lowercase, and turn punctuation (except @ . : / -) into spaces, for fair comparisons."""
    return " ".join(re.sub(r"[^\w@.:/-]+", " ", text.lower()).split())


def _key_fields(text: str) -> set[str]:
    """Pull out the details an extraction must get right: emails, URLs, and numbers or dates."""
    patterns = [r"[\w.+-]+@[\w-]+\.[\w.]+", r"https?://\S+", r"\d[\d,.:/-]*\d|\d"]
    fields = set()
    for p in patterns:
        fields.update(m.rstrip(".,") for m in re.findall(p, text.lower()))
    return fields


def check_extraction(answer: str, reference: str) -> QualityResult:
    fields = _key_fields(reference)
    answer_norm = _normalize(answer)
    if fields:
        found = [f for f in fields if f in answer.lower()]
        share = len(found) / len(fields)
        detail = f"{len(found)}/{len(fields)} key fields found"
    else:
        # No emails, URLs, or numbers: compare the answers' text directly
        ref_norm = _normalize(reference).rstrip(".")
        share = 1.0 if (ref_norm in answer_norm or answer_norm.rstrip(".") in ref_norm) else 0.0
        detail = "answer matches reference" if share else "answer differs from reference"
    return QualityResult("extraction", "key_fields", 1 + 4 * share, share == 1.0, detail)


def check_classification(answer: str, reference: str) -> QualityResult:
    ref_words = _normalize(reference).split()
    label = ref_words[0].strip(".:") if ref_words else ""
    # The label should appear near the start of the cheap answer
    match = label != "" and label in [w.strip(".:") for w in _normalize(answer).split()[:5]]
    detail = f"reference label '{label}' {'found' if match else 'not found'} in answer"
    return QualityResult("classification", "label_match", 5.0 if match else 1.0, match, detail)


def judge(prompt: str, answer: str, reference: str, task_type: str) -> QualityResult:
    """Ask the top model to score the answer from 1 to 5 (the LLM-as-judge check)."""
    judge_prompt = JUDGE_PROMPT.format(prompt=prompt, reference=reference, answer=answer)
    cost = 0.0
    for model in (JUDGE_MODEL, BACKUP_JUDGE):
        try:
            reply = send_request(judge_prompt, model)
        except Exception:
            continue  # Judge unavailable: try the backup (a failed call costs nothing)
        cost += reply.cost
        found = re.search(r"[1-5]", reply.text)
        if found:
            score = int(found.group())
            return QualityResult(task_type, "judge", float(score), score >= JUDGE_PASS_SCORE,
                                 f"judged {score}/5 by {model.name}", cost)
    return QualityResult(task_type, "judge", None, None, "judge unavailable; not scored", cost)


FAST_CHECKS = {
    "extraction": check_extraction,
    "classification": check_classification,
}


def evaluate(prompt: str, answer: str, reference: str) -> QualityResult:
    """Pick the right check for this prompt and run it."""
    task_type = detect_task_type(prompt)
    if task_type in FAST_CHECKS:
        fast = FAST_CHECKS[task_type](answer, reference)
        if fast.passed:
            return fast
        # The fast check failed, but it may have missed a correctly worded answer,
        # so the judge decides. If the judge is unavailable, keep the fast result.
        judged = judge(prompt, answer, reference, task_type)
        if judged.score is None:
            fast.cost = judged.cost  # Keep the cost of any judge call that was made
            return fast
        judged.detail = f"{fast.detail}; {judged.detail}"
        return judged
    return judge(prompt, answer, reference, task_type)


if __name__ == "__main__":
    # Examples 1 and 3 pass the fast checks with no API calls.
    # Examples 2, 4, and 5 fail or need judging, so they call the judge model.
    examples = [
        # (prompt, cheap answer, reference answer)
        ("Extract the email address from this text: 'Contact Dana at dana.reyes@brightpath.io.'",
         "dana.reyes@brightpath.io", "The email address is dana.reyes@brightpath.io."),
        ("Extract the email address from this text: 'Contact Dana at dana.reyes@brightpath.io.'",
         "dana@brightpath.io", "dana.reyes@brightpath.io"),
        ("Classify this review as positive, negative, or mixed: 'Great screen, awful speakers.'",
         "Mixed", "Mixed. It praises the screen but criticizes the speakers."),
        ("Classify this review as positive, negative, or mixed: 'Great screen, awful speakers.'",
         "Positive", "Mixed"),
        # The real failure from your baseline: Qwen's wrong train answer (uses the judge, so it calls the API)
        ("A train leaves at 9:40 a.m. and travels 210 km at 84 km/h. It then waits 25 minutes, "
         "and travels another 96 km at 64 km/h. What time does it arrive?",
         "The train arrives at 3:45 p.m.",
         "2.5 h + 25 min + 1.5 h = 4 h 25 min after 9:40 a.m., so it arrives at 2:05 p.m."),
    ]
    for prompt, answer, reference in examples:
        r = evaluate(prompt, answer, reference)
        verdict = "PASS" if r.passed else ("FAIL" if r.passed is False else "UNSCORED")
        score = f"{r.score:.1f}" if r.score is not None else "-"
        print(f"{verdict:<8} score {score:>3}  [{r.task_type} / {r.method}] {r.detail}")
        print(f"         answer: {answer[:60]}\n")
