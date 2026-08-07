import asyncio
import json
import logging
from datetime import datetime
from functools import partial
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command, interrupt

from src.core.config import chat_synth_llm, clarification_llm, evaluator_llm, execution_llm
from src.graph.prompts import (
    build_chit_chat_prompt,
    build_clarifier_prompt,
    build_evaluator_prompt,
    build_mcp_prompt,
    build_orchestrator_prompt,
    build_synthesizer_prompt,
)
from src.graph.state import GraphState, ObjectiveCompletionEvaluatorSchema, OrchestratorOutput, RewrittenQueryOutput

logger = logging.getLogger(__name__)


async def get_cached_tools(mcp_client: MultiServerMCPClient):
    if not hasattr(get_cached_tools, "_cache"):
        get_cached_tools._cache = None
    if get_cached_tools._cache is None:
        get_cached_tools._cache = await mcp_client.get_tools()
    return get_cached_tools._cache


def serialize_working_memory(working_memory: list[ToolMessage]) -> str:
    if not working_memory:
        return "No tools have been executed."

    records = []
    for message in working_memory:
        tool_name = message.name or "Unknown Tool"
        records.append(f"Tool: {tool_name}\nResult:\n{message.content}")
    return "\n\n".join(records)


async def orchestrator(state: GraphState) -> GraphState:
    query = state.get("query", "")
    current_time = state.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    history = state.get("history", [])

    context_history = history
    if history and isinstance(history[-1], HumanMessage):
        context_history = history[:-1]

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", build_orchestrator_prompt(current_time)),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("human", "{query}"),
        ]
    )

    chain = prompt_template | execution_llm.with_structured_output(OrchestratorOutput)
    response = await chain.ainvoke({"history": context_history, "query": query})

    return {
        "need_clarification": response.need_clarification,
        "clarification_reason": response.clarification_reason,
        "route": response.route,
        "route_reason": response.route_reason,
        "final_response": None,
        "user_clarification": None,
        "user_clarification_intent_type": None,
        "evaluation_status": None,
        "evaluator_reasoning": None,
        "mcp_loop_count": 0,
    }


async def ambiguity_clarifier(state: GraphState) -> GraphState:
    original_query = state.get("query", "")
    clarification_reason = state.get("clarification_reason", "")
    human_response = interrupt(f"I need a bit more context: {clarification_reason}\nPlease clarify your request.")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", build_clarifier_prompt()),
            ("human", "User's New Response: {human_response}"),
        ]
    )

    structured_llm = clarification_llm.with_structured_output(RewrittenQueryOutput)
    clarification_chain = prompt_template | structured_llm
    response = await clarification_chain.ainvoke({
        "original_query": original_query,
        "clarification_reason": clarification_reason,
        "human_response": human_response,
    })

    new_state = {
        "query": response.rewritten_query,
        "history": [AIMessage(content=(f"I need a bit more context: {clarification_reason}.")), HumanMessage(content=human_response)],
        "need_clarification": False,
        "clarification_reason": None,
        "user_clarification": human_response,
        "user_clarification_intent_type": response.intent_type,
    }

    if response.intent_type == "merge":
        new_state["current_clarification_iteration"] = state.get("current_clarification_iteration", 0) + 1
    else:
        new_state["current_clarification_iteration"] = 0

    return new_state


async def cancel_node(state: GraphState) -> GraphState:
    cancel_response = "Task cancelled. Let me know if there's anything else you'd like to do!"
    return {
        "final_response": cancel_response,
        "history": [AIMessage(content=cancel_response)],
        "need_clarification": False,
        "clarification_reason": None,
        "current_clarification_iteration": 0,
        "mcp_loop_count": 0,
        "user_clarification": None,
        "user_clarification_intent_type": None,
        "evaluation_status": None,
        "evaluator_reasoning": None,
        "route": None,
        "route_reason": None,
    }


async def clarification_limit_node(state: GraphState) -> GraphState:
    clarification_limit_response = "I'm unable to complete this request because the required information wasn't provided after multiple clarification attempts.\nLet's start fresh. Please enter your request again with the required details."
    return {
        "final_response": clarification_limit_response,
        "history": [AIMessage(content=clarification_limit_response)],
        "need_clarification": False,
        "clarification_reason": None,
        "current_clarification_iteration": 0,
        "mcp_loop_count": 0,
        "user_clarification": None,
        "user_clarification_intent_type": None,
        "evaluation_status": None,
        "evaluator_reasoning": None,
        "route": None,
        "route_reason": None,
    }


async def mcp_node(state: GraphState, mcp_client: MultiServerMCPClient) -> GraphState:
    query = state.get("query", "")
    working_memory = state.get("working_memory", [])
    execution_history = serialize_working_memory(working_memory)
    supervisor_feedback = state.get("evaluator_reasoning", "")

    tools = await get_cached_tools(mcp_client)
    llm_with_tools = execution_llm.bind_tools(tools)
    current_time = state.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    messages = [
        ("system", build_mcp_prompt(current_time)),
        ("human", """
Original User Query:
{query}

Execution History:
{execution_history}

Objective Completion Evaluator Feedback:
{supervisor_feedback}
"""),
    ]

    chain = ChatPromptTemplate.from_messages(messages) | llm_with_tools
    response = await chain.ainvoke({
        "query": query,
        "execution_history": execution_history,
        "supervisor_feedback": supervisor_feedback,
    })

    return {
        "planner_tool_calls": response.tool_calls,
        "mcp_loop_count": state.get("mcp_loop_count", 0) + 1,
    }


