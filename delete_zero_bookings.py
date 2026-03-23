import sqlite3
conn = sqlite3.connect('database.db')
# This specifically removes the booking that is causing the layout issue
conn.execute("DELETE FROM bookings WHERE total_price = 0.0")
conn.commit()
conn.close()
print("Incorrect booking deleted. You can now redo the process.")