import os
import warnings
import logging
from dotenv import load_dotenv
from tavily import TavilyClient
from mcp.server.fastmcp import FastMCP

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_ALLOWED_RESULTS = 10  # Define a maximum limit for results to prevent excessive API calls
mcp = FastMCP("Tavily Search Server")

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def enforce_presence(**kwargs):
    """
    Validates that all required tool arguments are present and non-empty.
    Raises ValueError when a required argument is missing or contains only whitespace.
    """
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")


def format_result(result: dict):
    """
    Converts a raw Tavily search result into the standardized search result
    structure returned by this MCP server.
    """
    return {
        "title": result.get("title"),
        "link": result.get("url"),
        "snippet": result.get("content"),
    }


@mcp.tool(name="TavilySearch")
def tavily_search(query: str, max_results: int = 5):
    """
    Searches the public web using Tavily to retrieve relevant, up-to-date information.

    Use this tool when the user requests:

    - factual information,
    - explanations,
    - research,
    - recent developments,
    - current events,
    - or information that requires searching the public web.

    Requires a search query. The optional `max_results` argument controls the maximum number
    of search results returned.

    Returns the most relevant web search results, including the page title,
    URL, and summary snippet.

    Do not use this tool when a more specialized tool can satisfy the user's request
    (for example, WeatherReport, StockPrice, or Google Calendar tools).

    Use this tool only when the user's intent requires retrieving information from
    the public web.
    """

    try:
        enforce_presence(query=query)
        max_results = max(1, min(max_results, MAX_ALLOWED_RESULTS))

    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "results": []
        }

    try:
        response = tavily.search(
            query=query,
            topic="general",
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
            include_images=False
        )

        results = [
            format_result(result)
            for result in response.get("results", [])
            if result
        ]

        if not results:
            logger.warning("No search results found.")
            return {
                "status": "error",
                "message": "No search results found.",
                "results": []
            }

        logger.info("Tavily search completed successfully.")

        return {
            "status": "success",
            "message": "Search completed successfully.",
            "results": results
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "results": []
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")