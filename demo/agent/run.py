"""CLI entrypoint for running the procurement agent."""
import argparse
import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys

from .config import agent_settings
from .loop import run_agent_loop
from .tools import AgentToolExecutor
from .transcript import RunTranscript

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent.run")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the LLM-driven procurement agent against the store and firewall."
    )
    parser.add_argument(
        "--task",
        type=str,
        default="Buy 2 boxes of printer paper under $30",
        help="The procurement task instruction for the agent",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default="clean",
        help="Store variant (clean, hidden_dom, fake_system_banner, review_injection, etc.)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["naive", "hardened"],
        default="naive",
        help="Agent security mode: naive (default) or hardened (defensive prompt)",
    )
    parser.add_argument(
        "--store-url",
        type=str,
        default=None,
        help="Base URL of the mock store (default: http://localhost:9000)",
    )
    parser.add_argument(
        "--firewall-url",
        type=str,
        default=None,
        help="Base URL of the payment firewall (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model name",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Maximum loop steps (default: 8)",
    )
    parser.add_argument(
        "--max-llm-calls",
        type=int,
        default=None,
        help="Maximum LLM calls (default: 12)",
    )
    parser.add_argument(
        "--transcript-dir",
        type=str,
        default="results/transcripts",
        help="Directory to save JSON transcripts",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    settings = agent_settings
    if args.model:
        settings.AGENT_MODEL = args.model

    print(f"\n=======================================================")
    print(f"🚀 AGENT STARTING RUN")
    print(f"   Task:     {args.task}")
    print(f"   Variant:  {args.variant}")
    print(f"   Mode:     {args.mode}")
    print(f"   Model:    {settings.AGENT_MODEL}")
    print(f"=======================================================\n")

    tool_executor = AgentToolExecutor(
        settings=settings,
        store_base_url=args.store_url,
        firewall_base_url=args.firewall_url,
        variant=args.variant,
    )

    secrets = [settings.AGENT_LLM_API_KEY, settings.get_effective_agent_key()]
    transcript = RunTranscript(
        task=args.task,
        variant=args.variant,
        mode=args.mode,
        model=settings.AGENT_MODEL,
        secrets_to_mask=secrets,
    )

    transcript = await run_agent_loop(
        task=args.task,
        settings=settings,
        variant=args.variant,
        mode=args.mode,
        tool_executor=tool_executor,
        transcript=transcript,
        max_steps=args.max_steps,
        max_llm_calls=args.max_llm_calls,
    )

    # Save transcript
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_task = "".join(c if c.isalnum() else "_" for c in args.task[:30])
    filename = f"{timestamp}_{args.variant}_{args.mode}_{clean_task}.json"
    filepath = Path(args.transcript_dir) / filename
    saved_path = transcript.save(str(filepath))

    print(f"\n=======================================================")
    print(f"🏁 AGENT RUN COMPLETE")
    print(f"   Duration:         {transcript.duration_ms} ms")
    print(f"   LLM Calls:        {transcript.llm_calls}")
    print(f"   Tool Calls:       {len(transcript.tool_calls)}")
    print(f"   Intents Sent:     {len(tool_executor.submitted_intents)}")
    if tool_executor.last_payment_decision:
        print(f"   Firewall Decision:{tool_executor.last_payment_decision.get('decision')}")
    print(f"   Final Response:   {transcript.final_response}")
    print(f"   Transcript saved: {saved_path}")
    print(f"=======================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
