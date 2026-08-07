import os
import sqlite3
import warnings
import logging
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Expense Tracker Server")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expenses.db")

def enforce_presence(**kwargs):
    """Validates that all required tool arguments are present and non-empty. Raises ValueError when a required argument is missing or contains only whitespace."""
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")

from datetime import datetime


def validate_datetime_range(start_date: str, end_date: str):
    """Validates that the supplied start date occurs on or before the end date. Raises ValueError if the date range is invalid."""
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
    except ValueError:
        raise ValueError(
            "Dates must be in ISO 8601 format (YYYY-MM-DD). Ask the user for valid dates."
        )

    if start > end:
        raise ValueError(
            "'end_date' must be later than or equal to 'start_date'. Ask the user for a valid date range."
        )

def get_connection():
    """Creates and returns a connection to the SQLite expense database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the expense database by creating the required tables if they do not already exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                note TEXT DEFAULT ''
            )
        """)

init_db()

@mcp.tool(name="Add-Expense")
def add_expense(start_date: str, amount: float, category: str, note: str = "", end_date: Optional[str] = None):
    """
Records a new expense in the expense tracker.

Use this tool when the user requests to:
- add,
- record,
- save,
- log,
- or track an expense.

Requires the expense date, amount, and category. An optional note and end date may also be provided.

Returns the recorded expense, including its generated identifier.

Use this tool only when the user's intent is to record a new expense.
    """
    try:
        enforce_presence(start_date=start_date, amount=amount, category=category)
        if end_date is not None:
            validate_datetime_range(start_date, end_date)

        if amount <= 0:
            raise ValueError(
                "'amount' must be greater than zero."
            )
        
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "expense": {}
        }

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO expenses(start_date, end_date, amount, category, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    start_date,
                    end_date,
                    amount,
                    category,
                    note
                ),
            )

        logger.info("Expense recorded successfully.")

        return {
            "status": "success",
            "message": "Expense recorded successfully.",
            "expense": {
                "id": cursor.lastrowid,
                "start_date": start_date,
                "end_date": end_date,
                "amount": amount,
                "category": category,
                "note": note
            }
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "expense": {}
        }

@mcp.tool(name="List-Expenses")
def list_expenses(start_date: str, end_date: str):
    """
Retrieves recorded expenses within a specified date range.

Use this tool when the user requests:
- expense history,
- spending records,
- transactions,
- expenses for a day, week, month, or custom period,
- or wants to review recorded expenses.

Requires a start date and an end date.

Returns every recorded expense within the requested date range.

Use this tool only when the user's intent is to retrieve expense records.
    """ 
    try:
        enforce_presence(start_date=start_date, end_date=end_date)
        if end_date is not None:
            validate_datetime_range(start_date, end_date)

    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "expenses": []
        }

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    id,
                    start_date,
                    end_date,
                    amount,
                    category,
                    note
                FROM expenses
                WHERE start_date BETWEEN ? AND ?
                ORDER BY start_date ASC, id ASC
                """,
                (start_date, end_date),
            )
            rows = cursor.fetchall()

        expenses = [
            {
                "id": row[0],
                "start_date": row[1],
                "end_date": row[2],
                "amount": row[3],
                "category": row[4],
                "note": row[5]
            }
            for row in rows
        ]

        logger.info("Expenses retrieved successfully.")

        return {
            "status": "success",
            "message": "Expenses retrieved successfully." if expenses else "No expenses found.",
            "expenses": expenses
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "expenses": []
        }

@mcp.tool(name="Summarize-Expenses")
def summarize_expenses(start_date: str, end_date: str, category: Optional[str] = None):
    """
Generates a spending summary for a specified date range.

Use this tool when the user requests:
- total spending,
- expense summaries,
- category-wise spending,
- spending breakdowns,
- or aggregated expense reports.

Requires a start date and an end date. An optional category filters the summary to a single expense category.

Returns the total spending grouped by category.

Use this tool only when the user's intent is to summarize recorded expenses.
    """
    try:
        enforce_presence(start_date=start_date, end_date=end_date)
        if end_date is not None:
            validate_datetime_range(start_date, end_date)

    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "summary": []
        }

    try:
        query = """
            SELECT
                category,
                SUM(amount) AS total_amount
            FROM expenses
            WHERE start_date BETWEEN ? AND ?
        """

        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += """
            GROUP BY category
            ORDER BY category ASC
        """

        with get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        summary = [
            {
                "category": row[0],
                "total_amount": row[1]
            }
            for row in rows
        ]

        logger.info("Expense summary retrieved successfully.")

        return {
            "status": "success",
            "message": "Expense summary retrieved successfully." if summary else "No expense summary found.",
            "summary": summary
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "summary": []
        }

if __name__ == "__main__":
    mcp.run(transport="stdio")