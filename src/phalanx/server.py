"""PHALANX FastAPI Server & Interactive API.

Provides endpoints for live fights, coach exploit synthesis, fix recommendations,
and serves the standalone dashboard.
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from phalanx.blue_team import make_blue
from phalanx.llm import (
    COACH_MODEL,
    DEFAULT_BLUE_MODEL,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_RED_MODEL,
    FIX_MODEL,
    NEBIUS_BASE_URL,
)
from phalanx.coach import analyze_coverage_gaps, coach, select_instructive_fights
from phalanx.dashboard import render as render_dashboard
from phalanx.fix import propose_fix, write_fix
from phalanx.jobs import NebiusJobDispatcher
from phalanx.personas import list_personas, list_scenarios, load_persona, load_scenario
from phalanx.recon import ThreatRecon
from phalanx.runner import RUNS_DIR, run_fight, save_run
from phalanx.verifier import verify_remediation

app = FastAPI(
    title="PHALANX API",
    description="Autonomous Adversarial Red-Teaming & Self-Hardening Suite for NVIDIA Nemotron Models on Nebius",
    version="0.1.0",
)


class FightRequest(BaseModel):
    persona: str
    scenario: str
    blue_mode: str = "standard"
    max_turns: int = 14


class CoachRequest(BaseModel):
    max_fights: int = 4
    target_gap: bool = True
    target_mechanic: str | None = None


class FixRequest(BaseModel):
    fight_id: str


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    path = render_dashboard()
    return path.read_text()


@app.get("/api/status")
def status() -> dict[str, Any]:
    import os
    has_key = bool(os.environ.get("NEBIUS_API_KEY"))
    mock_mode = os.environ.get("PHALANX_MOCK_MODE", "").lower() in ("true", "1")
    is_live = has_key and not mock_mode
    return {
        "status": "online",
        "engine": "Nebius Token Factory",
        "live_mode": is_live,
        "base_url": NEBIUS_BASE_URL,
        "models": {
            "red_adversary": "nvidia/nemotron-3-ultra",
            "blue_target": "nvidia/nemotron-nano",
            "referee": "nvidia/nemotron-super",
            "coach": "nvidia/nemotron-3-ultra",
            "fix": "nvidia/nemotron-3-ultra",
            "endpoints": {
                "red_adversary": DEFAULT_RED_MODEL,
                "blue_target": DEFAULT_BLUE_MODEL,
                "referee": DEFAULT_JUDGE_MODEL,
                "coach": COACH_MODEL,
                "fix": FIX_MODEL,
            },
        },
        "total_runs": len(list(RUNS_DIR.glob("*.json"))) if RUNS_DIR.exists() else 0,
    }


@app.get("/api/personas")
def get_personas() -> list[dict[str, Any]]:
    names = list_personas()
    return [load_persona(n).model_dump() for n in names]


@app.get("/api/scenarios")
def get_scenarios() -> list[dict[str, Any]]:
    names = list_scenarios()
    return [load_scenario(n).model_dump() for n in names]


@app.get("/api/runs")
def get_runs() -> list[dict[str, Any]]:
    runs = []
    if not RUNS_DIR.exists():
        return []
    for p in sorted(RUNS_DIR.glob("*.json")):
        if p.name.startswith("_") or p.name.endswith(".fix.json"):
            continue
        try:
            data = json.loads(p.read_text())
            runs.append(data)
        except Exception:
            continue
    return runs


@app.get("/api/gaps")
def get_gaps() -> list[dict[str, Any]]:
    gaps = analyze_coverage_gaps(RUNS_DIR)
    return [
        {
            "category": g.attack_category,
            "n_runs": g.n_runs,
            "red_wins": g.red_wins,
            "red_win_rate": g.red_win_rate,
            "avg_red_score": g.avg_red_score,
            "gap_score": g.gap_score,
        }
        for g in gaps
    ]


@app.post("/api/fight")
def post_fight(req: FightRequest) -> dict[str, Any]:
    try:
        persona = load_persona(req.persona)
        scenario = load_scenario(req.scenario)
        blue = make_blue(mode=req.blue_mode)
        transcript, verdict = run_fight(
            persona=persona,
            scenario=scenario,
            max_turns=req.max_turns,
            blue=blue,
        )
        saved_path = save_run(transcript, verdict, label=f"{persona.name}-{req.blue_mode}")
        return {
            "transcript": transcript.model_dump(mode="json"),
            "verdict": verdict.model_dump(mode="json"),
            "saved_file": saved_path.name,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/fight/stream")
def post_fight_stream(req: FightRequest) -> StreamingResponse:
    """Stream live adversarial duel events (thinking, tools, utterances, verdict) in real time."""
    def event_stream():
        q: queue.Queue[tuple[str, Any]] = queue.Queue()

        def on_event(event_type: str, data: Any) -> None:
            q.put((event_type, data))

        def worker() -> None:
            try:
                persona = load_persona(req.persona)
                scenario = load_scenario(req.scenario)
                blue = make_blue(mode=req.blue_mode)
                transcript, verdict = run_fight(
                    persona=persona,
                    scenario=scenario,
                    max_turns=req.max_turns,
                    blue=blue,
                    on_event=on_event,
                )
                saved_path = save_run(transcript, verdict, label=f"{persona.name}-{req.blue_mode}")
                q.put(("saved", {"saved_file": saved_path.name}))
            except Exception as exc:
                q.put(("error", {"message": str(exc)}))
            finally:
                q.put(("done", {}))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        yield "event: connected\ndata: {}\n\n"

        while True:
            try:
                kind, payload = q.get(timeout=60.0)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

            if kind == "done":
                yield "event: done\ndata: {}\n\n"
                break
            elif kind == "error":
                data_json = json.dumps(payload)
                yield f"event: error\ndata: {data_json}\n\n"
                break
            elif kind == "status":
                data_json = json.dumps(payload)
                yield f"event: status\ndata: {data_json}\n\n"
            elif kind == "utterance":
                u_dict = payload.model_dump(mode="json")
                data_json = json.dumps({"utterance": u_dict})
                yield f"event: utterance\ndata: {data_json}\n\n"
            elif kind == "verdict":
                t_dict = payload["transcript"].model_dump(mode="json")
                v_dict = payload["verdict"].model_dump(mode="json")
                data_json = json.dumps({"transcript": t_dict, "verdict": v_dict})
                yield f"event: verdict\ndata: {data_json}\n\n"
            elif kind == "saved":
                data_json = json.dumps(payload)
                yield f"event: saved\ndata: {data_json}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/coach")
def post_coach(req: CoachRequest) -> dict[str, Any]:
    try:
        gaps = analyze_coverage_gaps(RUNS_DIR) if req.target_gap else None
        fights = select_instructive_fights(RUNS_DIR, max_fights=req.max_fights, target_gap=req.target_gap, gaps=gaps)
        if not fights:
            raise HTTPException(status_code=400, detail="No fights available to learn from.")
        
        threat_items = None
        if req.target_mechanic:
            from phalanx.recon import ThreatFinding
            threat_items = [
                ThreatFinding(
                    title="Zero-Day CVE Targeted Exploit",
                    url="https://cve.mitre.org",
                    snippet=req.target_mechanic,
                    vector_category="prompt_injection",
                    extracted_mechanic=req.target_mechanic,
                )
            ]

        out = coach(fights, gaps=gaps, threat_intel=threat_items)
        return {
            "persona_name": out.persona_name,
            "scenario_name": out.scenario_name,
            "rationale": out.rationale,
            "persona_path": str(out.persona_path),
            "scenario_path": str(out.scenario_path),
            "raw": out.raw_json,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/fix")
def post_fix(req: FixRequest) -> dict[str, Any]:
    target_file = None
    for p in RUNS_DIR.glob("*.json"):
        if p.name.endswith(".fix.json") or p.name.startswith("_"):
            continue
        if req.fight_id in p.name:
            target_file = p
            break
    if not target_file:
        raise HTTPException(status_code=404, detail=f"Fight {req.fight_id} not found.")

    try:
        fix_p = target_file.with_suffix(".fix.json")
        if fix_p.exists():
            try:
                payload = json.loads(fix_p.read_text())
                if payload.get("summary") and payload.get("prompt_patch"):
                    return payload
            except Exception:
                pass

        payload = json.loads(target_file.read_text())
        proposal = propose_fix(payload)
        out_path = write_fix(proposal, target_file)
        return {
            "fight_id": proposal.fight_id,
            "persona_name": proposal.persona_name,
            "blue_mode": proposal.blue_mode,
            "summary": proposal.summary,
            "root_cause": proposal.root_cause,
            "prompt_patch": proposal.prompt_patch,
            "action_rail": getattr(proposal, "action_rail", {}),
            "regression_tests": proposal.regression_tests,
            "taxonomy": proposal.taxonomy,
            "test_manager": getattr(proposal, "test_manager", {}),
            "fix_file": out_path.name,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class VerifyRequest(BaseModel):
    fight_id: str


@app.post("/api/verify")
def post_verify(req: VerifyRequest) -> dict[str, Any]:
    try:
        res = verify_remediation(req.fight_id)
        return res.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/recon")
def get_recon(query: str = "LLM agent prompt injection zero-day CVE financial") -> dict[str, Any]:
    try:
        tr = ThreatRecon()
        rep = tr.search_threats(query=query)
        return rep.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class JobDispatchRequest(BaseModel):
    workers: int = 4
    max_turns: int = 6
    batch_size: int = 4


@app.post("/api/job/dispatch")
def post_job_dispatch(req: JobDispatchRequest) -> dict[str, Any]:
    try:
        dispatcher = NebiusJobDispatcher()
        summary = dispatcher.execute_job(
            workers=req.workers,
            max_turns=req.max_turns,
            batch_size=req.batch_size,
        )
        return summary.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/job/dispatch/stream")
def post_job_dispatch_stream(req: JobDispatchRequest) -> StreamingResponse:
    """Stream distributed serverless batch grid events in real time."""
    def event_stream():
        q: queue.Queue[tuple[str, Any]] = queue.Queue()

        def on_event(event_type: str, data: Any) -> None:
            q.put((event_type, data))

        def worker() -> None:
            try:
                dispatcher = NebiusJobDispatcher()
                dispatcher.execute_job_stream(
                    workers=req.workers,
                    max_turns=req.max_turns,
                    batch_size=req.batch_size,
                    on_event=on_event,
                )
            except Exception as exc:
                q.put(("error", {"message": str(exc)}))
            finally:
                q.put(("done", {}))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        yield "event: connected\ndata: {}\n\n"

        while True:
            try:
                kind, payload = q.get(timeout=120.0)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

            if kind == "done":
                yield "event: done\ndata: {}\n\n"
                break
            elif kind == "error":
                data_json = json.dumps(payload)
                yield f"event: error\ndata: {data_json}\n\n"
                break
            else:
                data_json = json.dumps(payload)
                yield f"event: {kind}\ndata: {data_json}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
