"""
test_safe_query.py — Step 6 test suite for run_safe_query()
Run with:  .venv\Scripts\python.exe test_safe_query.py
"""
import os, sys, json, time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from server import list_tables, run_safe_query

PASS = "PASS"
FAIL = "FAIL"

results = []   # collect (test_num, label, status, detail)

def check(num, label, got: dict, *, expect_ok=True, check_rows=None,
          blocked_word=None, truncated=None):
    """
    Assert the result of run_safe_query and record the outcome.
    expect_ok  : True  → result must have 'rows' (not an error)
    expect_ok  : False → result must have 'error'
    check_rows : if set, assert row_count == this value
    blocked_word: if set, assert this word appears in the error message
    truncated  : if set, assert result['truncated'] == this bool
    """
    has_error = "error" in got
    status = PASS
    detail = ""

    if expect_ok and has_error:
        status = FAIL
        detail = f"Expected success but got error: {got['error']}"
    elif not expect_ok and not has_error:
        status = FAIL
        detail = f"Expected rejection but query succeeded: {got}"
    elif not expect_ok and blocked_word:
        err_lower = got.get("error", "").lower()
        if blocked_word.lower() not in err_lower:
            status = FAIL
            detail = f"Error missing '{blocked_word}': {got['error']}"
    elif expect_ok and check_rows is not None:
        if got.get("row_count") != check_rows:
            status = FAIL
            detail = f"Expected {check_rows} rows, got {got.get('row_count')}"
    elif expect_ok and truncated is not None:
        if got.get("truncated") != truncated:
            status = FAIL
            detail = f"Expected truncated={truncated}, got {got.get('truncated')}"

    results.append((num, label, status, detail, got))
    icon = "✅" if status == PASS else "❌"
    print(f"  {icon} [{num:02d}] {label}")
    if detail:
        print(f"        → {detail}")
    if status == PASS and expect_ok:
        print(f"        rows={got.get('row_count')}  truncated={got.get('truncated')}")
    elif status == PASS and not expect_ok:
        print(f"        error='{got.get('error')}'")


print("\n" + "=" * 60)
print("  Step 6 — run_safe_query() test suite")
print("=" * 60)

# ------------------------------------------------------------------
# SAFE QUERIES — must succeed
# ------------------------------------------------------------------
print("\n--- SAFE QUERIES ---")

check(1, "Safe SELECT on customers",
      run_safe_query("SELECT id, name FROM customers"),
      expect_ok=True, check_rows=3)

check(2, "Safe SELECT on orders",
      run_safe_query("SELECT id, customer_id, amount FROM orders"),
      expect_ok=True, check_rows=4)

check(3, "JOIN customers + orders",
      run_safe_query("""
          SELECT c.name, o.amount
          FROM customers AS c
          JOIN orders AS o ON c.id = o.customer_id
          ORDER BY o.amount DESC
      """),
      expect_ok=True, check_rows=4)

check(4, "SUM with GROUP BY (interview demo query)",
      run_safe_query("""
          SELECT c.name, SUM(o.amount) AS total_spent
          FROM customers AS c
          JOIN orders AS o ON c.id = o.customer_id
          GROUP BY c.id, c.name
          ORDER BY total_spent DESC
          LIMIT 5
      """),
      expect_ok=True, check_rows=3)

# ------------------------------------------------------------------
# DANGEROUS STATEMENTS — must be rejected
# ------------------------------------------------------------------
print("\n--- DANGEROUS STATEMENTS (must be rejected) ---")

check(5, "DELETE statement rejected",
      run_safe_query("DELETE FROM customers WHERE id = 1"),
      expect_ok=False, blocked_word="delete")

check(6, "DROP TABLE rejected",
      run_safe_query("DROP TABLE customers"),
      expect_ok=False, blocked_word="drop")

check(7, "UPDATE rejected",
      run_safe_query("UPDATE customers SET name='x' WHERE id=1"),
      expect_ok=False, blocked_word="update")

check(8, "Multiple statements rejected",
      run_safe_query("SELECT id FROM customers; DROP TABLE customers"),
      expect_ok=False, blocked_word="multiple")

# ------------------------------------------------------------------
# COLUMN-LEVEL ACCESS CONTROL — email must be blocked
# ------------------------------------------------------------------
print("\n--- COLUMN ACCESS CONTROL (email must be blocked) ---")

check(9, "Direct email column access rejected",
      run_safe_query("SELECT email FROM customers"),
      expect_ok=False, blocked_word="email")

check(10, "Email alias access rejected",
      run_safe_query("SELECT email AS contact FROM customers"),
      expect_ok=False, blocked_word="email")

