import sqlite3 
import bcrypt

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

users = [
        
        ("Robert", "password123"),
        ("Grandma", "abc123")
]


for username, plaintext in users:
        hashed = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt())
        cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)", 
                (username, hashed)
        )
        print(f"Added user: {username}")
        
conn.commit()
conn.close()

print("All users added with hashed passwords.")
 
