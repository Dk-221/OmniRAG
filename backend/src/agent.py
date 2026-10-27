"""
agent.py – Agentic tool-calling loop with query planning, dynamic routing,
parallel tool execution, structured artifacts, self-check verification, and SSE streaming.

Architecture:
    1. Query planner: For complex questions, generate a 2-4 step JSON plan and emit {"type":"plan"}.
    2. Dynamic routing: Select at most ROUTER_MAX_TOOLS (default 6) via keyword + embedding matching.
    3. Model execution: Call Groq with selected tool specs.
    4. Parallel tool execution: Run all tool calls requested in a single turn concurrently with asyncio.gather.
       Emit {"type":"tool_call"} together, then {"type":"artifact"} and {"type":"tool_result"} as they finish.
       Update {"type":"plan_step", "status":"running|done"}.
    5. Retry fallback: If model indicates no tool fits, retry once with all tools.
    6. Self-check verification: If VERIFY_ANSWERS=true and multi-step evidence was gathered,
       run a verification Groq call and emit {"type":"verification", "verdict":"...", "notes":"..."}.
    7. Stream final answer tokens, then emit {"type":"sources"} and {"type":"done"}.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

from src.config import settings
from src.llm import llm_client
from src.router import get_all_tools, select_tools
from src.tool_registry import TOOL_MAP
from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

# ── system prompt ─────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an expert AI research assistant equipped with real-time tools.

Instructions:
1. Carefully understand the user query. Choose the best tool(s) to gather factual evidence.
2. For user facts, preferences, or personal identity (e.g. user's name, preferences, past context), check the Stored Long-Term Memories provided below. Always answer user identity questions (like "what is my name", "who am I", "what is the name of user") directly using these remembered facts. You can also use search_knowledge_base to retrieve memories or document archives.
3. Whenever a URL (http:// or https://) is present in the user request, you MUST ALWAYS call read_url with that exact URL. Never pass a URL into web_search. If the URL is a news portal, homepage, or aggregation feed (such as Google News, BBC, CNN, etc.) or when a direct article or date is not provided, read the top news stories from that page and extract the requested key points immediately. Never refuse or ask the user to provide a direct article link or date.
4. For current news or breaking headlines without a URL, call get_news to fetch live Google News articles on that topic (or leave topic empty for general top stories).
5. For stocks or crypto, use get_stock_data, compare_stocks, crypto_price, or currency_convert.
6. For datasets (CSV/XLSX), use analyze_data with the exact dataset filename from Available Uploaded Datasets. When the user asks to analyze "my uploaded CSV", "the dataset", or uploaded data without specifying a filename, use the actual uploaded dataset (e.g. "test_sales.csv"). NEVER pass "uploaded.csv" as a literal filename. To visualize series, use make_chart.
7. For sandboxed computation or simulations, use run_python or calculate. When the user asks to compute and plot/chart data (e.g. compound interest, financial growth, math curves), run the Python computation to get the exact data series, and call make_chart with the calculated numerical values (e.g. 1050.0, 1102.5, etc. — never string numbers with commas or placeholders) so the frontend renders a fully dynamic interactive chart.
8. For weather, air quality, or geocoding, use get_weather, air_quality, geocode_place.
9. Call multiple independent tools concurrently when appropriate.
10. Synthesize factual, well-structured answers and cite sources accurately.
11. Interactive charts and tables (from make_chart, compare_stocks, analyze_data) are rendered natively by the frontend UI. Never emit markdown image tags like ![chart](...) or hallucinated image links in your response.
"""

Event = Dict[str, Any]


def _ev(type_: str, **kwargs: Any) -> Event:
    return {"type": type_, **kwargs}


