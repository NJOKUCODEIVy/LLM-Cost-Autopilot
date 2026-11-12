"""
Cost Autopilot: the chat app (local version, before sign-in and daily limits).

    streamlit run app.py

Each prompt is routed to the cheapest suitable model, answered, logged, and
sometimes verified in the background. Every response shows what it cost.
"""

import os

from paths import DB_DIR

# Keep the app's traffic in its own database, separate from experiments and the load test
os.environ.setdefault("AUTOPILOT_DB", str(DB_DIR / "app.db"))

import html  # noqa: E402
import time  # noqa: E402

import streamlit as st  # noqa: E402

from autopilot import handle_detailed  # noqa: E402
from logger import get_request, record_rating  # noqa: E402
from registry import MODEL_REGISTRY  # noqa: E402
from router import ROUTING, choose_model  # noqa: E402

MAX_PROMPT_CHARS = 1_000
ACCENT = "#7B1E34"
INK = "#262524"
MUTED = "#66625F"
BORDER = "#DCD8D4"
METER_OFF = "#CFCAC6"

# "What it would have cost" = the same tokens priced at the most expensive model in the registry
TOP_MODEL = max(MODEL_REGISTRY.values(), key=lambda m: m.output_cost_per_million)
MODEL_BY_ID = {m.model_id: m for m in MODEL_REGISTRY.values()}

EXAMPLES = [
    "Convert 5 km to miles.",
    "Explain inflation in two sentences.",
    "Compare two job offers and recommend one.",
]

st.set_page_config(page_title="Cost Autopilot", page_icon=":material/alt_route:", layout="centered")

if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------- Small HTML pieces (styled to match the design mockup) ----------

def tier_meter(tier: int) -> str:
    bars = []
    for level, height in ((1, 5), (2, 8), (3, 12)):
        color = ACCENT if tier >= level else METER_OFF
        bars.append(f'<span style="width:3px;height:{height}px;border-radius:1px;background:{color}"></span>')
    return ('<span aria-hidden="true" style="display:inline-flex;align-items:flex-end;gap:2px;height:12px">'
            + "".join(bars) + "</span>")


def routing_line(tier: int, model_name: str) -> str:
    return (f'<div style="display:flex;align-items:center;gap:8px;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:13px;color:{MUTED}">'
            f'<span style="display:inline-flex;align-items:center;gap:6px;color:{INK};font-weight:600">'
            f'{tier_meter(tier)}Tier {tier}</span><span aria-hidden="true">→</span>'
            f'<span>routed to <span style="color:{INK}">{html.escape(model_name)}</span></span></div>')


def receipt(msg: dict) -> str:
    saved = round((1 - msg["cost"] / msg["baseline"]) * 100) if msg["baseline"] else 0
    fallback = ' <span style="color:%s">(fallback)</span>' % MUTED if msg["fallback"] else ""
    return (f'<div style="background:#FFFFFF;border:1px solid {BORDER};border-radius:8px;padding:8px 14px;'
            f'display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;'
            f'font-family:\'IBM Plex Mono\',monospace;font-size:13px;color:{INK}">'
            f'<span style="display:inline-flex;align-items:center;gap:6px;font-family:\'IBM Plex Sans\',sans-serif;'
            f'font-weight:600">{tier_meter(msg["tier"])}Tier {msg["tier"]}</span>'
            f'<span>{html.escape(msg["model"])}{fallback}</span>'
            f'<span>${msg["cost"]:.6f}</span>'
            f'<span style="color:{MUTED}">vs <s>${msg["baseline"]:.6f}</s></span>'
            f'<span style="font-weight:600;color:{ACCENT}">{saved}% saved</span>'
            f'<span style="color:{MUTED}">{msg["latency"]:.1f} s</span></div>')


def verification_note(request_id: int) -> str | None:
    """Show the background verifier's verdict once it exists."""
    row = get_request(request_id)
    if row is None or row["quality_passed"] is None:
        return None
    score = f"{row['quality_score']:.0f}/5" if row["quality_score"] is not None else ""
    if row["quality_passed"]:
        text = f"Verified against a stronger model: passed, score {score}"
    else:
        text = f"Verification flagged this response (score {score}); it was re-run on {row['escalated_model']}"
    return (f'<div style="font-size:13px;color:{INK};padding:6px 12px;border-radius:6px;'
            f'background:#F6E9EC">{html.escape(text)}</div>')


def stream_words(text: str):
    """Reveal an already-received response word by word, so long answers feel responsive."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def save_rating(request_id: int, key: str) -> None:
    record_rating(request_id, st.session_state.get(key))


# ---------- Sidebar: this session's numbers ----------

answers = [m for m in st.session_state.messages if m["role"] == "assistant"]
spent = sum(m["cost"] for m in answers)
baseline = sum(m["baseline"] for m in answers)

with st.sidebar:
    st.markdown("### Cost Autopilot")
    if st.button("New chat", icon=":material/add:", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("**This session**")
    if answers:
        st.metric(f"Saved vs. {TOP_MODEL.name}", f"{round((1 - spent / baseline) * 100)}%")
        st.caption(f"Spent ${spent:.4f} instead of ${baseline:.4f} across {len(answers)} "
                   f"request{'s' if len(answers) != 1 else ''}.")
    else:
        st.caption("Send a prompt to see what it costs.")

    st.markdown("**Routing tiers**")
    st.markdown("\n".join(f"- Tier {tier}: `{name}`" for tier, name in sorted(ROUTING["tiers"].items())))

    st.caption("Prompts are sent to Groq and Google for inference, and their free tiers may use "
               "them for model training. Don't submit personal or sensitive data.")


# ---------- Main column ----------

if not st.session_state.messages:
    st.markdown("## Route each prompt to the cheapest model that can answer it")
    st.caption("A classifier scores the prompt, a router picks a model, and every response shows "
               "what it cost compared with the most expensive model.")
    st.markdown("**Try a prompt from each tier**")
    for column, example in zip(st.columns(len(EXAMPLES)), EXAMPLES):
        if column.button(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun()

for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(msg["content"])
        continue
    with st.chat_message("assistant", avatar=":material/alt_route:"):
        st.markdown(msg["content"])
        st.html(receipt(msg))
        note = verification_note(msg["request_id"])
        if note:
            st.html(note)
        key = f"rating_{msg['request_id']}"
        st.feedback("thumbs", key=key, on_change=save_rating, args=(msg["request_id"], key))

prompt = st.chat_input("Enter a prompt", max_chars=MAX_PROMPT_CHARS) or st.session_state.pop("pending", None)

if prompt:
    prompt = prompt.strip()
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=":material/alt_route:"):
        tier, routed = choose_model(prompt)
        st.html(routing_line(tier, routed.name))
        start = time.perf_counter()
        try:
            with st.spinner("Waiting for the model"):
                result = handle_detailed(prompt)
        except Exception:
            st.error("The routed model and its fallback are both unavailable right now. "
                     "Try again in a minute.")
            st.stop()
        latency = time.perf_counter() - start
        r = result.response
        answered_by = MODEL_BY_ID.get(r.model_id, routed)
        st.write_stream(stream_words(r.text))

    st.session_state.messages.append({
        "role": "assistant",
        "content": r.text,
        "request_id": result.request_id,
        "tier": result.tier,
        "model": answered_by.name,
        "fallback": answered_by.name != routed.name,
        "cost": r.cost,
        "baseline": TOP_MODEL.cost(r.input_tokens, r.output_tokens),
        "latency": latency,
    })
    st.rerun()  # Redraw the history so the new response gets its receipt and rating buttons