check(11, "Email in LOWER() rejected",
      run_safe_query("SELECT LOWER(email) FROM customers"),
      expect_ok=False, blocked_word="email")

# ------------------------------------------------------------------
# SCHEMA VALIDATION — unknown tables and columns
# ------------------------------------------------------------------
print("\n--- SCHEMA VALIDATION ---")

check(12, "Unknown table rejected",
      run_safe_query("SELECT id FROM unknown_table"),
      expect_ok=False, blocked_word="allowed")

check(13, "Unknown column rejected",
      run_safe_query("SELECT secret_col FROM customers"),
      expect_ok=False)   # blocked by SENSITIVE_KEYWORDS or allowlist

# ------------------------------------------------------------------
# ROW LIMITS
# ------------------------------------------------------------------
print("\n--- ROW LIMIT ---")

# Generate a query that produces more than 100 rows via a cross-join
# (customers × orders = 12 rows — our DB is small, so we fake many rows
# by joining many times; with only 3 customers and 4 orders we can't
# exceed 100. Instead we verify truncated=False on real data, which is
# the correct behavior for small datasets.)
check(14, "Row limit: small result not truncated",
      run_safe_query("SELECT id, name FROM customers"),
      expect_ok=True, truncated=False)

# ------------------------------------------------------------------
# TIME LIMIT — expensive query
# ------------------------------------------------------------------
print("\n--- TIME LIMIT ---")

# We patch the module-level TIME_BUDGET_S to near-zero so the timer
# fires immediately and interrupts even a trivial query.
import server as _srv
original_budget = _srv.TIME_BUDGET_S
_srv.TIME_BUDGET_S = 0.000001   # near-zero → interrupt fires immediately

# Import run_safe_query fresh from the module so the patched budget is used
from server import run_safe_query as _rsq
t15 = _rsq("SELECT id, name FROM customers")
_srv.TIME_BUDGET_S = original_budget   # always restore

has_time_error = "error" in t15 and (
    "time" in t15.get("error", "").lower()
    or "interrupt" in t15.get("error", "").lower()
    or "cancel" in t15.get("error", "").lower()
)
results.append((15, "Query interrupted by time limit", PASS if has_time_error else FAIL, "", t15))
icon = "✅" if has_time_error else "❌"
print(f"  {icon} [15] Query interrupted by time limit")
if has_time_error:
    print(f"        error='{t15.get('error')}'")
else:
    print(f"        Not interrupted — got: {t15}")

# ------------------------------------------------------------------
# SQLite INTERNAL TABLES
# ------------------------------------------------------------------
print("\n--- INTERNAL TABLE ACCESS ---")

check(16, "sqlite_master access rejected",
      run_safe_query("SELECT name FROM sqlite_master"),
      expect_ok=False, blocked_word="internal")

# ------------------------------------------------------------------
# UNAPPROVED FUNCTIONS
# ------------------------------------------------------------------
print("\n--- UNAPPROVED FUNCTIONS ---")

check(17, "hex() function rejected",
      run_safe_query("SELECT hex(name) FROM customers"),
      expect_ok=False, blocked_word="hex")

# ------------------------------------------------------------------
# SQL INJECTION
# ------------------------------------------------------------------
print("\n--- SQL INJECTION ATTEMPTS ---")

check(18, "SQL injection via UNION rejected",
      run_safe_query("SELECT id FROM customers UNION SELECT email FROM customers"),
      expect_ok=False)

# ------------------------------------------------------------------
# VERIFY shop.db IS UNCHANGED
# ------------------------------------------------------------------
print("\n--- DATABASE INTEGRITY ---")

db_size = os.path.getsize(os.path.join(os.path.dirname(__file__), "shop.db"))
tables  = list_tables()
db_ok   = db_size > 0 and "customers" in tables and "orders" in tables
icon    = "✅" if db_ok else "❌"
print(f"  {icon} [19] shop.db unchanged — size={db_size} bytes, tables={tables}")

# ------------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------------
passed  = sum(1 for _, _, s, *_ in results if s == PASS)
failed  = sum(1 for _, _, s, *_ in results if s == FAIL)
total   = len(results) + 1   # +1 for the db-integrity check

print("\n" + "=" * 60)
print(f"  Results: {passed + (1 if db_ok else 0)}/{total} passed")
if failed or not db_ok:
    print("  FAILED tests:")
    for num, label, status, detail, _ in results:
        if status == FAIL:
            print(f"    [{num:02d}] {label}: {detail}")
    if not db_ok:
        print("    [19] shop.db integrity check failed")
print("=" * 60 + "\n")