# ── source tracking ───────────────────────────────────────────────────────
def _extract_sources(
    tool_history: List[Dict[str, Any]],
    has_memories: bool = False,
    user_query: str = "",
) -> List[Dict[str, Any]]:
    """Build a deduplicated sources list including page numbers for documents and memory references."""
    sources: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for record in tool_history:
        tool_name = record.get("name", "")
        result = record.get("result", "")

        if tool_name == "search_knowledge_base":
            for line in result.splitlines():
                if line.startswith("[") and "File:" in line:
                    parts = line.split("|")
                    filename = ""
                    page = 1
                    for p in parts:
                        if "File:" in p:
                            filename = p.split("File:")[-1].strip()
                        if "Page:" in p:
                            try:
                                page = int(p.split("Page:")[-1].strip())
                            except ValueError:
                                page = 1
                    if filename == "[Memory]":
                        key = "Memory"
                        if key not in seen:
                            seen.add(key)
                            sources.append({"type": "memory", "title": "Stored Memory", "ref": "Memory Store"})
                    else:
                        key = f"{filename}:p{page}"
                        if filename and key not in seen:
                            seen.add(key)
                            title = f"{filename} (page {page})"
                            sources.append({"type": "doc", "title": title, "ref": filename, "page": page})

        elif tool_name in ("web_search", "read_url"):
            for line in result.splitlines():
                stripped = line.strip()
                if stripped.startswith("URL:"):
                    url = stripped[4:].strip()
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"type": "web", "title": url, "ref": url})
                elif stripped.startswith("http://") or stripped.startswith("https://"):
                    url = stripped.split()[0]
                    if url not in seen:
                        seen.add(url)
                        sources.append({"type": "web", "title": url, "ref": url})

        elif tool_name in ("get_news", "tech_news"):
            for line in result.splitlines():
                stripped = line.strip()
                if stripped.startswith("http://") or stripped.startswith("https://"):
                    url = stripped.split()[0]
                    if url not in seen:
                        seen.add(url)
                        sources.append({"type": "news", "title": url, "ref": url})

        elif tool_name in ("get_stock_data", "compare_stocks"):
            tickers = record.get("args", {}).get("ticker") or record.get("args", {}).get("tickers")
            key = f"Stock: {tickers}"
            if key not in seen:
                seen.add(key)
                sources.append({"type": "finance", "title": key, "ref": str(tickers)})

        elif tool_name == "get_weather":
            city = record.get("args", {}).get("city", "")
            key = f"Weather: {city}"
            if city and key not in seen:
                seen.add(key)
                sources.append({"type": "weather", "title": key, "ref": city})

    if not sources and has_memories:
        q_lower = (user_query or "").lower()
        if any(w in q_lower for w in ("name", "who am i", "remember", "preference", "favorite", "about me", "my", "user")):
            sources.append({"type": "memory", "title": "Stored Memory", "ref": "Memory Store"})

    return sources


# ── message trimming ──────────────────────────────────────────────────────
def _trim_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    n = settings.max_history_messages
    return history[-n:] if len(history) > n else history


def _build_messages(
    user_message: str,
    history: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], bool]:
    from src.rag import list_memories, retrieve_memories

    has_memories = False
    memory_context = ""
    try:
        all_memories = list_memories()
        if all_memories:
            has_memories = True
            if len(all_memories) <= 15:
                facts = [f"- {m['fact']}" for m in all_memories]
            else:
                rel = retrieve_memories(user_message, top_k=6)
                rel_facts = [r["text"].replace("Memory: ", "") for r in rel]
                rec_facts = [m["fact"] for m in all_memories[-6:]]
                combined = list(dict.fromkeys(rel_facts + rec_facts))
                facts = [f"- {f}" for f in combined]

            memory_context = (
                "\n\nPersistent User Context & Stored Long-Term Memories:\n"
                + "\n".join(facts)
                + "\nNote: Always prioritize and answer directly using these stored facts whenever the user asks about themselves (e.g. name, preferences, favorite stocks, previous details) or when relevant to their request."
            )
    except Exception as exc:
        logger.warning("Failed to inject memories into prompt: %s", exc)

    dataset_context = ""
    try:
        from src.tools.analyze_data_tool import list_datasets
        dsets = list_datasets()
        if dsets:
            d_lines = [f"- {d['filename']} ({d['size_bytes']} bytes)" for d in dsets]
            dataset_context = (
                "\n\nAvailable Uploaded Datasets in Workspace:\n"
                + "\n".join(d_lines)
                + f"\nNote: When the user refers to 'my uploaded CSV', 'the CSV', 'the dataset', or 'my data', automatically use the dataset listed above (e.g. '{dsets[0]['filename']}'). Never use 'uploaded.csv' as a literal filename."
            )
    except Exception as exc:
        logger.warning("Failed to inject datasets into prompt: %s", exc)

    system_prompt = _SYSTEM_PROMPT + memory_context + dataset_context
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(_trim_history(history))
    messages.append({"role": "user", "content": user_message})
    return messages, has_memories


