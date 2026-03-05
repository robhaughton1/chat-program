# pylint: disable=import-error
import socket
import threading
import time
import sqlite3
import base64
import bcrypt
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32

def derive_key(password, salt):
    """Derive a 32-byte AES key from the given password."""
    return PBKDF2(password, salt, dkLen=KEY_LENGTH, count=PBKDF2_ITERATIONS)

def encrypt_message(key, plaintext):
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
    return base64.b64encode(cipher.nonce + tag + ciphertext).decode()

def decrypt_message(key, b64_ciphertext):
    raw = base64.b64decode(b64_ciphertext.encode())
    nonce = raw[:16]
    tag = raw[16:32]
    ciphertext = raw[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag).decode()

# Database user fetching

def load_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, password, salt FROM users")
    rows = cursor.fetchall()
    conn.close()
    return {username: (password, salt) for username, password, salt in rows}

VALID_USERS = load_users()
active_users = set()
connected_clients = []
user_sockets = {}
user_session_keys = {}

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
            if not username or not VALID_USERS.get(username):
                conn.send("INVALID_USER".encode())
                continue


                # Credentials
            stored = VALID_USERS.get(username)
            if stored:
                _, salt_hex = stored
                conn.send(salt_hex.encode())
            else:
                conn.send(get_random_bytes(16).hex().encode())
            password = conn.recv(1024).decode().strip()

            if username in active_users:
                print(f"[DENIED] {username} attempted second login.")
                conn.send("Authentication failed.".encode())
                attempts+= 1
                continue
            if not username or not stored:
                conn.send("invalid username or password.".encode())
                continue

            stored_hash, salt_hex = stored
            salt = bytes.fromhex(salt_hex)

            if bcrypt.checkpw(password.encode(), stored_hash):
                session_key = derive_key(password.encode(), salt)
                user_session_keys[username] = session_key
                encrypted = encrypt_message(session_key, "Verified.")
                conn.send(encrypted.encode())
                print(f"User '{username}' authenticated successfully.")
                active_users.add(username)
                connected_clients.append(conn)
                user_sockets[username] = conn
                break

            conn.send("Invalid username or password.".encode())
            print(f"Authentication failed for user '{username}'.")
            attempts += 1


        except Exception as e:
            print(f"Authentication error: {e}")
            conn.close()
            return

    if attempts >= 5:
        conn.send("too many attempts.".encode())
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
                raw = data.decode(errors="replace")
                message = decrypt_message(session_key, raw)
                raw_message = message.split("[", 1)[0].strip()

                if raw_message == "/who":
                    if active_users:
                        online = ", ".join(active_users)
                        response = f"Online users: {online}"
                        encrypted = encrypt_message(session_key, response)
                        conn.send(encrypted.encode())
                    else:
                        response = "No users online."
                        encrypted = encrypt_message(session_key, response)
                        conn.send(encrypted.encode())
                    continue

                     #Help menu
                if raw_message == "/help":
                    help_text = (
                        "Available commands:\n"
                        "/msg <user> <message - Private message\n"
                        "/who - List online users\n"
                        "/help - Shows command menu\n"
                        "/exit - Disconnect"
                    )
                    encrypted = encrypt_message(session_key, help_text)
                    conn.send(encrypted.encode())
                    continue

                    # Private messages
                if raw_message.startswith("/msg "):
                    parts = raw_message.split(" ", 2)
                    if len(parts) < 3:
                        sender_key = user_session_keys[username]
                        encrypted = encrypt_message(sender_key, "Usage: /msg <user> <message>")
                        conn.send(encrypted.encode())
                        continue

                    target_user = parts[1]
                    private_text = message.split(" ", 2)[2]

                    if target_user not in user_sockets:
                        sender_key = user_session_keys[username]
                        encrypted = encrypt_message(sender_key, f"User {target_user} not online.")
                        conn.send(encrypted.encode())
                        continue

                    target_conn = user_sockets[target_user]

                    try:
                        target_conn = user_sockets[target_user]

                        target_key = user_session_keys[target_user]
                        sender_key = user_session_keys[username]

                        msg_to_target = f"[Private] {username}: {private_text}"
                        msg_to_sender = f"[Private to {target_user}] {private_text}"

                        encrypted_target = encrypt_message(target_key, msg_to_target)
                        encrypted_sender = encrypt_message(sender_key, msg_to_sender)

                        target_conn.send(encrypted_target.encode())
                        conn.send(encrypted_sender.encode())
                    except:
                        sender_key = user_session_keys[username]
                        encrypted = encrypt_message(sender_key, "Error delivering private message.")
                        conn.send(encrypted.encode())
                    continue

                if raw_message == "/exit":
                    print("Client requested disconnect.")
                    active_users.discard(username)
                    break

                print(f"{username}: {message}")

                response = f"Server received: {message}"
                encrypted = encrypt_message(session_key, response)
                conn.send(encrypted.encode())

        threading.Thread(target=receive_message, daemon=True).start()

        while True:
            time.sleep(1)

    except Exception as e:
        print(f"Error with data transfer: {e}")

def server_broadcast():
    while True:
        msg = input('')
        for client in connected_clients:
            try:
                key = user_session_keys.get(username)
                if not key:
                    continue
                encrypted = encrypt_message(key, msg)
                client.send(encrypted.encode())
            except:
                connected_clients.remove(client)
                user_sockets.pop(username, None)
                user_session_keys.pop(username, None)

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
