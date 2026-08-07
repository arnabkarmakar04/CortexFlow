import warnings
import logging
from datetime import datetime
from mcp.server.fastmcp import FastMCP

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastMCP server
mcp = FastMCP("Time Server")

def format_time_result(now: datetime) -> dict:
    """
    Converts a datetime object into the standardized time result
    structure returned by this MCP server.
    """
    return {
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "day": now.strftime("%A")
    }


@mcp.tool(name="GetCurrentTimeInfo")
def get_current_time_info() -> dict:
    """
    Retrieves the current local time, date, and day of the week.

    Use this tool when the user requests:
    - the current time,
    - today's date,
    - or the current day of the week.

    Returns the temporal information formatted in a structured way.
    """
    try:
        now = datetime.now()

        result = format_time_result(now)

        if not result:
            logger.warning("Failed to parse current time.")
            return {
                "status": "error",
                "message": "Failed to parse current time.",
                "results": []
            }

        logger.info("Time retrieval completed successfully.")

        return {
            "status": "success",
            "message": "Time information retrieved successfully.",
            "results": [result]
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