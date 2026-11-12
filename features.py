"""
Phase 2, Step 2: feature extraction.

Turns a prompt into a handful of numbers (features) that the classifier
can learn from. These are the features listed in the project brief:
token count, instruction words, number of constraints, whether context
is provided, and output format complexity.
"""

import re

# Instruction words grouped by the tier they usually signal
SIMPLE_WORDS = [
    "convert", "extract", "format", "translate", "sort", "capitalize",
    "uppercase", "lowercase", "remove", "replace", "count", "abbreviate",
    "reverse", "spell", "plural", "pull out", "what is the", "how many",
]
MODERATE_WORDS = [
    "summarize", "summary", "classify", "categorize", "group", "rewrite",
    "paraphrase", "simplify", "explain", "describe", "identify", "tag",
    "pros", "cons", "strengths", "weaknesses", "main point", "main idea",
]
COMPLEX_WORDS = [
    "analyze", "analyse", "compare", "evaluate", "recommend", "justify",
    "prove", "design", "step by step", "trade-offs", "weigh", "discuss",
    "debug", "plan", "estimate", "should", "ethical", "strategy",
    "story", "poem", "haiku", "limerick", "speech", "dialogue", "scene",
    "fable", "letter", "verse", "invent",
]

# Phrases that add a rule the answer must follow
CONSTRAINT_PATTERNS = [
    r"\bunder \d+", r"\bexactly\b", r"\bonly\b", r"\bat most\b", r"\bno more than\b",
    r"\bin (one|two|three|four|five|\d+) (sentence|word|line|bullet)",
    r"\b(one|two|three|four|five|\d+) (sentences|words|lines|bullet points)\b",
    r"\brhyme\b", r"\brounded\b", r"\breply with\b", r"\bkeep it\b",
    r"\bwithout\b", r"\busing\b", r"\bwith the (fields|columns)\b",
]

# Output formats, from short answers up to long-form or code
LONG_OUTPUTS = ["story", "poem", "haiku", "limerick", "speech", "dialogue", "scene",
                "fable", "letter", "verse", "essay", "schema", "function", "class",
                "algorithm", "api", "plan", "strategy", "paragraph"]
STRUCTURED_OUTPUTS = ["json", "table", "csv", "bullet", "numbered", "list", "steps"]


def _count_matches(text: str, words: list[str]) -> int:
    """Count how many of the words or phrases appear in the text as whole words."""
    return sum(1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", text))


def extract_features(prompt: str) -> dict:
    text = prompt.lower()

    # A quoted passage of 5+ words, or an explicit "Text:" label, counts as provided context
    has_context = bool(re.search(r"'[^']*(?:\s+[^'\s]+){4,}[^']*'", prompt) or "text:" in text)

    if _count_matches(text, LONG_OUTPUTS):
        output_complexity = 3
    elif _count_matches(text, STRUCTURED_OUTPUTS):
        output_complexity = 2
    else:
        output_complexity = 1

    return {
        "token_count": round(len(prompt) / 4),  # Rough rule: about 4 characters per token
        "simple_words": _count_matches(text, SIMPLE_WORDS),
        "moderate_words": _count_matches(text, MODERATE_WORDS),
        "complex_words": _count_matches(text, COMPLEX_WORDS),
        "num_constraints": sum(1 for p in CONSTRAINT_PATTERNS if re.search(p, text)),
        "has_context": int(has_context),
        "output_complexity": output_complexity,
    }


FEATURE_NAMES = list(extract_features("example").keys())


if __name__ == "__main__":
    import csv
    from collections import defaultdict

    from paths import LABELED_PROMPTS

    with open(LABELED_PROMPTS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Average each feature per tier, to see whether the features tell the tiers apart
    totals = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    for row in rows:
        counts[row["tier"]] += 1
        for name, value in extract_features(row["prompt"]).items():
            totals[row["tier"]][name] += value

    print(f"Average feature values per tier ({len(rows)} prompts)\n")
    print(f"{'Feature':<18}" + "".join(f"{'Tier ' + t:>9}" for t in sorted(counts)))
    for name in FEATURE_NAMES:
        print(f"{name:<18}" + "".join(f"{totals[t][name] / counts[t]:>9.2f}" for t in sorted(counts)))
