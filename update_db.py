import sqlite3

def upgrade_database():
    conn = sqlite3.connect('database.db') # Use your actual database name
    cursor = conn.cursor()
    
    try:
        # Add the hourly price column
        cursor.execute('ALTER TABLE equipment ADD COLUMN price_per_hour REAL DEFAULT 0.0')
        
        # Add the return time column for the 1-hour gap
        cursor.execute('ALTER TABLE bookings ADD COLUMN return_time DATETIME')
        
        conn.commit()
        print("Database updated successfully!")
    except sqlite3.OperationalError:
        print("Columns might already exist.")
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_database()