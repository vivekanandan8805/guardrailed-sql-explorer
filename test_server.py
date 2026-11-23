"""Quick test: call list_tables() directly and print the result."""
import sys
import os

# Make sure we run from the project folder so shop.db is found correctly
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from server import list_tables

result = list_tables()
print("list_tables() result:", result)
print("Tables found:", len(result))
for t in result:
    print(" -", t)

assert "customers" in result, "ERROR: 'customers' table missing!"
assert "orders"    in result, "ERROR: 'orders' table missing!"
print("\n✅ list_tables() works correctly — both tables confirmed.")