MAX_CONCURRENT_TOOLS = 5


async def tool_executor_node(state: GraphState, mcp_client: MultiServerMCPClient) -> dict:
    tool_calls = state.get("planner_tool_calls", [])
    if not tool_calls:
        return {"planner_tool_calls": []}

    tools = await get_cached_tools(mcp_client)
    tool_map = {tool.name: tool for tool in tools}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TOOLS)

    async def execute_tool(tool_call: dict) -> ToolMessage:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id")

        if tool_call_id is None:
            raise ValueError("Planner produced a tool call without an id.")
        if tool_name is None:
            raise ValueError(f"Planner produced a tool call without a name. Tool call ID: {tool_call_id}")

        async with semaphore:
            tool = tool_map.get(tool_name)
            if tool is None:
                content = json.dumps({
                    "status": "error",
                    "tool": tool_name,
                    "error_type": "ToolNotFoundError",
                    "message": f"Tool '{tool_name}' not found.",
                })
            else:
                try:
                    result = await tool.ainvoke(tool_args)

                    if isinstance(result, list) and result and isinstance(result[0], dict) and "text" in result[0]:
                        content = result[0]["text"]
                    elif isinstance(result, str):
                        content = result
                    elif isinstance(result, (dict, list)):
                        content = json.dumps(result, default=str)
                    else:
                        content = str(result)
                except Exception as exc:
                    logger.exception("Error while executing tool '%s' with args=%s", tool_name, tool_args)
                    content = json.dumps({
                        "status": "error",
                        "tool": tool_name,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    })

        return ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)

    tool_messages = await asyncio.gather(*(execute_tool(tool_call) for tool_call in tool_calls))

    return {
        "working_memory": tool_messages,
        "planner_tool_calls": [],
    }


async def objective_completion_evaluator(state: GraphState) -> GraphState:
    query = state.get("query", "")
    working_memory = state.get("working_memory", [])
    loop_count = state.get("mcp_loop_count", 0)

    if loop_count >= 3:
        logger.warning("Circuit breaker tripped. Max retries (3) reached for query: '%s'", query)
        return {
            "evaluation_status": "abort",
            "evaluator_reasoning": "Execution aborted: Maximum tool retry limit (3) reached without successfully completing the objective. The system attempted to self-correct but the tool failed repeatedly.",
        }

    execution_history = serialize_working_memory(working_memory)

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", build_evaluator_prompt()),
            ("human", "User Query: {query}\nExecution History:\n{execution_history}"),
        ]
    )

    chain = prompt_template | evaluator_llm.with_structured_output(ObjectiveCompletionEvaluatorSchema)
    response = await chain.ainvoke({"query": query, "execution_history": execution_history})

    return {
        "evaluation_status": response.evaluation_status,
        "evaluator_reasoning": response.reasoning,
    }


async def synthesizer(state: GraphState) -> GraphState:
    query = state.get("query", "")
    working_memory = state.get("working_memory", [])
    status = state.get("evaluation_status", "unknown")
    execution_history = serialize_working_memory(working_memory)

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", build_synthesizer_prompt()),
            ("human", "Original User Query:\n{query}\n\nFinal Execution Status: {status}\n\nExecution History:\n{execution_history}"),
        ]
    )

    chain = prompt_template | chat_synth_llm
    response = await chain.ainvoke({"query": query, "status": status, "execution_history": execution_history})

    delete_messages = [RemoveMessage(id=m.id) for m in working_memory if m.id is not None]

    return {
        "final_response": response.content,
        "history": [AIMessage(content=response.content)],
        "current_clarification_iteration": 0,
        "mcp_loop_count": 0,
        "evaluation_status": None,
        "evaluator_reasoning": None,
        "working_memory": delete_messages,
        "user_clarification": None,
        "user_clarification_intent_type": None,
        "route": None,
        "route_reason": None,
    }


async def rag_node(state: GraphState) -> GraphState:
    delete_messages = [RemoveMessage(id=m.id) for m in state.get("working_memory", []) if m.id is not None]
    return {
        "final_response": "Executing RAG flow...",
        "history": [AIMessage(content="Executing RAG flow...")],
        "current_clarification_iteration": 0,
        "working_memory": delete_messages,
        "mcp_loop_count": 0,
        "evaluation_status": None,
        "evaluator_reasoning": None,
        "user_clarification": None,
        "user_clarification_intent_type": None,
        "route": None,
        "route_reason": None,
    }


async def chit_chat_node(state: GraphState) -> GraphState:
    query = state.get("query", "")
    history = state.get("history", [])
    current_time = state.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    context_history = history
    if history and isinstance(history[-1], HumanMessage):
        context_history = history[:-1]

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", build_chit_chat_prompt(current_time)),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("human", "{query}"),
        ]
    )

    chain = prompt_template | chat_synth_llm
    response = await chain.ainvoke({"history": context_history, "query": query})

    delete_messages = [RemoveMessage(id=m.id) for m in state.get("working_memory", []) if m.id is not None]

    return {
        "final_response": response.content,
        "history": [AIMessage(content=response.content)],
        "current_clarification_iteration": 0,
        "working_memory": delete_messages,
        "mcp_loop_count": 0,
        "user_clarification": None,
        "user_clarification_intent_type": None,
        "evaluation_status": None,
        "evaluator_reasoning": None,
        "route": None,
        "route_reason": None,
    }
