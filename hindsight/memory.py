"""
DealLens hindsight memory: RETAIN past deals, RECALL similar ones.

Cloud: official Hindsight bank (when HINDSIGHT_API_KEY is configured).
Local: structured store in data/memory_store.json so recall, patterns, and
the dashboard still work for a demo if the API is unavailable.
"""
import asyncio
import json
import os
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from agent.analysis import active_signal_names, detect_signals

load_dotenv()

LOCAL_STORE = Path(__file__).resolve().parent.parent / "data" / "memory_store.json"


def _run_async(coro):
    """Run an async coroutine synchronously, compatible with aiohttp 3.14+."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _get_client():
    """Create a fresh Hindsight client for each operation."""
    from hindsight_client import Hindsight
    return Hindsight(
        base_url=os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
        api_key=os.getenv("HINDSIGHT_API_KEY"),
    )


class HindsightMemory:
    def __init__(self):
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "deallens-demo")
        self.base_url = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
        api_key = os.getenv("HINDSIGHT_API_KEY")
        self.error = None
        self.client = None
        # Last analyze-brief, used by the Hindsight Memory dashboard.
        self.last_brief = None
        self._local_path = LOCAL_STORE
        if not api_key:
            self.error = "HINDSIGHT_API_KEY is missing. Local memory is still active; add a key to `.env` for cloud recall."
            return
        try:
            self.client = _get_client()
            try:
                _run_async(self.client.acreate_bank(bank_id=self.bank_id, name="DealLens deal intelligence"))
            except Exception as exc:
                if "exist" not in str(exc).lower() and "409" not in str(exc):
                    raise
        except Exception as exc:
            self.client = None
            self.error = f"Hindsight connection unavailable: {self._safe_error(exc)}"

    @property
    def ready(self):
        """Cloud Hindsight is connected. Local structured memory is always available."""
        return self.client is not None and self.error is None

    def recall(self, deal):
        """
        RECALL: find past deals that share objections, competitors, industry,
        or implementation concerns with the current deal.

        Merges scored local memories with Hindsight cloud results (when ready).
        Each item includes why_similar so the UI can explain the match.
        """
        local_matches = self._recall_local(deal)
        cloud_matches = []
        if self.ready:
            query = (
                f"Find past sales experiences relevant to this deal. Industry: {deal.get('industry')}. "
                f"Company: {deal.get('company')}. Objections: {deal.get('objections')}. "
                f"Competitor: {deal.get('competitor')}. Requirements: {deal.get('requirements')}. "
                f"Meeting notes: {deal.get('situation')}"
            )
            client = _get_client()
            try:
                response = _run_async(client.arecall(bank_id=self.bank_id, query=query))
                cloud_matches = [self._recall_view(result, deal) for result in getattr(response, "results", [])[:5]]
            except Exception as exc:
                self.error = f"Hindsight recall warning: {self._safe_error(exc)}"
            finally:
                with suppress(Exception):
                    _run_async(client.aclose())
        return self._merge_recalls(local_matches, cloud_matches)

    def retain(self, deal, analysis):
        """
        RETAIN: store structured facts from this deal so later analyses can recall them.

        Writes the local JSON store always, and the Hindsight bank when connected.
        """
        record = self._deal_record(deal, analysis)
        self._append_local(record)

        document_id = record["document_id"]
        if self.ready:
            content = self._retain_content(record)
            client = _get_client()
            try:
                _run_async(client.aretain(
                    bank_id=self.bank_id,
                    content=content,
                    context="DealLens sales meeting notes",
                    document_id=document_id,
                    metadata={
                        "industry": record.get("industry") or "",
                        "company": record.get("company") or "",
                        "outcome": record.get("outcome") or "",
                        "source": "deallens",
                    },
                    tags=["sales-deal", "meeting-notes"],
                ))
            except Exception as exc:
                self.error = f"Hindsight retain warning: {self._safe_error(exc)}"
            finally:
                with suppress(Exception):
                    _run_async(client.aclose())
        return {"lesson": record.get("lesson") or "", "document_id": document_id, "record": record}

    def all(self):
        """Past deals for the Hindsight Memory dashboard (local structured store)."""
        items = self._load_local()
        if self.ready and not items:
            client = _get_client()
            try:
                response = _run_async(client.alist_memories(bank_id=self.bank_id, limit=100, offset=0))
                raw = getattr(response, "items", [])
                return [self._memory_view(item) for item in raw]
            except Exception as exc:
                self.error = f"Hindsight connection unavailable: {self._safe_error(exc)}"
                return []
            finally:
                with suppress(Exception):
                    _run_async(client.aclose())
        return items

    def dashboard_context(self):
        """Aggregate RETAIN/RECALL/REFLECT views for the Hindsight Memory page."""
        past = self.all()
        brief = self.last_brief or {}
        # Store-wide win/loss lessons always explain the memory bank.
        # Last analysis fills similar deals + current insight so the "why" is visible.
        return {
            "past_deals": past,
            "similar_deals": brief.get("similar_deals") or [],
            "patterns": brief.get("patterns") or self._patterns_from_store(past),
            "successful_strategies": [
                {"strategy": item.get("lesson"), "company": item.get("company"), "outcome": item.get("outcome"), "why": "Recorded against a won or recovered deal."}
                for item in past if self._is_win(item.get("outcome")) and item.get("lesson")
            ],
            "failed_strategies": [
                {"strategy": item.get("lesson"), "company": item.get("company"), "outcome": item.get("outcome"), "why": "Recorded against a lost deal."}
                for item in past if self._is_loss(item.get("outcome")) and item.get("lesson")
            ],
            "lessons": [
                {"title": f"Lesson from {item.get('company')}", "detail": item.get("lesson"), "source": item.get("company")}
                for item in past if item.get("lesson")
            ],
            "current_insights": brief,
        }

    def _recall_local(self, deal):
        """Score local history against the current deal and explain each match."""
        current_signals = detect_signals(deal)
        current_tags = set(active_signal_names(current_signals))
        current_industry = (deal.get("industry") or "").strip().lower()
        current_company = (deal.get("company") or "").strip().lower()
        current_competitor = (deal.get("competitor") or "").strip().lower()
        scored = []
        for item in self._load_local():
            if (item.get("company") or "").strip().lower() == current_company:
                continue
            past_signals = detect_signals(item)
            past_tags = set(active_signal_names(past_signals))
            shared = current_tags & past_tags
            score = len(shared) * 4
            reasons = []
            if shared:
                reasons.append(self._shared_reason(shared))
            if current_industry and current_industry == (item.get("industry") or "").strip().lower():
                score += 3
                reasons.append(f"Same industry ({item.get('industry')})")
            past_competitor = (item.get("competitor") or "").strip().lower()
            if current_competitor and past_competitor and (current_competitor in past_competitor or past_competitor in current_competitor):
                score += 3
                reasons.append("A named competitor was also in play")
            elif current_signals.get("competition") and (past_signals.get("competition") or past_competitor):
                score += 2
                reasons.append("A competitor influenced the previous decision")
            if score <= 0:
                continue
            view = dict(item)
            view["similarity"] = min(99, 55 + score * 6)
            view["why_similar"] = "; ".join(reasons) if reasons else "Overlapping deal context."
            view["source"] = "local-memory"
            view["what_happened"] = self._what_happened(item)
            scored.append(view)
        scored.sort(key=lambda row: row.get("similarity") or 0, reverse=True)
        return scored[:5]

    def _merge_recalls(self, local_matches, cloud_matches):
        merged = []
        seen = set()
        for item in local_matches + cloud_matches:
            key = (item.get("company") or "").strip().lower() or (item.get("text") or "")[:80]
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        merged.sort(key=lambda row: row.get("similarity") or 0, reverse=True)
        return merged[:6]

    def _deal_record(self, deal, analysis):
        stamp = datetime.now(timezone.utc)
        document_id = f"deal-{self._slug(deal.get('company') or 'unknown')}-{stamp.strftime('%Y%m%d%H%M%S')}"
        lesson = ""
        if analysis:
            decision = analysis.get("decision") or {}
            lesson = decision.get("suggested_action") or (analysis.get("actions") or [""])[0]
        outcome = (deal.get("outcome") or "").strip() or "Open"
        return {
            "company": deal.get("company") or "",
            "customer": deal.get("customer") or deal.get("company") or "",
            "industry": deal.get("industry") or "",
            "deal_value": deal.get("deal_value") or "",
            "situation": deal.get("situation") or "",
            "objections": deal.get("objections") or "",
            "competitor": deal.get("competitor") or "",
            "requirements": deal.get("requirements") or "",
            "negotiation": deal.get("negotiation") or "",
            "outcome": outcome,
            "lesson": lesson,
            "created_at": stamp.isoformat(),
            "document_id": document_id,
        }

    def _retain_content(self, record):
        return "\n".join((
            "DealLens sales interaction",
            f"Company: {record.get('company')}",
            f"Customer: {record.get('customer')}",
            f"Industry: {record.get('industry')}",
            f"Deal value: {record.get('deal_value')}",
            f"Objections: {record.get('objections')}",
            f"Competitor: {record.get('competitor')}",
            f"Requirements: {record.get('requirements')}",
            f"Negotiation: {record.get('negotiation')}",
            f"Outcome: {record.get('outcome')}",
            f"Meeting notes: {record.get('situation')}",
            f"Lesson: {record.get('lesson')}",
        ))

    def _load_local(self):
        if not self._local_path.exists():
            return []
        try:
            data = json.loads(self._local_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return data

    def _append_local(self, record):
        items = self._load_local()
        items.append(record)
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        self._local_path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _recall_view(self, item, current_deal=None):
        metadata = self._value(item, "metadata", {}) or {}
        text = self._value(item, "text", "Memory retrieved by Hindsight.")
        parsed = self._parse_memory_text(text)
        company = parsed.get("company") or metadata.get("company") or "Hindsight memory"
        merged = {
            "text": text,
            "type": self._value(item, "type", "memory"),
            "context": self._value(item, "context", "DealLens sales memory"),
            "company": company,
            "customer": parsed.get("customer") or company,
            "industry": parsed.get("industry") or metadata.get("industry") or "",
            "deal_value": parsed.get("deal_value") or "",
            "situation": parsed.get("situation") or text,
            "objections": parsed.get("objections") or "",
            "competitor": parsed.get("competitor") or "",
            "requirements": parsed.get("requirements") or "",
            "negotiation": parsed.get("negotiation") or "",
            "outcome": parsed.get("outcome") or metadata.get("outcome") or "",
            "lesson": parsed.get("lesson") or self._value(item, "lesson", ""),
            "source": "hindsight-cloud",
            "similarity": 70,
        }
        if current_deal:
            shared = set(active_signal_names(detect_signals(current_deal))) & set(active_signal_names(detect_signals(merged)))
            merged["why_similar"] = self._shared_reason(shared) if shared else "Retrieved by Hindsight using semantic, keyword, graph, and temporal recall."
            merged["what_happened"] = self._what_happened(merged)
        else:
            merged["why_similar"] = "Retrieved by Hindsight using semantic, keyword, graph, and temporal recall."
        return merged

    def _memory_view(self, item):
        text = self._value(item, "text", "Stored memory")
        parsed = self._parse_memory_text(text)
        return {
            "text": text,
            "type": self._value(item, "type", "memory"),
            "context": self._value(item, "context", "DealLens sales memory"),
            "company": parsed.get("company") or "Hindsight memory",
            "customer": parsed.get("customer") or "",
            "industry": parsed.get("industry") or "",
            "deal_value": parsed.get("deal_value") or "",
            "situation": parsed.get("situation") or text,
            "objections": parsed.get("objections") or "",
            "competitor": parsed.get("competitor") or "",
            "requirements": parsed.get("requirements") or "",
            "outcome": parsed.get("outcome") or "",
            "lesson": parsed.get("lesson") or "",
            "created_at": "",
        }

    def _parse_memory_text(self, text):
        fields = {}
        labels = {
            "company": "company",
            "customer": "customer",
            "industry": "industry",
            "deal value": "deal_value",
            "objections": "objections",
            "competitor": "competitor",
            "requirements": "requirements",
            "negotiation": "negotiation",
            "outcome": "outcome",
            "meeting notes": "situation",
            "lesson": "lesson",
        }
        for raw_line in (text or "").splitlines():
            if ":" not in raw_line:
                continue
            label, value = raw_line.split(":", 1)
            key = labels.get(label.strip().lower())
            if key:
                fields[key] = value.strip()
        return fields

    def _shared_reason(self, shared):
        labels = {
            "pricing": "Price was a main objection",
            "competition": "A competitor was involved",
            "implementation": "Implementation time affected the decision",
            "security": "Security or compliance was a blocker",
            "decision": "The decision path / economic buyer was unclear",
        }
        return "; ".join(labels[name] for name in shared if name in labels)

    def _what_happened(self, item):
        outcome = item.get("outcome") or "Unknown outcome"
        lesson = item.get("lesson") or ""
        situation = item.get("situation") or item.get("text") or ""
        bits = [f"Outcome: {outcome}."]
        if situation:
            bits.append(situation.strip())
        if lesson:
            bits.append(f"Lesson kept: {lesson}")
        return " ".join(bits)

    def _patterns_from_store(self, past):
        price = [item for item in past if detect_signals(item).get("pricing")]
        if len(price) < 2:
            return []
        return [{
            "name": "Price objection pattern",
            "count": len(price),
            "statement": "Price objections appear across multiple retained deals; wins more often cite ROI and implementation value than discounting.",
            "evidence": [item.get("company") for item in price[:5]],
        }]

    @staticmethod
    def _is_win(outcome):
        value = (outcome or "").lower()
        return any(token in value for token in ("won", "win", "recovered"))

    @staticmethod
    def _is_loss(outcome):
        value = (outcome or "").lower()
        return any(token in value for token in ("lost", "loss"))

    @staticmethod
    def _value(item, name, default=""):
        return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)

    @staticmethod
    def _slug(value):
        return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-") or "unknown"

    def close(self):
        """Close the underlying aiohttp session to avoid resource warnings."""
        if self.client:
            with suppress(Exception):
                _run_async(self.client.aclose())

    @staticmethod
    def _safe_error(error):
        message = str(error).replace("\n", " ")
        return message[:180]
