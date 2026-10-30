"""Nebius Serverless Job Dispatcher & Distributed Red-Teaming Runner.

Packages adversarial fight matrices into Nebius Serverless Job specifications
and orchestrates high-throughput batch fuzzing across distributed endpoints.
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from phalanx.blue_team import make_blue
from phalanx.personas import CANONICAL_PAIRS, load_persona, load_scenario
from phalanx.runner import RUNS_DIR, run_fight, save_run


@dataclass
class JobItemResult:
    persona: str
    scenario: str
    blue_mode: str
    winner: str
    blue_score: int
    red_score: int
    breach: bool
    worker_id: int = 1
    duration: float = 0.0
    fight_id: str = ""
    turns: int = 0
    saved_file: str = ""
    transcript: dict[str, Any] | None = None
    verdict: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "scenario": self.scenario,
            "blue_mode": self.blue_mode,
            "winner": self.winner,
            "blue_score": self.blue_score,
            "red_score": self.red_score,
            "breach": self.breach,
            "worker_id": self.worker_id,
            "duration": round(self.duration, 1),
            "fight_id": self.fight_id,
            "turns": self.turns,
            "saved_file": self.saved_file,
            "transcript": self.transcript,
            "verdict": self.verdict,
        }


@dataclass
class JobSummary:
    job_id: str
    total_fights: int
    blue_defenses: int
    red_breaches: int
    draws: int
    avg_blue_score: float
    duration_seconds: float
    results: list[JobItemResult] = field(default_factory=list)
    worker_stats: dict[int, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "total_fights": self.total_fights,
            "blue_defenses": self.blue_defenses,
            "red_breaches": self.red_breaches,
            "draws": self.draws,
            "avg_blue_score": round(self.avg_blue_score, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "worker_stats": self.worker_stats,
            "results": [r.to_dict() for r in self.results],
        }


class NebiusJobDispatcher:
    def __init__(self, runs_dir: Path = RUNS_DIR) -> None:
        self.runs_dir = runs_dir

    def generate_manifest(
        self,
        pairs: list[tuple[str, str]] | None = None,
        blue_modes: list[str] | None = None,
        workers: int = 8,
    ) -> dict[str, Any]:
        pairs = pairs or CANONICAL_PAIRS
        blue_modes = blue_modes or ["standard", "lenient", "naive"]
        job_id = f"job-nebius-{uuid.uuid4().hex[:8]}"

        manifest = {
            "apiVersion": "serverless.nebius.ai/v1alpha1",
            "kind": "ServerlessJob",
            "metadata": {
                "name": job_id,
                "labels": {
                    "suite": "phalanx-red-team",
                    "framework": "nvidia-nemotron",
                },
            },
            "spec": {
                "taskTemplate": {
                    "container": {
                        "image": "cr.nemotron.nebius.ai/phalanx:latest",
                        "resources": {
                            "gpu": "1x-l40s",
                            "cpu": 4,
                            "memory": "16Gi",
                        },
                        "env": [
                            {"name": "NEBIUS_BASE_URL", "value": "https://api.tokenfactory.nebius.com/v1"},
                            {"name": "DEFAULT_RED_MODEL", "value": "nvidia/Nemotron-3-Ultra-550b-a55b"},
                            {"name": "DEFAULT_BLUE_MODEL", "value": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"},
                            {"name": "DEFAULT_JUDGE_MODEL", "value": "nvidia/nemotron-3-super-120b-a12b"},
                        ],
                    },
                },
                "concurrency": workers,
                "parallelism": len(pairs) * len(blue_modes),
                "matrix": [
                    {"persona": p, "scenario": s, "blue_mode": m}
                    for p, s in pairs
                    for m in blue_modes
                ],
            },
        }
        return manifest

    def execute_job_stream(
        self,
        pairs: list[tuple[str, str]] | None = None,
        blue_modes: list[str] | None = None,
        workers: int = 4,
        max_turns: int = 6,
        batch_size: int = 4,
        on_event: Callable[[str, Any], None] | None = None,
    ) -> JobSummary:
        """Execute the adversarial test matrix concurrently across multiple worker threads with live event streaming."""
        start_time = datetime.utcnow()
        pairs = pairs or CANONICAL_PAIRS
        blue_modes = blue_modes or ["standard", "lenient", "naive"]
        job_id = f"nebius-job-{uuid.uuid4().hex[:8]}"

        matrix = [(p, s, m) for p, s in pairs for m in blue_modes]
        if batch_size and batch_size > 0:
            matrix = matrix[:batch_size]

        total_fights = len(matrix)
        if on_event:
            on_event("job_start", {
                "job_id": job_id,
                "total_fights": total_fights,
                "workers": workers,
            })

        task_queue: queue.Queue[tuple[int, str, str, str]] = queue.Queue()
        for idx, item in enumerate(matrix):
            task_queue.put((idx, item[0], item[1], item[2]))

        results: list[JobItemResult] = []
        worker_runs: dict[int, list[JobItemResult]] = {w: [] for w in range(1, workers + 1)}
        lock = threading.Lock()

        def _worker_loop(worker_id: int) -> None:
            while True:
                try:
                    idx, p_name, s_name, mode = task_queue.get_nowait()
                except queue.Empty:
                    break

                if on_event:
                    on_event("worker_assigned", {
                        "worker_id": worker_id,
                        "fight_index": idx,
                        "total_fights": total_fights,
                        "persona": p_name,
                        "scenario": s_name,
                        "blue_mode": mode,
                    })

                fight_start = datetime.utcnow()
                try:
                    persona = load_persona(p_name)
                    scenario = load_scenario(s_name)
                    blue = make_blue(mode=mode)

                    def _on_fight_event(ev: str, data: Any) -> None:
                        if not on_event:
                            return
                        if ev == "status":
                            on_event("worker_turn", {
                                "worker_id": worker_id,
                                "fight_index": idx,
                                "phase": data.get("phase", ""),
                                "turn": data.get("turn", 1),
                                "message": data.get("message", ""),
                            })
                        elif ev == "utterance":
                            u = data
                            content_str = u.content or ""
                            snippet = (content_str[:90] + "...") if len(content_str) > 90 else content_str
                            on_event("worker_turn", {
                                "worker_id": worker_id,
                                "fight_index": idx,
                                "speaker": u.speaker,
                                "snippet": snippet,
                            })

                    transcript, verdict = run_fight(
                        persona=persona,
                        scenario=scenario,
                        max_turns=max_turns,
                        blue=blue,
                        on_event=_on_fight_event,
                    )
                    saved_path = save_run(transcript, verdict, label=f"job-{job_id[:8]}-w{worker_id}-{mode}")
                    fight_dur = (datetime.utcnow() - fight_start).total_seconds()
                    is_breach = verdict.winner == "red" or any("POLICY BREACH" in b for b in verdict.policy_breaches)
                    t_dump = transcript.model_dump(mode="json")
                    v_dump = verdict.model_dump(mode="json")

                    res = JobItemResult(
                        persona=p_name,
                        scenario=s_name,
                        blue_mode=mode,
                        winner=verdict.winner,
                        blue_score=verdict.blue_score,
                        red_score=verdict.red_score,
                        breach=is_breach,
                        worker_id=worker_id,
                        duration=fight_dur,
                        fight_id=transcript.fight_id,
                        turns=len(transcript.utterances),
                        saved_file=saved_path.name,
                        transcript=t_dump,
                        verdict=v_dump,
                    )

                    with lock:
                        results.append(res)
                        worker_runs[worker_id].append(res)

                    if on_event:
                        on_event("fight_completed", {
                            "worker_id": worker_id,
                            "fight_index": idx,
                            "total_fights": total_fights,
                            "persona": p_name,
                            "scenario": s_name,
                            "blue_mode": mode,
                            "winner": verdict.winner,
                            "blue_score": verdict.blue_score,
                            "red_score": verdict.red_score,
                            "breach": is_breach,
                            "turns": len(transcript.utterances),
                            "duration": round(fight_dur, 1),
                            "fight_id": transcript.fight_id,
                            "saved_file": saved_path.name,
                            "transcript": t_dump,
                            "verdict": v_dump,
                        })
                except Exception as exc:
                    pass
                finally:
                    task_queue.task_done()

        threads: list[threading.Thread] = []
        actual_workers = min(workers, total_fights)
        for w in range(1, actual_workers + 1):
            t = threading.Thread(target=_worker_loop, args=(w,), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        blue_wins = sum(1 for r in results if r.winner == "blue")
        red_breaches = sum(1 for r in results if r.breach)
        draws = sum(1 for r in results if r.winner == "draw")
        avg_score = sum(r.blue_score for r in results) / len(results) if results else 0.0

        worker_stats = {}
        for w in range(1, actual_workers + 1):
            w_res = worker_runs.get(w, [])
            w_def = sum(1 for r in w_res if r.winner == "blue")
            w_br = sum(1 for r in w_res if r.breach)
            w_avg = sum(r.blue_score for r in w_res) / len(w_res) if w_res else 0.0
            worker_stats[w] = {
                "completed": len(w_res),
                "defenses": w_def,
                "breaches": w_br,
                "avg_blue_score": round(w_avg, 1),
            }

        summary = JobSummary(
            job_id=job_id,
            total_fights=len(results),
            blue_defenses=blue_wins,
            red_breaches=red_breaches,
            draws=draws,
            avg_blue_score=avg_score,
            duration_seconds=elapsed,
            results=results,
            worker_stats=worker_stats,
        )

        if on_event:
            on_event("job_complete", summary.to_dict())

        return summary

    def execute_job(
        self,
        pairs: list[tuple[str, str]] | None = None,
        blue_modes: list[str] | None = None,
        workers: int = 4,
        max_turns: int = 6,
        batch_size: int = 4,
    ) -> JobSummary:
        """Execute the adversarial test matrix concurrently across multiple worker threads."""
        return self.execute_job_stream(
            pairs=pairs,
            blue_modes=blue_modes,
            workers=workers,
            max_turns=max_turns,
            batch_size=batch_size,
        )
