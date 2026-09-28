"""Official Hindsight Cloud memory adapter for DealLens."""
import asyncio
import os
from contextlib import suppress
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


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
        if not api_key:
            self.error = "HINDSIGHT_API_KEY is missing. Add it to .env and restart the app."
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
        return self.client is not None and self.error is None

    def recall(self, deal):
        if not self.ready:
            raise RuntimeError(self.error)
        query = (
            f"Find past sales experiences relevant to this deal. Industry: {deal['industry']}. "
            f"Company: {deal['company']}. Meeting notes: {deal['situation']}"
        )
        client = _get_client()
        try:
            response = _run_async(client.arecall(bank_id=self.bank_id, query=query))
            return [self._recall_view(result) for result in getattr(response, "results", [])[:5]]
        finally:
            with suppress(Exception):
                _run_async(client.aclose())

    def retain(self, deal, analysis):
        if not self.ready:
            raise RuntimeError(self.error)
        content = "\n".join((
            "DealLens sales interaction",
            f"Company: {deal['company']}",
            f"Customer: {deal['customer']}",
            f"Industry: {deal['industry']}",
            f"Deal value: {deal['deal_value']}",
            f"Meeting notes: {deal['situation']}",
            f"Detected risks: {', '.join(analysis['risks'])}",
            f"Recommended next action: {analysis['actions'][0]}",
        ))
        document_id = f"deal-{self._slug(deal['company'])}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        client = _get_client()
        try:
            _run_async(client.aretain(
                bank_id=self.bank_id,
                content=content,
                context="DealLens sales meeting notes",
                document_id=document_id,
                metadata={"industry": deal["industry"], "company": deal["company"], "source": "deallens"},
                tags=["sales-deal", "meeting-notes"],
            ))
        finally:
            with suppress(Exception):
                _run_async(client.aclose())
        return {"lesson": analysis["actions"][0], "document_id": document_id}

    def all(self):
        if not self.ready:
            return []
        client = _get_client()
        try:
            response = _run_async(client.alist_memories(bank_id=self.bank_id, limit=100, offset=0))
            items = getattr(response, "items", [])
            return [self._memory_view(item) for item in items]
        except Exception as exc:
            self.error = f"Hindsight connection unavailable: {self._safe_error(exc)}"
            return []
        finally:
            with suppress(Exception):
                _run_async(client.aclose())

    @staticmethod
    def _value(item, name, default=""):
        return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)

    def _recall_view(self, item):
        metadata = self._value(item, "metadata", {}) or {}
        return {
            "text": self._value(item, "text", "Memory retrieved by Hindsight."),
            "type": self._value(item, "type", "memory"),
            "context": self._value(item, "context", "DealLens sales memory"),
            "company": metadata.get("company", "Hindsight memory"),
            "why_recalled": "Retrieved by Hindsight using semantic, keyword, graph, and temporal recall.",
            "lesson": self._value(item, "lesson", ""),
        }

    def _memory_view(self, item):
        return {
            "text": self._value(item, "text", "Stored memory"),
            "type": self._value(item, "type", "memory"),
            "context": self._value(item, "context", "DealLens sales memory"),
        }

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
