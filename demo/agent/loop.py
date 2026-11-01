"""LLM tool-calling execution loop with retry backoff and safety caps."""
import asyncio
import json
import logging
import time
from typing import Any, Optional
import httpx

from .config import AgentSettings
from .prompts import get_system_prompt
from .tools import TOOL_DEFINITIONS, AgentToolExecutor
from .transcript import RunTranscript

logger = logging.getLogger(__name__)


async def call_llm_with_retry(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    Call OpenAI-compatible chat completion endpoint with exponential backoff on 429 and 5xx.
    Honors Retry-After header when present.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            res = await client.post(url, json=payload, headers=headers, timeout=30.0)
            
            if res.status_code == 200:
                return res.json()
            
            # Rate limit or server error -> backoff retry
            if res.status_code == 429 or res.status_code >= 500:
                retry_after_hdr = res.headers.get("Retry-After")
                if retry_after_hdr and retry_after_hdr.isdigit():
                    wait_time = float(retry_after_hdr)
                else:
                    wait_time = (2 ** attempt) * 1.5

                logger.warning(
                    "LLM call returned status %s on attempt %d/%d; waiting %.1fs before retry",
                    res.status_code,
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                continue

            # Other 4xx client errors
            res.raise_for_status()

        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code == 429 or exc.response.status_code >= 500:
                await asyncio.sleep((2 ** attempt) * 1.5)
                continue
            raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as exc:
            last_error = exc
            logger.warning("LLM connection error on attempt %d/%d: %s", attempt + 1, max_retries, exc)
            await asyncio.sleep((2 ** attempt) * 1.5)
            continue

    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to reach LLM after {max_retries} retries")


async def run_agent_loop(
    task: str,
    settings: AgentSettings,
    variant: str = "clean",
    mode: str = "naive",
    tool_executor: Optional[AgentToolExecutor] = None,
    transcript: Optional[RunTranscript] = None,
    max_steps: Optional[int] = None,
    max_llm_calls: Optional[int] = None,
) -> RunTranscript:
    """
    Execute the agent procurement loop for a given task.
    Returns the completed and sanitized RunTranscript.
    """
    effective_max_steps = max_steps or settings.MAX_STEPS
    effective_max_llm_calls = max_llm_calls or settings.MAX_LLM_CALLS
    
    if transcript is None:
        secrets = [settings.AGENT_LLM_API_KEY, settings.get_effective_agent_key()]
        transcript = RunTranscript(
            task=task,
            variant=variant,
            mode=mode,
            model=settings.AGENT_MODEL,
            secrets_to_mask=secrets,
        )

    if tool_executor is None:
        tool_executor = AgentToolExecutor(
            settings=settings,
            variant=variant,
        )

    # Initialize messages
    system_prompt = get_system_prompt(mode)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {task}"},
    ]
    transcript.add_message("system", system_prompt)
    transcript.add_message("user", f"Task: {task}")

    step = 0
    final_text = ""
    error_msg: Optional[str] = None

    async with httpx.AsyncClient(timeout=35.0) as client:
        while step < effective_max_steps and transcript.llm_calls < effective_max_llm_calls:
            step += 1
            payload = {
                "model": settings.AGENT_MODEL,
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
                "temperature": 0.2,
            }

            try:
                transcript.record_llm_call()
                t0 = time.time()
                llm_response = await call_llm_with_retry(
                    client=client,
                    base_url=settings.AGENT_LLM_BASE_URL,
                    api_key=settings.AGENT_LLM_API_KEY,
                    payload=payload,
                )
                llm_duration_ms = int((time.time() - t0) * 1000)

                choice = llm_response.get("choices", [{}])[0]
                message = choice.get("message", {})
                tool_calls = message.get("tool_calls")
                content = message.get("content") or ""

                # Record assistant message
                messages.append(message)
                transcript.add_message("assistant", content, tool_calls)

                # If no tool calls, model provided final answer -> stop
                if not tool_calls:
                    final_text = content
                    break

                # Execute all requested tool calls
                for tc in tool_calls:
                    tc_id = tc.get("id", f"call_{int(time.time()*1000)}")
                    func = tc.get("function", {})
                    fn_name = func.get("name", "")
                    fn_args_raw = func.get("arguments", "{}")

                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except Exception:
                        fn_args = {}

                    t_start = time.time()
                    tool_result = await tool_executor.execute(fn_name, fn_args)
                    tool_duration = int((time.time() - t_start) * 1000)

                    transcript.record_tool_execution(
                        tool_name=fn_name,
                        tool_call_id=tc_id,
                        arguments=fn_args,
                        result=tool_result,
                        duration_ms=tool_duration,
                    )

                    # Feed tool response back into conversation
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": fn_name,
                        "content": json.dumps(tool_result),
                    }
                    messages.append(tool_msg)
                    transcript.add_message("tool", json.dumps(tool_result))

            except Exception as exc:
                logger.exception("Error in agent loop step %d: %s", step, exc)
                error_msg = f"Agent error during step {step}: {str(exc)}"
                break

    if not final_text and not error_msg:
        final_text = "Task concluded upon reaching step/budget limits."

    transcript.finish(final_response=final_text, error=error_msg)
    return transcript
