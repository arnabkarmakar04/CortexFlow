import warnings
import logging
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from langchain_community.utilities import GoogleSerperAPIWrapper

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_ALLOWED_RESULTS = 10 # Define a maximum limit for results to prevent excessive API calls
mcp = FastMCP("Web Search Server")

def enforce_presence(**kwargs):
    """Validates that all required tool arguments are present and non-empty. Raises ValueError when a required argument is missing or contains only whitespace."""
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")

def format_result(result: dict):
    """Converts a raw Google Serper search result into the standardized search result structure returned by this MCP server."""
    return {
        "title": result.get("title"),
        "link": result.get("link"),
        "snippet": result.get("snippet")
    }

@mcp.tool(name="WebSearch")
async def web_search(query: str, max_results: int = 5):
    """
Searches the public web for up-to-date information relevant to a user's query.

Use this tool when the user requests:
- recent or breaking news,
- current events,
- publicly available factual information,
- information about people, organizations, places, products, technologies, or services,
- or any information that requires searching the public web.

Requires a search query. The optional `max_results` argument controls the maximum number of organic search results to return.

Returns the most relevant web search results, including the page title, URL, and summary snippet.

Do not use this tool when a more specialized tool can satisfy the user's request (for example, WeatherReport, StockPrice, or Google Calendar tools).

Use this tool only when the user's intent requires retrieving information from the public web.
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
        search = GoogleSerperAPIWrapper(k=max_results)
        response = await search.aresults(query=query)
        
        if response.get("error"):
            logger.warning(response["error"])
            return {
                "status": "error",
                "message": response["error"],
                "results": []
            }
        results = [format_result(result) for result in response.get("organic", []) if result]

        logger.info("Web search completed successfully.")

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