"""
End-to-End Chat verification test.
Tests /api/chat with "Compare AAPL and RELIANCE.NS over 6 months and chart it".
Verifies streaming of plan, tool_call, tool_result, artifact(chart), token, and done events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import List
import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app
from src.agent import run_agent_streaming

logging.basicConfig(level=logging.INFO)


async def main():
    question = "Compare AAPL and RELIANCE.NS over 6 months and chart it"
    print(f"\n--- Testing E2E: '{question}' ---")

    seen_events: List[dict] = []
    event_types = set()

    async for event in run_agent_streaming(question):
        t = event.get("type")
        event_types.add(t)
        seen_events.append(event)

        if t == "plan":
            print(f"📋 Plan emitted: {event.get('steps')}")
        elif t == "plan_step":
            print(f"   Plan Step {event.get('id')}: {event.get('status')}")
        elif t == "tool_call":
            print(f"🔧 Tool Call: {event.get('name')}({event.get('args')})")
        elif t == "artifact":
            print(f"📦 Artifact [{event.get('kind')}]: {json.dumps(event.get('data'))[:120]}…")
        elif t == "tool_result":
            print(f"✅ Tool Result: {event.get('name')} -> {event.get('summary')[:80]}")
        elif t == "verification":
            print(f"🛡️ Verification: {event.get('verdict')} - {event.get('notes')}")
        elif t == "token":
            print(event.get("text"), end="", flush=True)
        elif t == "sources":
            print(f"\n📚 Sources: {event.get('items')}")
        elif t == "done":
            print("\n🏁 Done event received.")
        elif t == "error":
            print(f"\n❌ Error event: {event.get('message')}")

    print("\n--- Summary of Event Types Received ---")
    print(sorted(list(event_types)))

    # Assertions
    assert "plan" in event_types, "Expected 'plan' event"
    assert "tool_call" in event_types, "Expected 'tool_call' event"
    assert "tool_result" in event_types, "Expected 'tool_result' event"
    assert "artifact" in event_types, "Expected 'artifact' event"
    assert "token" in event_types, "Expected 'token' event"
    assert "done" in event_types, "Expected 'done' event"

    chart_artifacts = [e for e in seen_events if e.get("type") == "artifact" and e.get("kind") == "chart"]
    assert len(chart_artifacts) > 0, "Expected at least one chart artifact"
    chart_data = chart_artifacts[0].get("data", {})
    assert "series" in chart_data and len(chart_data["series"]) >= 2, "Chart series should have data for both stocks"

    print("\n🎉 ALL E2E VERIFICATION ASSERTIONS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
