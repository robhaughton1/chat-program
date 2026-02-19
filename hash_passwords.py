import sqlite3
import bcrypt

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("SELECT username, password FROm users")
rows = cursor.fetchall()

for username, plaintext_password in rows:
        print(f"Hashing password for user: {username}")
        
        hashed = bcrypt.hashpw(plaintext_password.encode(), bcrypt.gensalt())
        
        cursor.execute(
                "UPDATE users SET password = ? WHERE username = ?",
                (hashed, username)
                
        )

conn.commit()
conn.close()

print("Hashing complete.")
