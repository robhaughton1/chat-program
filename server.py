import socket
import threading
import time
import sqlite3

# Database user fetching

def load_users():
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT username, password FROM users")
        rows = cursor.fetchall()
        conn.close()
        return {username: password for username, password in rows}
        
VALID_USERS = load_users()
        
active_users = set()


print("Server running with Port 5000...")
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("localhost", 5000))
server.listen(1)

def handle_client(conn, addr):
        print(f"Client connected with address{addr}.")
        
        # Authentication
        attempts = 0
        while attempts < 5:

                try:

                        username = conn.recv(1024).decode().strip()
                        password = conn.recv(1024).decode().strip()
                
                # Duplicate session prevention
                
                        if username in active_users:
                                conn.send("Authentication failed".encode())
                                print(f"[DENIED] {username} attempted second login.")
                                attempts+= 1
                                continue
        
                # Credentials
                        if username in VALID_USERS and VALID_USERS[username] == password:
                                conn.send("Verified.".encode())
                                print(f"User '{username}' authenticated successfully.")
                                active_users.add(username)
                                break
                        else:
                                conn.send("Invalid username or password.".encode())
                                print(f"Authentication failed for user '{username}'.")
                                attempts += 1
                        
                        
                except Exception as e:
                        print(f"Authentication error: {e}")
                        conn.close()
                        return
             
        if attempts >= 5:
                conn.send("Too many attempts.".encode())
                conn.close()
                return
             
      # Messaging / Disconnection

        try:
             
                def receive_message():
                
                        while True:
                                data = conn.recv(1024)
                                if not data:
                                        print("Client disconnected.")
                                        active_users.discard(username)
                                        break
	   
                                message = data.decode(errors="replace")
                                if message.lower() == "exit":
                                        print("Client requested disconnect.")
                                        active_users.discard(username)
                                        break
	    
                                print(f"{username}: {message}")
                                
                                conn.send(f"Server received: {message}".encode())
                                
                def send_messages():
                        while True:
                                server_msg = input("")
                                conn.send(server_msg.encode())
                threading.Thread(target=receive_message, daemon=True).start()
                threading.Thread(target=send_messages, daemon=True).start()
                
                while True:
                        time.sleep(1)
                        
        except Exception as e:
                   print(f"Error with data transfer: {e}")

while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

	    
