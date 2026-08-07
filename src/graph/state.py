from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage, ToolCall, ToolMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

Route = Literal["MCP", "RAG", "Clarifier", "Chit-Chat"]


class GraphState(TypedDict):
    history: Annotated[list[BaseMessage], add_messages]
    working_memory: Annotated[list[ToolMessage], add_messages]
    planner_tool_calls: list[ToolCall] | None

    timestamp: str
    query: str

    need_clarification: bool
    clarification_reason: str | None
    user_clarification: str | None
    user_clarification_intent_type: Literal["merge", "context_switch", "cancel"] | None
    current_clarification_iteration: int
    max_clarification_iterations: Annotated[int, Field(default=3, description="Maximum clarification attempts allowed for a single user query.")]

    route: Route
    route_reason: str

    evaluation_status: Literal["complete", "continue", "abort"] | None
    evaluator_reasoning: str | None
    mcp_loop_count: int

    final_response: str


class OrchestratorOutput(BaseModel):
    """Output of the main orchestrator."""

    need_clarification: bool = Field(description="Indicates whether the user's request is ambiguous and requires clarification.")
    clarification_reason: str | None = Field(description="Reason for requesting clarification from the user.")
    route: Route
    route_reason: str = Field(description="Reason for selecting the specific route.")


class RewrittenQueryOutput(BaseModel):
    intent_type: Literal["merge", "context_switch", "cancel"] = Field(
        description="Categorize the user's response. 'merge' if the user provides the missing information. 'context_switch' if the user starts a completely new request. 'cancel' if the user aborts the current task."
    )
    rewritten_query: str = Field(
        description="If intent is 'merge', return the fully merged query. Otherwise return exactly the user's response."
    )


class ObjectiveCompletionEvaluatorSchema(BaseModel):
    evaluation_status: Literal["complete", "continue", "abort"] = Field(
        description=(
            "'complete' if the original user objective has been fully satisfied. "
            "'continue' if additional tool execution is required, or if the Execution History contains a recoverable execution failure that the planner can resolve. "
            "'abort' only if the Execution History contains an unrecoverable tool or service failure."
        )
    )
    reasoning: str = Field(
        description=(
            "Concise, evidence-based evaluation and planning guidance derived solely "
            "from the Execution History."
        )
    )
