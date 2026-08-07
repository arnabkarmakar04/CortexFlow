
import warnings
import logging
from dotenv import load_dotenv
from ddgs import DDGS
from mcp.server.fastmcp import FastMCP

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("DuckDuckGo Server")


def enforce_presence(**kwargs):
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")


def format_result(result: dict):
    return {
        "title": result.get("title"),
        "link": result.get("href"),
        "snippet": result.get("body"),
    }


@mcp.tool(name="DuckDuckGoSearch")
def duckduckgo_search(query: str):
    """Search the web using DuckDuckGo."""
    try:
        enforce_presence(query=query)
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "results": []
        }

    try:
        with DDGS() as ddgs:
            response = list(ddgs.text(query, max_results=1))

        if not response:
            logger.warning("No search results found.")
            return {
                "status": "error",
                "message": "No search results found.",
                "results": []
            }

        logger.info("DuckDuckGo search completed successfully.")

        return {
            "status": "success",
            "message": "Search completed successfully.",
            "results": [format_result(response[0])]
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


# import warnings
# import logging
# from dotenv import load_dotenv
# from ddgs import DDGS
# from mcp.server.fastmcp import FastMCP

# load_dotenv()
# warnings.filterwarnings("ignore")

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# mcp = FastMCP("DuckDuckGo Server")

# def enforce_presence(**kwargs):
#     for key, value in kwargs.items():
#         if value is None or (isinstance(value, str) and not value.strip()):
#             raise ValueError(f"'{key}' is required. Ask the user for this information.")

# def format_result(result: dict):
#     return {
#         "title": result.get("title"),
#         "link": result.get("href"),
#         "snippet": result.get("body")
#     }

# @mcp.tool(name="DuckDuckGoSearch")
# def duckduckgo_search(query: str):
#     """Search the web using DuckDuckGo."""
#     try:
#         enforce_presence(query=query)
#     except ValueError as e:
#         logger.warning(str(e))
#         return {
#             "status": "error",
#             "message": str(e),
#             "results": []
#         }

#     try:
#         with DDGS() as ddgs:
#             response = list(ddgs.text(query, max_results=5))

#         results = [format_result(result) for result in response]

#         logger.info(f"DuckDuckGo search completed successfully. Returned {len(results)} result(s).")

#         return {
#             "status": "success",
#             "message": "Search completed successfully." if results else "No search results found.",
#             "results": results
#         }

#     except Exception as e:
#         logger.exception(e)
#         return {
#             "status": "error",
#             "message": str(e),
#             "results": []
#         }

# if __name__ == "__main__":
#     mcp.run(transport="stdio")