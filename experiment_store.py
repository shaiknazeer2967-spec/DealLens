"""Durable local store and evidence-based helpers for Experiment Memory Agent."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

STORE = Path(__file__).resolve().parent / "data" / "experiments.json"
REQUIRED = ("name", "objective", "change", "result", "learning")
RESULTS = {"Successful", "Unsuccessful", "Inconclusive"}

def _read():
    try:
        payload = json.loads(STORE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, json.JSONDecodeError): return []

def _write(items):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(items, indent=2), encoding="utf-8")

def all_experiments(query="", result=""):
    needle = query.strip().lower(); selected = []
    for item in _read():
        blob = " ".join(str(item.get(key, "")) for key in ("name", "objective", "change", "learning")).lower()
        if (not needle or needle in blob) and (not result or item.get("result") == result): selected.append(item)
    return sorted(selected, key=lambda item: item.get("created_at", ""), reverse=True)

def get_experiment(experiment_id): return next((item for item in _read() if item.get("id") == experiment_id), None)

def _words(item):
    text = " ".join(str(item.get(key, "")) for key in ("objective", "change", "learning")).lower()
    return {word for word in re.findall(r"[a-z]{4,}", text) if word not in {"with", "that", "this", "from", "were", "will", "into", "team", "experiment"}}

def related_to(experiment, limit=3):
    current = _words(experiment); matches = []
    for item in _read():
        if item.get("id") == experiment.get("id"): continue
        overlap = current & _words(item)
        if overlap: matches.append((len(overlap), item, sorted(overlap)))
    matches.sort(key=lambda row: (row[0], row[1].get("created_at", "")), reverse=True)
    return [{**item, "relevance": f"Shared focus: {', '.join(words[:4])}."} for _, item, words in matches[:limit]]

def analysis_for(experiment):
    related = related_to(experiment); result = experiment["result"]
    if result == "Successful":
        finding, explanation, next_step = "The recorded change achieved the stated objective strongly enough to be marked successful.", "The tested change aligned with the team’s objective; validate it with a broader segment before treating it as universal.", "Repeat the winning change with a new segment or a larger sample, while measuring the same success signal."
    elif result == "Unsuccessful":
        finding, explanation, next_step = "The recorded change did not achieve the expected result.", "The learning points to a mismatch between the intervention and the user or product need, rather than a reason to discard the original objective.", "Test a narrower alternative that directly addresses the lesson before investing in a wider rollout."
    else:
        finding, explanation, next_step = "The experiment produced an inconclusive result.", "The available record does not support a clear success or failure conclusion yet.", "Run a more focused follow-up with one primary success metric and a clearly defined audience."
    if related: next_step += f" Review the lesson from {related[0]['name']} before finalizing the design."
    return {"finding": finding, "explanation": explanation, "next_step": next_step, "memory_lesson": experiment["learning"], "related": related}

def create(payload, demo=False):
    data = {key: str(payload.get(key, "")).strip() for key in REQUIRED}
    missing = [key.replace("_", " ").title() for key in REQUIRED if not data[key]]
    if missing: raise ValueError("Please complete: " + ", ".join(missing) + ".")
    if data["result"] not in RESULTS: raise ValueError("Result must be Successful, Unsuccessful, or Inconclusive.")
    item = {"id": uuid4().hex, **data, "demo": demo, "created_at": datetime.now(timezone.utc).isoformat()}
    items = _read(); items.append(item); _write(items); return item

def remove(experiment_id):
    items = _read(); kept = [item for item in items if item.get("id") != experiment_id]
    if len(kept) == len(items): return False
    _write(kept); return True

def load_demo():
    if any(item.get("demo") for item in _read()): return 0
    samples = [
        {"name": "Shorter onboarding checklist", "objective": "Help new users reach their first project sooner", "change": "Replaced the seven-step setup with a guided three-step checklist", "result": "Successful", "learning": "A focused first action reduced setup friction; advanced options work better after activation."},
        {"name": "Annual-plan checkout prompt", "objective": "Increase annual subscription adoption", "change": "Added an annual-plan prompt before payment", "result": "Unsuccessful", "learning": "Presenting a long commitment before value is experienced created hesitation for new users."},
        {"name": "Team invite reminder", "objective": "Increase collaboration in the first week", "change": "Sent an in-app reminder to invite a teammate on day three", "result": "Inconclusive", "learning": "The reminder was noticed, but the audience was too small to separate timing from product-fit effects."},
    ]
    for sample in samples: create(sample, demo=True)
    return len(samples)

def insights():
    items = _read(); wins = [item for item in items if item.get("result") == "Successful"]; losses = [item for item in items if item.get("result") == "Unsuccessful"]
    return {"total": len(items), "successful": len(wins), "unsuccessful": len(losses), "learnings": sum(bool(item.get("learning")) for item in items), "wins": wins[:3], "losses": losses[:3], "lessons": [item for item in items if item.get("learning")][:5]}
