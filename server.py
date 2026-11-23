
import os
import sqlite3
import time

import sqlglot
from sqlglot import exp
from mcp.server.mcpserver import MCPServer


# ============================================================
# STEP 1: MCP SERVER SETUP
# ============================================================

mcp = MCPServer("SQL Explorer")

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "shop.db"
)

SENSITIVE_KEYWORDS = (
    "email",
    "phone",
    "mobile",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "auth",
    "ssn",
    "card",
)

ALLOWED_COLUMNS = {
    "customers": {"id", "name"},
    "orders": {"id", "customer_id", "amount"},
}

ALLOWED_FUNCTIONS = {
    "sum", "count", "avg", "min", "max",
    "upper", "lower", "length",
    "coalesce", "ifnull", "nullif",
    "abs", "round",
    "strftime", "date", "time",
}

MAX_SQL_LENGTH = 5000
MAX_ROWS = 100
FETCH_LIMIT = MAX_ROWS + 1
TIME_BUDGET_S = 2.0


# ============================================================
# STEP 2: DATABASE HELPERS
# ============================================================

def get_connection():
    """Open the SQLite database in read-only mode."""

    conn = sqlite3.connect(
        f"file:{DB_PATH}?mode=ro",
        uri=True
    )

    conn.execute("PRAGMA query_only = ON")

    return conn


