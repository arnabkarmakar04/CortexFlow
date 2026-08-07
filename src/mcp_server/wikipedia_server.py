import os
import warnings
import logging
import wikipediaapi
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Wikipedia Server")

wiki = wikipediaapi.Wikipedia(
    language="en",
    user_agent=os.getenv("WIKIPEDIA_USER_AGENT")
)


def enforce_presence(**kwargs):
    """Validates that all required tool arguments are present and non-empty. Raises ValueError when a required argument is missing or contains only whitespace."""
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")


@mcp.tool(name="WikipediaSearch")
def wikipedia_search(query: str):
    """
Retrieves the summary of a Wikipedia article for a specified topic.

Use this tool when the user requests:
- general knowledge,
- historical information,
- biographies,
- definitions,
- explanations of concepts,
- or encyclopedic information that is well covered by Wikipedia.

Requires a search query representing the article title or topic.

Returns the article title, Wikipedia URL, and a summary of the matching article.

Do not use this tool when the user requests recent news, current events, or information that requires up-to-date web search.

Use this tool only when the user's intent is to retrieve encyclopedic information from Wikipedia.
    """
    try:
        enforce_presence(query=query)
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "article": []
        }

    try:
        page = wiki.page(query.strip())

        if not page.exists():
            logger.warning(f"No Wikipedia page found for '{query}'.")
            return {
                "status": "error",
                "message": f"No Wikipedia page found for '{query}'.",
                "article": []
            }

        logger.info("Wikipedia article retrieved successfully.")

        return {
            "status": "success",
            "message": "Wikipedia article retrieved successfully.",
            "article": [
                {
                    "title": page.title,
                    "link": page.fullurl,
                    "content": page.summary
                }
            ]
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "article": []
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")