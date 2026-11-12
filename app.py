"""
Cost Autopilot: the public web app.

Signed-out visitors see the landing page. Signing in with Google creates an
account the first time (their sign-up) and opens the chat, where every prompt
is routed to the cheapest suitable model and every response shows its cost.

    streamlit run app.py

To try the chat before Google sign-in is set up (on your own machine only):
    AUTOPILOT_DEV_USER="Your Name" streamlit run app.py
"""
   
import os

from paths import DB_DIR

# Keep the app's traffic in its own database, separate from experiments and the load test
os.environ.setdefault("AUTOPILOT_DB", str(DB_DIR / "app.db"))

import html  # noqa: E402
import time  # noqa: E402

import streamlit as st  # noqa: E402
import openai  # noqa: E402

openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    try:
        openai_key = st.secrets["openai"]["api_key"]
    except Exception:
        openai_key = None
if openai_key:
    openai.api_key = openai_key

import verifier  # noqa: E402
from autopilot import handle_detailed  # noqa: E402
from logger import (  # noqa: E402
    cost_rows, count_requests_today, count_users, get_request, hash_prompt,
    record_rating, register_user, set_request_user,
)
from landing import render_landing  # noqa: E402
from registry import MODEL_REGISTRY  # noqa: E402
from router import ROUTING, choose_model  # noqa: E402
from theme import BASE_CSS, logo_img, tier_meter  # noqa: E402

# Public traffic: never store strangers' prompt text, even for failed responses
verifier.SAVE_FAILURES = False

DAILY_LIMIT = 20          # Requests per account per day
GLOBAL_DAILY_CAP = 300    # Requests per day across everyone, to protect the free API quota
MAX_PROMPT_CHARS = 1_000
BUILT_BY = "Njoku kelechi"  # Shown in the landing page footer
GITHUB_URL = "https://github.com/NJOKUCODEIVy/LLM-Cost-Autopilot"

ACCENT = "#7B1E34"
INK = "#262524"
MUTED = "#66625F"
BORDER = "#DCD8D4"

# "What it would have cost" = the same tokens priced at the most expensive model in the registry
TOP_MODEL = max(MODEL_REGISTRY.values(), key=lambda m: m.output_cost_per_million)
MODEL_BY_ID = {m.model_id: m for m in MODEL_REGISTRY.values()}
EXAMPLES = [
    "Convert 5 km to miles.",
    "Explain inflation in two sentences.",
    "Compare two job offers and recommend one.",
]


# ---------- Accounts ----------

def auth_configured() -> bool:
    """True when Google sign-in credentials are in .streamlit/secrets.toml."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def current_user() -> dict | None:
    """The signed-in person as {"key", "name", "dev"}, or None if nobody is signed in."""
    dev_name = os.getenv("AUTOPILOT_DEV_USER")
    if dev_name:
        return {"key": hash_prompt("dev:" + dev_name), "name": dev_name, "dev": True}
    if auth_configured() and getattr(st.user, "is_logged_in", False):
        identity = st.user.get("sub") or st.user.get("email") or ""
        name = st.user.get("given_name") or st.user.get("name") or "there"
        # Only a fingerprint of the account ID is stored; never the email or name
        return {"key": hash_prompt(str(identity)), "name": str(name), "dev": False}
    return None


def sign_in() -> None:
    if auth_configured():
        st.login()
    else:
        st.session_state.auth_missing = True


def app_totals() -> dict:
    """Everything the app has handled, for the landing page's running total."""
    rows = cost_rows()
    actual = sum(r["cost"] + r["verification_cost"] + r["escalation_cost"] for r in rows)
    baseline = sum(TOP_MODEL.cost(r["input_tokens"], r["output_tokens"]) for r in rows)
    return {
        "requests": len(rows),
        "users": count_users(),
        "saved_usd": max(0.0, baseline - actual),
        "saved_pct": round((1 - actual / baseline) * 100) if baseline else 0,
    }


# ---------- Chat (signed in) ----------

def routing_line(tier: int, model_name: str) -> str:
    return (f'<div class="ca ca-mono" style="display:flex;align-items:center;gap:8px;font-size:13px;color:{MUTED}">'
            f'<span style="display:inline-flex;align-items:center;gap:6px;color:{INK};font-weight:600">'
            f'{tier_meter(tier)}Tier {tier}</span><span aria-hidden="true">→</span>'
            f'<span>routed to <span style="color:{INK}">{html.escape(model_name)}</span></span></div>')


