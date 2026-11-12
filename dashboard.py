"""
Phase 4, Steps 2 and 3: the cost dashboard.

Reads every request from autopilot.db and shows what routing saved, which
models handled the traffic, how good the answers were, and how often the
system had to escalate. Start it with:

    streamlit run dashboard.py
"""

import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from logger import DB_FILE
from registry import MODEL_REGISTRY

st.set_page_config(page_title="LLM Cost Autopilot", page_icon="💸", layout="wide")


@st.cache_data(ttl=30)  # Re-read the database at most every 30 seconds
def load_requests() -> pd.DataFrame:
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM requests", conn)
    finally:
        conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    for column in ("escalation_cost", "verification_cost"):
        df[column] = df[column].fillna(0.0)
    # The real bill: the answers, the verifier's checking calls, and re-runs on stronger models
    df["actual_cost"] = df["cost"] + df["verification_cost"] + df["escalation_cost"]
    return df


df = load_requests()

st.title("💸 LLM Cost Autopilot")
if df.empty:
    st.info("No requests logged yet. Run `python simulate_traffic.py` first.")
    st.stop()

# --- Sidebar controls ---
by_price = sorted(MODEL_REGISTRY.values(), key=lambda m: m.output_cost_per_million, reverse=True)
baseline = MODEL_REGISTRY[st.sidebar.selectbox(
    "Compare against sending everything to:", [m.name for m in by_price], index=0
)]
period = st.sidebar.radio("Group charts by:", ["Day", "Week"])

# What each request would have cost on the comparison model, using the same token counts
df["baseline_cost"] = [baseline.cost(i, o) for i, o in zip(df["input_tokens"], df["output_tokens"])]
if period == "Day":
    df["period"] = df["timestamp"].dt.strftime("%Y-%m-%d")
else:
    week_start = df["timestamp"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    df["period"] = "Week of " + week_start.dt.strftime("%Y-%m-%d")

# --- The money shot ---
actual_total = df["actual_cost"].sum()
baseline_total = df["baseline_cost"].sum()
savings_pct = 1 - actual_total / baseline_total if baseline_total else 0.0

st.markdown(
    f"<h2 style='margin-bottom:0'>Routing saved <span style='color:#16a34a'>{savings_pct:.0%}</span> "
    f"compared with sending everything to {baseline.name}</h2>",
    unsafe_allow_html=True,
)
checked = df[df["quality_passed"].notna()]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Requests", f"{len(df)}")
c2.metric("Actual cost", f"${actual_total:.4f}")
c3.metric(f"All on {baseline.name}", f"${baseline_total:.4f}")
c4.metric("You saved", f"${baseline_total - actual_total:.4f}")
c5.metric("Checks passed", f"{checked['quality_passed'].mean():.0%}" if len(checked) else "-",
          help=f"{len(checked)} answers checked by the verifier")
# Backslashes stop Streamlit from reading the $ signs as math formatting
st.caption(
    f"Actual cost breakdown: answers \\${df['cost'].sum():.4f} · "
    f"verification \\${df['verification_cost'].sum():.4f} · "
    f"escalations \\${df['escalation_cost'].sum():.4f}"
)

# --- Cost over time ---
st.subheader(f"Cost per {period.lower()}")
cost_by_period = (
    df.groupby("period")[["actual_cost", "baseline_cost"]].sum().reset_index()
    .rename(columns={"actual_cost": "With routing", "baseline_cost": f"All on {baseline.name}"})
    .melt(id_vars="period", var_name="scenario", value_name="cost")
)
st.altair_chart(
    alt.Chart(cost_by_period).mark_bar().encode(
        x=alt.X("period:N", title=None),
        xOffset="scenario:N",
        y=alt.Y("cost:Q", title="Cost (USD)"),
        color=alt.Color("scenario:N", title=None, legend=alt.Legend(orient="top")),
        tooltip=["period", "scenario", alt.Tooltip("cost:Q", format="$.6f")],
    ),
    width="stretch",
)

left, right = st.columns(2)

# --- Routing distribution ---
with left:
    st.subheader("Which models handled the traffic")
    by_model = df.groupby("model").size().reset_index(name="requests")
    by_model["share"] = by_model["requests"] / by_model["requests"].sum()
    st.altair_chart(
        alt.Chart(by_model).mark_arc(innerRadius=60).encode(
            theta="requests:Q",
            color=alt.Color("model:N", title=None, legend=alt.Legend(orient="bottom")),
            tooltip=["model", "requests", alt.Tooltip("share:Q", format=".0%")],
        ),
        width="stretch",
    )

# --- Quality distribution ---
with right:
    st.subheader("Quality scores of checked answers")
    if checked.empty:
        st.info("No answers have been checked yet.")
    else:
        scores = checked.groupby("quality_score").size().reset_index(name="answers")
        scores["result"] = ["Pass" if s >= 4 else "Fail" for s in scores["quality_score"]]
        st.altair_chart(
            alt.Chart(scores).mark_bar().encode(
                x=alt.X("quality_score:O", title="Score (out of 5)"),
                y=alt.Y("answers:Q", title="Answers"),
                color=alt.Color("result:N", title=None,
                                scale=alt.Scale(domain=["Pass", "Fail"], range=["#16a34a", "#dc2626"])),
                tooltip=["quality_score", "answers"],
            ),
            width="stretch",
        )

# --- Escalation rate over time ---
st.subheader(f"Escalation rate per {period.lower()}")
if checked.empty:
    st.info("No answers have been checked yet.")
else:
    escalations = (
        checked.groupby("period")
        .agg(checked=("id", "count"), escalated=("escalated", "sum"))
        .reset_index()
    )
    escalations["rate"] = escalations["escalated"] / escalations["checked"]
    st.altair_chart(
        alt.Chart(escalations).mark_line(point=True).encode(
            x=alt.X("period:N", title=None),
            y=alt.Y("rate:Q", title="Share of checked answers escalated", axis=alt.Axis(format=".0%")),
            tooltip=["period", "checked", "escalated", alt.Tooltip("rate:Q", format=".0%")],
        ),
        width="stretch",
    )

# --- Per-model detail ---
st.subheader("Per-model detail")
detail = (
    df.groupby("model")
    .agg(requests=("id", "count"), total_cost=("actual_cost", "sum"), avg_cost=("cost", "mean"),
         avg_latency=("latency", "mean"), fallbacks=("fallback_from", "count"))
    .reset_index()
    .sort_values("requests", ascending=False)
)
st.dataframe(
    detail,
    hide_index=True,
    width="stretch",
    column_config={
        "total_cost": st.column_config.NumberColumn("Total cost", format="$%.6f"),
        "avg_cost": st.column_config.NumberColumn("Avg cost", format="$%.6f"),
        "avg_latency": st.column_config.NumberColumn("Avg latency (s)", format="%.2f"),
        "fallbacks": st.column_config.NumberColumn("Answered as fallback"),
    },
)

st.caption(
    "Actual cost includes the answers, the verifier's checking calls, and escalations. "
    f"Comparison costs re-price each request's actual token counts at {baseline.name}'s rates; "
    "a different model would write a different number of tokens, so treat it as an estimate. "
    "All costs use the registry's paid prices."
)
