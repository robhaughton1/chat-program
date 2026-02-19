import socket
import threading
import time
import sqlite3
import bcrypt

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

connected_clients = []

user_sockets = {}


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
                
                        stored_hash = VALID_USERS.get(username)
                        
                        if stored_hash and bcrypt.checkpw(password.encode(), stored_hash):
                                conn.send("Verified.".encode())
                                print(f"User '{username}' authenticated successfully.")
                                active_users.add(username)
                                connected_clients.append(conn)
                                user_sockets[username] = conn
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
                                        if conn in connected_clients:
                                                connected_clients.remove(conn)
                                        if username in user_sockets:
                                                del user_sockets[username]
                                        break
	   # Users online
                                message = data.decode(errors="replace")
                                
                                raw_message = message.split("[", 1)[0].strip()
                               
                                if raw_message == "/who":
                                        if active_users:
                                                online = ", ".join(active_users)
                                                conn.send(f"Online users: {online}".encode())
                                        else:
                                                conn.send("No users online.".encode())
                                        continue
                                        
                         # Help menue               
                                if raw_message == "/help":
                                        help_text = (
                                                "Available commands:\n"
                                                "/msg <user> <message - Private message\n"
                                                "/who - List online users\n"
                                                "/help - Shows command menu\n"
                                                "/exit - Disconnect"
                                        )
                                        conn.send(help_text.encode())
                                        continue
                                        
                            # Private messages    
                                if raw_message.startswith("/msg "):
                                        parts = raw_message.split(" ", 2)
                                        if len(parts) < 3:
                                                conn.send("Usage: /msg <user> <message>".encode())
                                                continue
                                        
                                        target_user = parts[1]
                                        private_text = message.split(" ", 2)[2]
                                        
                                        if target_user not in user_sockets:
                                                conn.send(f"User {target_user} is not online.".encode())
                                                continue
                                        target_conn = user_sockets[target_user]
                                        
                                        try: 
                                                target_conn.send(f"[Private] {username}: {private_text}".encode())
                                                conn.send(f"[Private to {target_user}] {private_text}".encode())
                                        except:
                                                conn.send("Error delivering private message.".encode())
                                        continue
                                        
                                        
                                if message.lower() == "exit":
                                        print("Client requested disconnect.")
                                        active_users.discard(username)
                                        break
	    
                                print(f"{username}: {message}")
                                
                                conn.send(f"Server received: {message}".encode())
                                
                threading.Thread(target=receive_message, daemon=True).start()
                               
                while True:
                        time.sleep(1)
                     
                        
        except Exception as e:
                   print(f"Error with data transfer: {e}")
                   
def server_broadcast():
        global connected_clients
        while True:
                msg = input('')
                for client in connected_clients:
                        try:
                                client.send(msg.encode())
                        except:
                                connected_clients.remove(client)
threading.Thread(target=server_broadcast, daemon=True).start()

while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

	    
