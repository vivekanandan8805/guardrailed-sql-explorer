import sqlite3

# sqlite3.connect() — Opens a connection to the database file.
# If 'shop.db' doesn't exist yet, SQLite creates it automatically.
conn = sqlite3.connect("shop.db")

# cursor() — Creates a cursor object.
# Think of it as a "pen" that lets you write (execute) SQL commands.
cursor = conn.cursor()

# --- Create Tables ---
# CREATE TABLE IF NOT EXISTS ensures the table is only created once,
# even if you run this script multiple times.

cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id      INTEGER PRIMARY KEY,
        name    TEXT,
        email   TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id          INTEGER PRIMARY KEY,
        customer_id INTEGER,
        amount      INTEGER
    )
""")

# --- Insert Sample Data (safe to rerun) ---
# We check if a record already exists before inserting.
# This prevents duplicate rows on repeated runs.

customers = [
    (1, "Arjun", "arjun@gmail.com"),
    (2, "Kumar", "kumar@gmail.com"),
    (3, "Priya", "priya@gmail.com"),
]

orders = [
    (1, 1, 5000),
    (2, 2, 3000),
    (3, 1, 2000),
    (4, 3, 8000),
]

# INSERT OR IGNORE respects the PRIMARY KEY — if a row with the same id
# already exists it is silently skipped, keeping the script idempotent.
# The ? placeholders are parameterized queries — SQLite fills them in safely,
# protecting against SQL-injection mistakes.

# executemany() — Runs the same SQL statement once for every tuple in the list.
cursor.executemany(
    "INSERT OR IGNORE INTO customers (id, name, email) VALUES (?, ?, ?)",
    customers,
)

cursor.executemany(
    "INSERT OR IGNORE INTO orders (id, customer_id, amount) VALUES (?, ?, ?)",
    orders,
)

# commit() — Saves (persists) all the changes to the database file on disk.
# Without this call, inserts would be lost when the connection closes.
conn.commit()

# --- Retrieve and Print Records ---
# execute() — Runs a single SQL statement.
# fetchall() — Returns every row the last SELECT found, as a list of tuples.

print("=" * 40)
print("CUSTOMERS")
print("=" * 40)
cursor.execute("SELECT * FROM customers")
for row in cursor.fetchall():
    print(f"  ID: {row[0]} | Name: {row[1]} | Email: {row[2]}")

print()
print("=" * 40)
print("ORDERS")
print("=" * 40)
cursor.execute("SELECT * FROM orders")
for row in cursor.fetchall():
    print(f"  ID: {row[0]} | Customer ID: {row[1]} | Amount: ₹{row[2]}")

print()
print("✅ shop.db created and populated successfully!")

# close() — Closes the connection and releases the file handle.
# Always close the connection when you are done.
conn.close()