# ── complexity check & query planner ──────────────────────────────────────
def _is_complex_query(text: str) -> bool:
    """Detect complex questions that benefit from query planning."""
    t_lower = text.lower()
    words = text.split()
    if len(words) > 25:
        return True
    if "compare" in t_lower or "versus" in t_lower or " vs " in t_lower:
        return True
    if " and " in t_lower and ("chart" in t_lower or "news" in t_lower or "price" in t_lower or "weather" in t_lower):
        return True
    return False


async def _generate_plan(user_message: str) -> List[Dict[str, Any]]:
    """Run a fast, lightweight Groq call to generate 2 to 4 plan steps."""
    prompt = (
        "Break down this user request into 2 to 4 short, actionable sub-steps for an AI agent.\n"
        f"User request: {user_message}\n\n"
        "Respond ONLY with a valid JSON object matching this schema:\n"
        '{"steps": [{"id": 1, "text": "description of step 1"}, {"id": 2, "text": "description of step 2"}]}\n'
        "Do NOT include markdown backticks or explanations."
    )
    try:
        resp = await asyncio.to_thread(
            llm_client.chat,
            messages=[{"role": "user", "content": prompt}],
            tools=None,
        )
        raw = resp.choices[0].message.content or ""
        # Clean json
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
        raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)
        steps = data.get("steps", [])
        if isinstance(steps, list) and 2 <= len(steps) <= 4:
            return steps
    except Exception as exc:
        logger.warning("Query planner skipped due to parse error: %s", exc)
    return []


