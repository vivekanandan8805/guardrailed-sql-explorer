import sqlite3

# Connect to the existing shop.db database (does NOT recreate it)
conn = sqlite3.connect("shop.db")

# cursor() — Creates a cursor object, like a pointer that lets you
# send SQL commands and read back results from the database.
cursor = conn.cursor()

# ------------------------------------------------------------------
# SECTION 1 — All Customers
# ------------------------------------------------------------------
# cursor.execute() — Sends one SQL statement to the database engine.
# SELECT * FROM customers — Means "give me every column (*) from the
# customers table".  SQLite runs the query and holds the results ready.
print("=" * 45)
print("  ALL CUSTOMERS")
print("=" * 45)

cursor.execute("SELECT * FROM customers")

# fetchall() — Collects every row the last SELECT found and returns
# them as a list of tuples.  Each tuple is one row.
customers = cursor.fetchall()

for row in customers:
    print(f"  ID: {row[0]} | Name: {row[1]} | Email: {row[2]}")

# ------------------------------------------------------------------
# SECTION 2 — All Orders
# ------------------------------------------------------------------
# SELECT * FROM orders — Same idea: every column from the orders table.
print()
print("=" * 45)
print("  ALL ORDERS")
print("=" * 45)

cursor.execute("SELECT * FROM orders")

orders = cursor.fetchall()

for row in orders:
    print(f"  Order ID: {row[0]} | Customer ID: {row[1]} | Amount: ₹{row[2]}")

# ------------------------------------------------------------------
# SECTION 3 — Total Spending per Customer (JOIN query)
# ------------------------------------------------------------------
# JOIN — Combines rows from two tables by matching a shared column.
#   Here we match customers.id  with  orders.customer_id
#   so each order row gets the customer's name attached to it.
#
# GROUP BY — After the join, rows with the same customer name are
#   collapsed into one group so we can do maths on each group.
#
# SUM(orders.amount) — Adds up every amount value inside each group,
#   giving us the total spending for that customer.
print()
print("=" * 45)
print("  TOTAL SPENDING PER CUSTOMER")
print("=" * 45)

query = """
    SELECT
        customers.name,
        SUM(orders.amount) AS total_spent
    FROM customers
    JOIN orders
        ON customers.id = orders.customer_id
    GROUP BY customers.name
    ORDER BY total_spent DESC
"""

cursor.execute(query)

spending = cursor.fetchall()

for row in spending:
    print(f"  {row[0]:<10} → Total Spent: ₹{row[1]}")

print()
print("✅ All records retrieved successfully from shop.db!")

# Always close the connection when you are finished reading or writing.
conn.close()
