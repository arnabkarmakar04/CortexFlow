from typing import Literal

from src.graph.state import GraphState


def route_after_orchestrator(state: GraphState) -> Literal["Clarifier", "MCP", "RAG", "Chit-Chat"]:
    if state.get("need_clarification"):
        return "Clarifier"
    if state.get("route") == "MCP":
        return "MCP"
    if state.get("route") == "RAG":
        return "RAG"
    return "Chit-Chat"


def route_after_clarifier(state: GraphState) -> Literal["Orchestrator", "ClarificationLimit", "CancelNode"]:
    if state.get("user_clarification_intent_type") == "cancel":
        return "CancelNode"

    if state.get("current_clarification_iteration", 0) >= state.get("max_clarification_iterations", 3):
        return "ClarificationLimit"

    return "Orchestrator"


def route_after_mcp(state: GraphState) -> Literal["ToolExecutor", "Synthesizer"]:
    planner_tool_calls = state.get("planner_tool_calls", [])
    return "ToolExecutor" if planner_tool_calls else "Synthesizer"


def route_after_evaluator(state: GraphState) -> Literal["MCP_Node", "Synthesizer"]:
    status = state.get("evaluation_status")
    if status in ["complete", "abort"]:
        return "Synthesizer"
    if status == "continue":
        return "MCP_Node"
    return "Synthesizer"