def receipt(msg: dict) -> str:
    saved = round((1 - msg["cost"] / msg["baseline"]) * 100) if msg["baseline"] else 0
    fallback = f' <span style="color:{MUTED}">(fallback)</span>' if msg["fallback"] else ""
    return (f'<div class="ca ca-mono" style="background:#FFFFFF;border:1px solid {BORDER};border-radius:8px;'
            f'padding:8px 14px;display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;font-size:13px">'
            f'<span style="display:inline-flex;align-items:center;gap:6px;font-family:\'IBM Plex Sans\',sans-serif;'
            f'font-weight:600">{tier_meter(msg["tier"])}Tier {msg["tier"]}</span>'
            f'<span>{html.escape(msg["model"])}{fallback}</span><span>${msg["cost"]:.6f}</span>'
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
    return (f'<div class="ca" style="font-size:13px;padding:6px 12px;border-radius:6px;background:#F6E9EC">'
            f'{html.escape(text)}</div>')


def stream_words(text: str):
    """Reveal an already-received response word by word, so long answers feel responsive."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def save_rating(request_id: int, key: str) -> None:
    record_rating(request_id, st.session_state.get(key))


def render_chat(user: dict) -> None:
    st.set_page_config(page_title="Cost Autopilot", page_icon=":material/alt_route:",
                       layout="centered", initial_sidebar_state="expanded")
    st.html(BASE_CSS)

    # The first sign-in creates the account (sign-up); later ones count as visits
    if st.session_state.get("registered_key") != user["key"]:
        if register_user(user["key"]):
            st.toast(f"Welcome, {user['name']}! Your account is ready.", icon=":material/waving_hand:")
        st.session_state.registered_key = user["key"]

    if "messages" not in st.session_state:
        st.session_state.messages = []

    used_today = count_requests_today(user["key"])
    left_today = max(0, DAILY_LIMIT - used_today)
    everyone_today = count_requests_today()
    blocked = None
    if left_today == 0:
        blocked = f"You've used today's {DAILY_LIMIT} requests. They reset at 00:00 UTC."
    elif everyone_today >= GLOBAL_DAILY_CAP:
        blocked = "Today's demo limit has been reached for everyone. Please come back tomorrow."

    answers = [m for m in st.session_state.messages if m["role"] == "assistant"]
    spent = sum(m["cost"] for m in answers)
    baseline = sum(m["baseline"] for m in answers)

    with st.sidebar:
        st.html(f'<div class="ca ca-logo">{logo_img()}Cost Autopilot</div>')
        st.caption(f"Signed in as {user['name']}" + (" (developer mode)" if user["dev"] else ""))
        if st.button("New chat", icon=":material/add:", width="stretch"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("**Requests left today**")
        st.progress(min(1.0, used_today / DAILY_LIMIT), text=f"{left_today} of {DAILY_LIMIT} left")

        st.markdown("**This session**")
        if answers:
            st.metric(f"Saved vs. {TOP_MODEL.name}", f"{round((1 - spent / baseline) * 100)}%")
            st.caption(f"Spent ${spent:.4f} instead of ${baseline:.4f}.")
        else:
            st.caption("Send a prompt to see what it costs.")

        st.markdown("**Routing tiers**")
        st.markdown("\n".join(f"- Tier {tier}: `{name}`" for tier, name in sorted(ROUTING["tiers"].items())))
        st.caption("Prompts are sent to Groq and Google for inference, and their free tiers may use them "
                   "for model training. Don't submit personal or sensitive data.")
        if not user["dev"]:
            st.button("Sign out", icon=":material/logout:", on_click=st.logout, width="stretch")

    if not st.session_state.messages:
        st.markdown(f"## Hi {user['name']}, send a prompt to see where it goes")
        st.caption("Each response shows its tier, the model that answered, and what it cost compared "
                   "with the most expensive model.")
        st.markdown("**Try a prompt from each tier**")
        for column, example in zip(st.columns(len(EXAMPLES)), EXAMPLES):
            if column.button(example, width="stretch", wrap=True, disabled=blocked is not None):
                st.session_state.pending = example
                st.rerun()

    for msg in st.session_state.messages:
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

    if blocked:
        st.html(f'<div class="ca" style="padding:12px 16px;border-radius:10px;background:#F6E9EC;'
                f'border:1px solid #E7CDD3">{html.escape(blocked)}</div>')
    prompt = st.chat_input("Enter a prompt", max_chars=MAX_PROMPT_CHARS, disabled=blocked is not None)
    prompt = prompt or st.session_state.pop("pending", None)
    if not prompt or blocked:
        return

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
            st.session_state.messages.pop()
            st.error("The routed model and its fallback are both unavailable right now. Try again in a minute.")
            return
        latency = time.perf_counter() - start
        set_request_user(result.request_id, user["key"])
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


user = current_user()
if user is None:
    render_landing(sign_in, app_totals(), TOP_MODEL.name, DAILY_LIMIT, GITHUB_URL, BUILT_BY)
else:
    render_chat(user)
