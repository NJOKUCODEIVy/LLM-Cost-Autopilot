"""
Phase 5: the HTTP API.

Lets any app use the Autopilot over HTTP, in any programming language,
instead of importing your Python code. Start it with:

    uvicorn api:app --reload

Then open http://localhost:8000 to try every endpoint in your browser.
"""

import sqlite3
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from autopilot import handle_detailed
from logger import DB_FILE

app = FastAPI(
    title="LLM Cost Autopilot",
    description="Routes each prompt to the cheapest model that can handle it, "
                "and checks a sample of answers against a stronger model.",
    version="1.0",
)


class RouteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000, description="The question or task")
    wait_for_check: bool = Field(
        default=False,
        description="Check the answer before returning it, and return a stronger model's "
                    "answer if it fails. Slower, so use it for important requests.",
    )


class RouteResponse(BaseModel):
    request_id: int
    answer: str
    model: str
    tier: int
    cost_usd: float
    latency_s: float
    escalated: bool


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Send visitors of the bare address to the interactive docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    """Quick check that the service is running."""
    return {"status": "ok"}


@app.post("/route", response_model=RouteResponse)
def route_prompt(body: RouteRequest) -> RouteResponse:
    """Answer a prompt with the cheapest suitable model."""
    start = time.perf_counter()
    try:
        result = handle_detailed(body.prompt, body.wait_for_check)
    except Exception as error:
        # Both the routed model and its fallback failed
        raise HTTPException(status_code=502, detail=f"All providers failed ({type(error).__name__})")
    r = result.response
    return RouteResponse(
        request_id=result.request_id,
        answer=r.text,
        model=r.model_id,
        tier=result.tier,
        cost_usd=r.cost,
        latency_s=round(time.perf_counter() - start, 3),
        escalated=result.escalated,
    )


@app.get("/stats")
def stats() -> dict:
    """Totals across every logged request, including verification and escalation costs."""
    conn = sqlite3.connect(DB_FILE)
    try:
        row = conn.execute(
            """SELECT COUNT(*),
                      COALESCE(SUM(cost + COALESCE(verification_cost, 0)
                                   + COALESCE(escalation_cost, 0)), 0),
                      COUNT(quality_passed),
                      AVG(quality_passed),
                      COALESCE(SUM(escalated), 0)
               FROM requests"""
        ).fetchone()
    finally:
        conn.close()
    requests, total_cost, checked, pass_rate, escalations = row
    return {
        "requests": requests,
        "total_cost_usd": round(total_cost, 6),
        "answers_checked": checked,
        "check_pass_rate": None if pass_rate is None else round(pass_rate, 3),
        "escalations": escalations,
    }