def get_valid_table(cursor, table_name):
    """Check whether a table exists."""

    if not isinstance(table_name, str):
        return None

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        AND name = ?
        """,
        (table_name,)
    )

    row = cursor.fetchone()

    return row[0] if row else None


def is_sensitive(column_name):
    """Check whether a column contains sensitive data."""

    name = column_name.lower()

    return any(
        keyword in name
        for keyword in SENSITIVE_KEYWORDS
    )


def mask_value(column_name, value):
    """Hide sensitive values before returning sample rows."""

    if value is None:
        return None

    if "email" in column_name.lower():
        value = str(value)

        if "@" in value:
            local, domain = value.split("@", 1)
            return local[:1] + "***@" + domain

    return "***"


# ============================================================
# TOOL 1: LIST TABLES
# ============================================================

@mcp.tool()
def list_tables() -> list[str]:
    """Return all user-defined tables in the database."""

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )

        return [
            row[0]
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()


# ============================================================
# TOOL 2: DESCRIBE TABLE
# ============================================================

@mcp.tool()
def describe_table(table_name: str) -> list[dict] | dict:
    """Return column names and data types."""

    conn = get_connection()

    try:
        cursor = conn.cursor()

        safe_table = get_valid_table(
            cursor,
            table_name
        )

        if safe_table is None:
            return {
                "error": (
                    f"Table '{table_name}' does not exist "
                    "or is not a user table."
                ),
                "hint": "Call list_tables() first."
            }

        cursor.execute(
            f'PRAGMA table_info("{safe_table}")'
        )

        return [
            {
                "column": row[1],
                "type": row[2]
            }
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()


# ============================================================
# TOOL 3: GET SAMPLE ROWS
# ============================================================

@mcp.tool()
def get_sample_rows(table_name: str) -> list[dict] | dict:
    """Return up to three rows with sensitive data masked."""

    conn = get_connection()

    try:
        cursor = conn.cursor()

        safe_table = get_valid_table(
            cursor,
            table_name
        )

        if safe_table is None:
            return {
                "error": (
                    f"Table '{table_name}' does not exist "
                    "or is not a user table."
                )
            }

        cursor.execute(
            f'SELECT * FROM "{safe_table}" LIMIT 3'
        )

        columns = [
            item[0]
            for item in cursor.description
        ]

        result = []

        for row in cursor.fetchall():
            record = {}

            for column, value in zip(columns, row):

                if is_sensitive(column):
                    record[column] = mask_value(
                        column,
                        value
                    )
                else:
                    record[column] = value

            result.append(record)

        return result

    finally:
        conn.close()


# ============================================================
# STEP 3: SQL SECURITY VALIDATION
# ============================================================

class SQLGuardrail:
    """Validate SQL before allowing database execution."""

    FORBIDDEN_NODE_TYPES = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
        exp.Subquery,
        exp.Union,
        exp.Intersect,
        exp.Except,
        exp.CTE,
        exp.Window,
    )

    def validate(self, sql):

        # ----------------------------------------------------
        # 1. Validate input
        # ----------------------------------------------------

        if not isinstance(sql, str):
            return "SQL must be a string."

        if not sql.strip():
            return "Empty SQL statement."

        if len(sql) > MAX_SQL_LENGTH:
            return (
                f"SQL too long. Maximum is "
                f"{MAX_SQL_LENGTH} characters."
            )

        # ----------------------------------------------------
        # 2. Parse SQL
        # ----------------------------------------------------

        try:
            statements = sqlglot.parse(
                sql,
                dialect="sqlite",
                error_level=sqlglot.ErrorLevel.RAISE
            )

        except Exception:
            return "SQL parse error. Invalid SQL syntax."

        # ----------------------------------------------------
        # 3. Only one statement
        # ----------------------------------------------------

        if len(statements) != 1:
            return (
                "Only one SQL statement is allowed. "
                "Multiple statements were detected."
            )

        statement = statements[0]

        if statement is None:
            return "Empty SQL statement."

        # ----------------------------------------------------
        # 4. SELECT only
        # ----------------------------------------------------

        if not isinstance(statement, exp.Select):
            kind = type(statement).__name__.upper()

            return (
                "Only SELECT queries are allowed. "
                f"Received: {kind}."
            )

        # ----------------------------------------------------
        # 5. Reject dangerous SQL constructs
        # ----------------------------------------------------

        for node in statement.walk():

            if isinstance(
                node,
                self.FORBIDDEN_NODE_TYPES
            ):
                return (
                    "Forbidden SQL construct detected: "
                    f"{type(node).__name__}."
                )

        # ----------------------------------------------------
        # 6. Reject SELECT *
        # ----------------------------------------------------

        for node in statement.find_all(exp.Star):
            return (
                "SELECT * is not allowed. "
                "List the required columns."
            )

        # ----------------------------------------------------
        # 7. Validate tables
        # ----------------------------------------------------

        alias_map = {}

        for table in statement.find_all(exp.Table):

            table_name = (
                table.name or ""
            ).lower()

            if table.db or table.catalog:
                return (
                    "Database-qualified tables "
                    "are not allowed."
                )

            if table_name.startswith("sqlite_"):
                return (
                    f"Access to internal table "
                    f"'{table_name}' is not allowed."
                )

            if table_name not in ALLOWED_COLUMNS:
                return (
                    f"Table '{table_name}' is not "
                    "in the allowed list. "
                    f"Allowed: {sorted(ALLOWED_COLUMNS)}"
                )

            alias = (
                table.alias or table_name
            ).lower()

            if alias in alias_map:
                return (
                    f"Duplicate table alias: '{alias}'."
                )

            alias_map[alias] = table_name

            if table_name not in alias_map:
                alias_map[table_name] = table_name

        if not alias_map:
            return "A permitted table is required."

        # ----------------------------------------------------
        # 8. Collect SELECT output aliases
        # ----------------------------------------------------

        select_aliases = {
            expression.alias.lower()
            for expression in statement.expressions
            if (
                isinstance(expression, exp.Alias)
                and expression.alias
            )
        }

        # ----------------------------------------------------
        # 9. Validate columns
        # ----------------------------------------------------

        for column in statement.find_all(exp.Column):

            column_name = (
                column.name or ""
            ).lower()

            qualifier = (
                column.table or ""
            ).lower()

            if column.db or column.catalog:
                return (
                    "Database-qualified columns "
                    "are not allowed."
                )

            # Sensitive columns are always rejected.
            if is_sensitive(column_name):
                return (
                    f"Column '{column_name}' contains "
                    "sensitive data and cannot be "
                    "accessed through run_safe_query."
                )

            # Allow SELECT aliases in ORDER BY.
            # Example: ORDER BY total_spent DESC
            parent = column.parent

            if (
                not qualifier
                and column_name in select_aliases
                and isinstance(parent, exp.Ordered)
            ):
                continue

            # Qualified column: c.name
            if qualifier:

                real_table = alias_map.get(
                    qualifier
                )

                if real_table is None:
                    return (
                        f"Unknown table or alias: "
                        f"'{qualifier}'."
                    )

                if (
                    column_name
                    not in ALLOWED_COLUMNS[real_table]
                ):
                    return (
                        f"Column '{column_name}' is not "
                        f"allowed for table '{real_table}'."
                    )

            # Unqualified column: name
            else:

                matches = [
                    table_name
                    for table_name in set(
                        alias_map.values()
                    )
                    if (
                        column_name
                        in ALLOWED_COLUMNS[table_name]
                    )
                ]

                if len(matches) == 0:
                    return (
                        f"Unknown or forbidden column: "
                        f"'{column_name}'."
                    )

                if len(matches) > 1:
                    return (
                        f"Ambiguous column: "
                        f"'{column_name}'. "
                        "Use a table alias."
                    )

        # ----------------------------------------------------
        # 10. Validate functions
        # ----------------------------------------------------

        for function in statement.find_all(exp.Func):

            if isinstance(function, exp.Anonymous):
                function_name = str(
                    function.this
                ).lower()

            else:
                function_name = (
                    type(function).__name__.lower()
                )

            function_aliases = {
                "currentdate": "date",
                "currenttimestamp": "time",
            }

            function_name = function_aliases.get(
                function_name,
                function_name
            )

            if function_name not in ALLOWED_FUNCTIONS:
                return (
                    f"Function '{function_name}' is "
                    "not in the approved list. "
                    f"Allowed: {sorted(ALLOWED_FUNCTIONS)}"
                )

        return None


# Create one validator instance.
_guardrail = SQLGuardrail()


# ============================================================
# TOOL 4: RUN SAFE QUERY
# ============================================================

@mcp.tool()
def run_safe_query(sql: str) -> dict:
    """
    Execute a validated read-only SELECT query.

    Security:
    - SELECT only
    - Allowed tables and columns
    - Sensitive column protection
    - Approved functions
    - Maximum 100 returned rows
    - Two-second time budget
    """

    # --------------------------------------------------------
    # 1. Validate SQL before execution
    # --------------------------------------------------------

    error = _guardrail.validate(sql)

    if error:
        return {"error": error}

    conn = None

    try:

        # ----------------------------------------------------
        # 2. Read-only database connection
        # ----------------------------------------------------

        conn = get_connection()

        # ----------------------------------------------------
        # 3. Start timeout clock
        # ----------------------------------------------------

        start_time = time.monotonic()

        def progress_handler():

            elapsed = (
                time.monotonic() - start_time
            )

            if elapsed >= TIME_BUDGET_S:
                return 1

            return 0

        conn.set_progress_handler(
            progress_handler,
            1000
        )

        # ----------------------------------------------------
        # 4. Execute SQL
        # ----------------------------------------------------

        try:
            cursor = conn.cursor()

            cursor.execute(sql)

            columns = [
                item[0]
                for item in cursor.description
            ]

            raw_rows = cursor.fetchmany(
                FETCH_LIMIT
            )

        finally:
            conn.set_progress_handler(
                None,
                0
            )

        # ----------------------------------------------------
        # 5. Check elapsed time after fetching
        # ----------------------------------------------------

        elapsed = time.monotonic() - start_time

        if elapsed >= TIME_BUDGET_S:
            return {
                "error": (
                    f"Query exceeded the "
                    f"{TIME_BUDGET_S}s time limit "
                    "and was cancelled."
                )
            }

        # ----------------------------------------------------
        # 6. Enforce row limit
        # ----------------------------------------------------

        truncated = (
            len(raw_rows) > MAX_ROWS
        )

        rows_to_return = raw_rows[:MAX_ROWS]

        # ----------------------------------------------------
        # 7. Build result
        # ----------------------------------------------------

        rows = [
            dict(zip(columns, row))
            for row in rows_to_return
        ]

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated
        }

    except sqlite3.OperationalError as error:

        message = str(error)

        if "interrupted" in message.lower():
            return {
                "error": (
                    f"Query exceeded the "
                    f"{TIME_BUDGET_S}s time limit "
                    "and was cancelled."
                )
            }

        return {
            "error": f"Database error: {message}"
        }

    except Exception:
        return {
            "error": (
                "An unexpected error occurred. "
                "Query was not executed."
            )
        }

    finally:
        if conn is not None:
            conn.close()


# ============================================================
# START MCP SERVER
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
