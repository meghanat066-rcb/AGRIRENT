import sqlite3

# Replace 'your_database.db' with your actual filename (e.g., database.db)
conn = sqlite3.connect('database.db') 
cursor = conn.cursor()

try:
    # This adds the missing column to your existing table without deleting data
    cursor.execute("ALTER TABLE feedback ADD COLUMN booking_id INTEGER;")
    conn.commit()
    print("Success! The booking_id column has been added.")
except sqlite3.OperationalError:
    print("The column might already exist, or there is a typo in the table name.")
finally:
    conn.close()