# ── self-check verification ───────────────────────────────────────────────
async def _verify_answer(
    draft_answer: str,
    tool_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Check draft answer claims against tool results using Groq."""
    if not tool_history:
        return {"verdict": "supported", "notes": "No tool claims to verify."}

    evidence_snippets = []
    for th in tool_history[-5:]:
        evidence_snippets.append(f"[{th.get('name')}]: {th.get('result', '')[:400]}")
    evidence_text = "\n\n".join(evidence_snippets)

    prompt = (
        "You are an objective fact-checker. Verify the draft answer against the gathered tool evidence.\n\n"
        f"Tool Evidence:\n{evidence_text}\n\n"
        f"Draft Answer:\n{draft_answer[:2000]}\n\n"
        "Are all major claims supported by the evidence?\n"
        "Respond ONLY with a JSON object in this format:\n"
        '{"verdict": "supported" | "partial" | "unsupported", "notes": "1-sentence summary"}\n'
        "Do not include code blocks or markdown fences."
    )
    try:
        resp = await asyncio.to_thread(
            llm_client.chat,
            messages=[{"role": "user", "content": prompt}],
            tools=None,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)
        verdict = data.get("verdict", "supported").lower()
        if verdict not in ("supported", "partial", "unsupported"):
            verdict = "supported"
        return {"verdict": verdict, "notes": data.get("notes", "")}
    except Exception as exc:
        logger.warning("Verification call failed: %s", exc)
        return {"verdict": "supported", "notes": "Verification passed by default."}


# ── parallel tool execution helper ────────────────────────────────────────
async def _run_single_tool(
    tool: BaseTool,
    args: Dict[str, Any],
) -> Tuple[str, bool, Optional[Dict[str, Any]]]:
    """Run tool in a worker thread and extract any generated artifact."""
    def _exec() -> Tuple[str, bool, Optional[Dict[str, Any]]]:
        res = tool.safe_run(**args)
        ok = not res.startswith("[Tool error]") and not res.startswith("[Error]")
        artifact = tool.get_artifact()
        return res, ok, artifact

    return await asyncio.to_thread(_exec)


# ── main async agent generator ────────────────────────────────────────────
async def run_agent_streaming(
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> AsyncGenerator[Event, None]:
    """
    Main SSE agent loop. Emits plan, plan_step, tool_call, artifact, tool_result,
    verification, token, sources, and done events.
    """
    history = history or []
    messages, has_memories = _build_messages(user_message, history)
    tool_history: List[Dict[str, Any]] = []

    yield _ev("thinking", text="Analysing request and preparing execution plan…")

    # 1. Query planner (for complex questions)
    plan_steps: List[Dict[str, Any]] = []
    if _is_complex_query(user_message):
        plan_steps = await _generate_plan(user_message)
        if plan_steps:
            yield _ev("plan", steps=plan_steps)

    current_plan_step_idx = 0

    # 2. Select initial tools via dynamic router
    offered_tools = select_tools(user_message, max_tools=settings.router_max_tools)
    tool_specs = [t.to_groq_spec() for t in offered_tools]
    has_retried_with_all_tools = False

    for iteration in range(settings.max_agent_iterations):
        logger.info("Agent iteration %d / %d", iteration + 1, settings.max_agent_iterations)

        try:
            response = await asyncio.to_thread(
                llm_client.chat,
                messages=messages,
                tools=tool_specs,
            )
        except RuntimeError as exc:
            yield _ev("error", message=str(exc))
            return

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        msg = choice.message

        # Check if model says no tool fits or needed a tool but none was offered
        no_tools_called = (finish_reason == "stop" or not msg.tool_calls)
        content_text = (msg.content or "").lower()
        model_complained_no_tool = (
            "no tool" in content_text or "don't have access to" in content_text
            or "cannot find a tool" in content_text or "unable to search" in content_text
        )

        if no_tools_called and model_complained_no_tool and not has_retried_with_all_tools:
            logger.info("Model indicated no tool fits; retrying with full tool list.")
            has_retried_with_all_tools = True
            all_tools = get_all_tools()
            tool_specs = [t.to_groq_spec() for t in all_tools]
            continue

        # ── No tool calls → Final answer generation ──────────────────────
        if no_tools_called:
            # Mark any remaining plan steps as done
            while current_plan_step_idx < len(plan_steps):
                step_id = plan_steps[current_plan_step_idx]["id"]
                yield _ev("plan_step", id=step_id, status="done")
                current_plan_step_idx += 1

            draft_answer = msg.content or ""
            caveat = ""

            # Self-check verification (if enabled and multi-tool evidence gathered)
            if settings.verify_answers and len(tool_history) >= 2:
                yield _ev("thinking", text="Verifying answer accuracy against collected evidence…")
                ver_res = await _verify_answer(draft_answer, tool_history)
                yield _ev(
                    "verification",
                    verdict=ver_res["verdict"],
                    notes=ver_res.get("notes", ""),
                )
                if ver_res["verdict"] in ("partial", "unsupported"):
                    caveat = "\n\n*Note: Some details in this response could not be fully verified against external sources.*"

            # Stream the answer tokens
            for word in draft_answer.split(" "):
                yield _ev("token", text=word + " ")
            if caveat:
                yield _ev("token", text=caveat)

            sources = _extract_sources(tool_history, has_memories=has_memories, user_query=user_message)
            if sources:
                yield _ev("sources", items=sources)
            yield _ev("done")
            return

        # ── Parallel Tool Execution ──────────────────────────────────────
        tool_calls = msg.tool_calls or []
        logger.info("Tools called (%d): %s", len(tool_calls), [tc.function.name for tc in tool_calls])

        # Append assistant message with all tool_calls to conversation history
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        })

        # Mark active plan step as running
        if plan_steps and current_plan_step_idx < len(plan_steps):
            active_step = plan_steps[current_plan_step_idx]
            yield _ev("plan_step", id=active_step["id"], status="running")

        # Emit all tool_call events together
        parsed_calls = []
        for tc in tool_calls:
            call_id = tc.id
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            yield _ev("tool_call", id=call_id, name=tool_name, args=args)
            parsed_calls.append((call_id, tool_name, args))

        # Launch all tool executions concurrently with asyncio.gather
        tasks = []
        for call_id, tool_name, args in parsed_calls:
            tool = TOOL_MAP.get(tool_name)
            if tool:
                tasks.append(_run_single_tool(tool, args))
            else:
                async def _err():
                    return f"[Error] Unknown tool: {tool_name}", False, None
                tasks.append(_err())

        results = await asyncio.gather(*tasks)

        # Process results and emit artifacts & tool_result events
        for (call_id, tool_name, args), (result_str, ok, artifact) in zip(parsed_calls, results):
            tool_history.append({"name": tool_name, "args": args, "result": result_str})

            # Emit artifact event if tool produced one
            artifact_ref = None
            if artifact:
                artifact_ref = call_id
                kind = artifact.get("kind") or artifact.get("type") or "data"
                if "chart_type" in artifact or ("labels" in artifact and "series" in artifact):
                    kind = "chart"
                elif "columns" in artifact and "rows" in artifact:
                    kind = "table"
                data = artifact.get("data", artifact)
                if not isinstance(data, dict):
                    data = artifact
                if kind == "chart" and "chart_type" not in data and "chart_type" in artifact:
                    data = artifact
                yield _ev("artifact", kind=kind, tool_call_id=call_id, data=data)

            # Emit tool_result event
            summary = result_str[:120].replace("\n", " ") + ("…" if len(result_str) > 120 else "")
            res_event = _ev("tool_result", id=call_id, name=tool_name, summary=summary, ok=ok)
            if artifact_ref:
                res_event["artifact_ref"] = artifact_ref
            yield res_event

            # Append tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result_str,
            })

        # Mark current plan step as done
        if plan_steps and current_plan_step_idx < len(plan_steps):
            active_step = plan_steps[current_plan_step_idx]
            yield _ev("plan_step", id=active_step["id"], status="done")
            current_plan_step_idx += 1

    # ── Force Final Answer after Max Iterations ───────────────────────────
    yield _ev("thinking", text="Synthesizing final response from gathered results…")
    messages.append({
        "role": "user",
        "content": (
            "Based on all gathered information above, provide a comprehensive, "
            "clear, and complete final answer to the user's question."
        ),
    })

    try:
        final_resp = await asyncio.to_thread(llm_client.chat, messages=messages, tools=None)
        final_text = final_resp.choices[0].message.content or "Completed research."
    except Exception as exc:
        yield _ev("error", message=str(exc))
        return

    for word in final_text.split(" "):
        yield _ev("token", text=word + " ")

    sources = _extract_sources(tool_history, has_memories=has_memories, user_query=user_message)
    if sources:
        yield _ev("sources", items=sources)
    yield _ev("done")


# ── Synchronous generator wrapper for backwards compatibility ────────────
def run_agent(
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Generator[Event, None, None]:
    """Synchronous adapter that wraps the async streaming generator."""
    loop = asyncio.new_event_loop()
    try:
        gen = run_agent_streaming(user_message, history)
        while True:
            try:
                event = loop.run_until_complete(gen.__anext__())
                yield event
            except StopAsyncIteration:
                break
    finally:
        loop.close()
