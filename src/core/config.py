import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MCP_DIR = PROJECT_ROOT / "src" / "mcp_server"

client_config = {
    "WebSearch": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "web_search_tavily.py")]},
    "Weather": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "weather_server.py")]},
    "ExpenseTracker": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "expense_tracker.py")]},
    "GoogleCalendar": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "google_calendar_server.py")]},
    "WikiPedia": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "wikipedia_server.py")]},
    "StockPrice": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "stock_price_server.py")]},
    "DateTimeServer": {"transport": "stdio", "command": "python", "args": [str(MCP_DIR / "time_server.py")]},
}

orchestrator_llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0.0)
clarification_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)
execution_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
evaluator_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
chat_synth_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.3)
