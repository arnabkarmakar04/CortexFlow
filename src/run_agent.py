import asyncio
import uuid
from datetime import datetime
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

# Ensure the project root is available when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import client_config
from src.graph.workflow import build_graph


async def run_agent():
    mcp_client = MultiServerMCPClient(client_config)
    session_id = str(uuid.uuid4())
    agent_graph = build_graph(mcp_client)
    thread_config = {"configurable": {"thread_id": session_id}}

    print("Agent initialized. Type 'exit' or 'quit' to stop.")

    while True:
        try:
            current_state = await agent_graph.aget_state(thread_config)

            if current_state.tasks and current_state.tasks[0].interrupts:
                interrupt_payload = current_state.tasks[0].interrupts[0].value
                print(f"\nAgent: {interrupt_payload}")
                user_input = await asyncio.to_thread(input, "\nYou: ")
                user_input = user_input.strip()
                print("\n")

                if user_input.lower() in ["exit", "quit"]:
                    break
                if not user_input:
                    continue

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                async for event in agent_graph.astream(
                    {"resume": user_input, "update": {"timestamp": timestamp}},
                    config=thread_config,
                    stream_mode="updates",
                ):
                    pass

            else:
                user_input = await asyncio.to_thread(input, "\nYou: ")
                user_input = user_input.strip()
                print("\n")

                if user_input.lower() in ["exit", "quit"]:
                    break
                if not user_input:
                    continue

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                async for event in agent_graph.astream(
                    {"history": [HumanMessage(content=user_input)], "query": user_input, "timestamp": timestamp},
                    config=thread_config,
                    stream_mode="updates",
                ):
                    pass

            post_state = await agent_graph.aget_state(thread_config)
            if post_state.tasks and post_state.tasks[0].interrupts:
                continue

            result_state = post_state.values
            final_response = result_state.get("final_response")
            if final_response is not None:
                print(f"\nAgent: {final_response}")
            else:
                print("\nAgent: I'm sorry, I couldn't generate a response.")
        except Exception as exc:
            print(f"\n[System Error]: {exc}")


if __name__ == "__main__":
    asyncio.run(run_agent())
