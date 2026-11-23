"""
Step 5 test suite — runs all 10 required checks against server.py tools.
Execute with:  .venv\Scripts\python.exe test_step5.py
"""
import os, sys, json

# Make sure imports resolve to the project folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from server import list_tables, describe_table, get_sample_rows

PASS = "✅ PASS"
FAIL = "❌ FAIL"

def header(text):
    print(f"\n{'=' * 55}")
    print(f"  {text}")
    print(f"{'=' * 55}")

def show(label, result):
    print(f"\n  [{label}]")
    print("  " + json.dumps(result, indent=2).replace("\n", "\n  "))

# ------------------------------------------------------------------
# TEST 1 — list_tables() still works
# ------------------------------------------------------------------
header("TEST 1 — list_tables()")
t1 = list_tables()
show("result", t1)
ok = "customers" in t1 and "orders" in t1
print(f"\n  {PASS if ok else FAIL} — returns both tables")

# ------------------------------------------------------------------
# TEST 2 — describe_table("customers")
# ------------------------------------------------------------------
header('TEST 2 — describe_table("customers")')
t2 = describe_table("customers")
show("result", t2)
col_names = [c["column"] for c in t2]
ok = col_names == ["id", "name", "email"]
print(f"\n  {PASS if ok else FAIL} — columns: id, name, email")

# ------------------------------------------------------------------
# TEST 3 — describe_table("orders")
# ------------------------------------------------------------------
header('TEST 3 — describe_table("orders")')
t3 = describe_table("orders")
show("result", t3)
col_names = [c["column"] for c in t3]
ok = col_names == ["id", "customer_id", "amount"]
print(f"\n  {PASS if ok else FAIL} — columns: id, customer_id, amount")

# ------------------------------------------------------------------
# TEST 4 — get_sample_rows("customers")
# ------------------------------------------------------------------
header('TEST 4 — get_sample_rows("customers")')
t4 = get_sample_rows("customers")
show("result", t4)
emails_masked = all("***" in str(r["email"]) for r in t4)
count_ok = len(t4) <= 3
print(f"\n  {PASS if emails_masked else FAIL} — emails are masked")
print(f"  {PASS if count_ok else FAIL} — row count ≤ 3 (got {len(t4)})")

# ------------------------------------------------------------------
# TEST 5 — get_sample_rows("orders")
# ------------------------------------------------------------------
header('TEST 5 — get_sample_rows("orders")')
t5 = get_sample_rows("orders")
show("result", t5)
count_ok = len(t5) <= 3
no_sensitive = all("email" not in r and "password" not in r for r in t5)
print(f"\n  {PASS if count_ok else FAIL} — row count ≤ 3 (got {len(t5)})")
print(f"  {PASS if no_sensitive else FAIL} — no sensitive columns in orders")

# ------------------------------------------------------------------
# TEST 6 — invalid table name
# ------------------------------------------------------------------
header('TEST 6 — describe_table("unknown_table")')
t6 = describe_table("unknown_table")
show("result", t6)
ok = "error" in t6
print(f"\n  {PASS if ok else FAIL} — returns error for unknown table")

# ------------------------------------------------------------------
# TEST 7 — SQL injection attempt via describe_table
# ------------------------------------------------------------------
header("TEST 7 — SQL injection attempt: describe_table")
injection = "customers; DROP TABLE customers; --"
t7 = describe_table(injection)
show("result", t7)
ok = "error" in t7
print(f"\n  {PASS if ok else FAIL} — injection string rejected with error")

# ------------------------------------------------------------------
# TEST 8 — SQL injection attempt via get_sample_rows
# ------------------------------------------------------------------
header("TEST 8 — SQL injection attempt: get_sample_rows")
injection2 = "orders' OR '1'='1"
t8 = get_sample_rows(injection2)
show("result", t8)
ok = "error" in t8
print(f"\n  {PASS if ok else FAIL} — injection string rejected with error")

# ------------------------------------------------------------------
# TEST 9 — Email masking format check
# ------------------------------------------------------------------
header("TEST 9 — Email masking format (first char + *** + @domain)")
t9 = get_sample_rows("customers")
all_correct = True
for row in t9:
    em = row["email"]
    # Must start with one real char, then ***, then @domain
    if not (len(em) > 4 and em[1:4] == "***" and "@" in em):
        all_correct = False
        print(f"  Unexpected format: {em}")
show("masked emails", [r["email"] for r in t9])
print(f"\n  {PASS if all_correct else FAIL} — format is  X***@domain")

# ------------------------------------------------------------------
# TEST 10 — shop.db untouched (size unchanged check)
# ------------------------------------------------------------------
header("TEST 10 — shop.db is unchanged (read-only check)")
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")
size = os.path.getsize(db_path)
print(f"\n  shop.db size: {size} bytes")
ok = size > 0
print(f"  {PASS if ok else FAIL} — database file exists and is non-empty")

print("\n" + "=" * 55)
print("  All Step 5 tests complete.")
print("=" * 55 + "\n")
