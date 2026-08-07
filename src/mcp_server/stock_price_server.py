import os
import warnings
import logging
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Stock Price Server")

def enforce_presence(**kwargs):
    """Validates that all required tool arguments are present and non-empty. Raises ValueError when a required argument is missing or contains only whitespace."""
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")

def format_stock(data: dict):
    """Converts the Alpha Vantage Global Quote response into the standardized stock data structure returned by this MCP server."""
    quote = data.get("Global Quote", {})
    return {
        "symbol": quote["01. symbol"],
        "open": quote["02. open"],
        "high": quote["03. high"],
        "low": quote["04. low"],
        "price": quote["05. price"],
        "volume": quote["06. volume"],
        "latest_trading_day": quote["07. latest trading day"],
        "previous_close": quote["08. previous close"],
        "change": quote["09. change"],
        "change_percent": quote["10. change percent"]
    }

@mcp.tool(name="StockPrice")

def stock_price(symbol: str):
    """
Retrieves the latest market quote for a publicly traded stock.

Use this tool when the user requests:
- the current stock price,
- the latest trading price,
- today's market quote,
- or recent trading information for a stock ticker.

Requires a valid stock ticker symbol (for example: AAPL, MSFT, TSLA, INFY, TCS).

Returns the latest available market data, including the current price, open, high, low, previous close, trading volume, price change, and percentage change.

Use this tool only when the user's intent is to retrieve the latest stock market information.
    """
    try:
        enforce_presence(symbol=symbol)
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "stock": {}
        }

    try:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol.strip().upper(),
                "apikey": api_key
            },
            timeout=10
        ).json()

        if not response.get("Global Quote") or not response["Global Quote"].get("01. symbol"):
            logger.warning(f"No stock data found for: {symbol}")
            return {
                "status": "error",
                "message": f"No stock data found for '{symbol}'.",
                "stock": {}
            }

        logger.info("Stock information retrieved successfully.")

        return {
            "status": "success",
            "message": "Stock information retrieved successfully.",
            "stock": format_stock(response)
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "stock": {}
        }

if __name__ == "__main__":
    mcp.run(transport="stdio")