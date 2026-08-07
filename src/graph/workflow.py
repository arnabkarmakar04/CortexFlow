from functools import partial

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.core.config import client_config
from src.graph.nodes import (
    ambiguity_clarifier,
    cancel_node,
    chit_chat_node,
    clarification_limit_node,
    mcp_node,
    objective_completion_evaluator,
    orchestrator,
    rag_node,
    synthesizer,
    tool_executor_node,
)
from src.graph.router import (
    route_after_clarifier,
    route_after_evaluator,
    route_after_mcp,
    route_after_orchestrator,
)
from src.graph.state import GraphState


def build_graph(mcp_client: MultiServerMCPClient):
    memory = InMemorySaver()

    workflow = StateGraph(GraphState)
    mcp_node_with_client = partial(mcp_node, mcp_client=mcp_client)
    tool_executor_with_client = partial(tool_executor_node, mcp_client=mcp_client)

    workflow.add_node("Orchestrator", orchestrator)
    workflow.add_node("Clarifier", ambiguity_clarifier)
    workflow.add_node("CancelNode", cancel_node)
    workflow.add_node("ClarificationLimit", clarification_limit_node)
    workflow.add_node("MCP_Node", mcp_node_with_client)
    workflow.add_node("ToolExecutor", tool_executor_with_client)
    workflow.add_node("Evaluator", objective_completion_evaluator)
    workflow.add_node("Synthesizer", synthesizer)
    workflow.add_node("RAG", rag_node)
    workflow.add_node("ChitChat", chit_chat_node)

    workflow.add_edge(START, "Orchestrator")
    workflow.add_conditional_edges(
        "Orchestrator",
        route_after_orchestrator,
        {
            "Clarifier": "Clarifier",
            "MCP": "MCP_Node",
            "RAG": "RAG",
            "Chit-Chat": "ChitChat",
        },
    )
    workflow.add_conditional_edges(
        "Clarifier",
        route_after_clarifier,
        {
            "Orchestrator": "Orchestrator",
            "ClarificationLimit": "ClarificationLimit",
            "CancelNode": "CancelNode",
        },
    )
    workflow.add_conditional_edges(
        "MCP_Node",
        route_after_mcp,
        {
            "ToolExecutor": "ToolExecutor",
            "Synthesizer": "Synthesizer",
        },
    )
    workflow.add_edge("ToolExecutor", "Evaluator")
    workflow.add_conditional_edges(
        "Evaluator",
        route_after_evaluator,
        {
            "MCP_Node": "MCP_Node",
            "Synthesizer": "Synthesizer",
        },
    )

    workflow.add_edge("CancelNode", END)
    workflow.add_edge("ClarificationLimit", END)
    workflow.add_edge("Synthesizer", END)
    workflow.add_edge("RAG", END)
    workflow.add_edge("ChitChat", END)

    return workflow.compile(checkpointer=memory, debug=True)
