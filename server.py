# pylint: disable=import-error
import socket
import threading
import time
import json
import ssl
import sqlite3
import base64
import bcrypt
import struct
import requests
import os
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32
STORAGE_KEY = os.getenv("CHAT_DB_KEY")
if not STORAGE_KEY:
    raise ValueError("CHAT_DB_KEY environment variable is not set.")
STORAGE_KEY = STORAGE_KEY.encode()

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

def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Socket closed during recv.")
        data += chunk
    return data

def send_packet(sock,text):
    data = text.encode()
    header = struct.pack("!I", len(data))
    sock.sendall(header + data)

def recv_packet(sock):
    header = recv_exact(sock, 4)
    length = struct.unpack("!I", header)[0]
    data = recv_exact(sock, length)
    return data.decode()

def encrypt_at_rest(plaintext):
    """Encrypt private message text before storing it in the database."""
    return encrypt_message(STORAGE_KEY, plaintext)

def decrypt_at_rest(ciphertext):
    """Decrypt private message text after reading it from the database."""
    return decrypt_message(STORAGE_KEY, ciphertext)

# Database password and message history fetching

def load_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, password, salt FROM users")
    rows = cursor.fetchall()
    conn.close()

    users = {}
    for username, password, salt in rows:
        if isinstance(password, str):
            password = password.encode()
        users[username] = (password, salt)
    return users

def init_messages_db():
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT,
            message TEXT NOT NULL,
            msg_type TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def init_groups_db():
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_name TEXT PRIMARY KEY,
            owner TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_name TEXT NOT NULL,
            username TEXT NOT NULL,
            PRIMARY KEY (group_name, username)
        )
    """)

    conn.commit()
    conn.close()

def create_group_db(group_name, owner):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO groups (group_name, owner)
        VALUES (?, ?)
    """, (group_name, owner))

    cursor.execute("""
        INSERT INTO group_members (group_name, username)
        VALUES (?, ?)
    """, (group_name, owner))

    conn.commit()
    conn.close()

def remove_group_member_db(group_name, username):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM group_members
        WHERE group_name = ? AND username = ?
    """, (group_name, username))

    conn.commit()
    conn.close()

def add_group_member_db(group_name, username):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO group_members (group_name, username)
        VALUES (?, ?)
    """, (group_name, username))

    conn.commit()
    conn.close()

def load_groups():
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("SELECT group_name, owner FROM groups")
    group_rows = cursor.fetchall()

    cursor.execute("SELECT group_name, username FROM group_members")
    member_rows = cursor.fetchall()

    conn.close()

    loaded_groups = {}

    for group_name, owner in group_rows:
        loaded_groups[group_name] = {
            "owner": owner,
            "members": set()
        }

    for group_name, username in member_rows:
        if group_name in loaded_groups:
            loaded_groups[group_name]["members"].add(username)

    return loaded_groups

def store_message(sender, recipient, message, msg_type, timestamp):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (sender, recipient, message, msg_type, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (sender, recipient, message, msg_type, timestamp))
    conn.commit()
    conn.close()

def get_recent_messages(username, limit=20):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sender, message, timestamp
        FROM messages
        WHERE msg_type = 'public'
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    rows.reverse()
    return rows

def get_private_convo(user1, user2, limit=20):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender, recipient, message, timestamp
        FROM messages
        WHERE msg_type = 'private'
            AND (
                    (sender = ? AND recipient = ?)
                    OR
                    (sender = ? AND recipient = ?)
            )
        ORDER BY id ASC
        LIMIT ?
    """, (user1, user2, user2, user1, limit))
    rows = cursor.fetchall()
    conn.close()
    decrypted_rows = []
    for sender, recipient, message, timestamp in rows:
        decrypted_message = decrypt_at_rest(message)
        decrypted_rows.append((sender, recipient, decrypted_message, timestamp))
    return decrypted_rows

def get_group_messages(group_name, limit=20):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sender, recipient, message, timestamp
        FROM messages
        WHERE msg_type = 'group' AND recipient = ?
        ORDER BY id ASC
        LIMIT ?
    """, (group_name, limit))

    rows = cursor.fetchall()
    conn.close()

    decrypted_rows = []
    for sender, recipient, message, timestamp in rows:
        decrypted_message = decrypt_at_rest(message)
        decrypted_rows.append((sender, recipient, decrypted_message, timestamp))

    return decrypted_rows

VALID_USERS = load_users()
init_messages_db()
init_groups_db()
active_users = set()
connected_clients = []
user_sockets = {}
user_session_keys = {}
groups = load_groups()
pending_group_requests = {}

print("Server running with Port 5000...")
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.minimum_version = ssl.TLSVersion.TLSv1_2
if hasattr(ssl, "OP_NO_COMPRESSION"):
    context.options |= ssl.OP_NO_COMPRESSION
context.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("localhost", 5000))
server.listen(5)
server = context.wrap_socket(server, server_side=True)

def load_system_prompt():
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"System prompt load error: {e}")
        return "You are Artemis, a helpful AI assistant."

def ai_response(prompt):
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return ("Artemis error: API key not set.")

    system_prompt = load_system_prompt()

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
    
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "meta-llama/llama-3.2-3b-instruct:free",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 150
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")

        if isinstance(content, str) and content.strip():
            return content.strip()

        return "Artemis is thinking, but no visible reply was returned."

        if content is None:
            return f"Artemis error: unexpected API response: {data}"
        return content.strip()
    except Exception as e:
        return f"Artemis error: {e}"

def cleanup_user(username, conn):
    active_users.discard(username)

    if conn in connected_clients:
        connected_clients.remove(conn)
         
    if username in user_sockets:
        del user_sockets[username]

    user_session_keys.pop(username, None)
    
    groups_to_delete = []
    
    for group_name, group_data in groups.items():
        if username in group_data["members"]:
            group_data["members"].remove(username)
            
            if group_data["owner"] == username:
                groups_to_delete.append(group_name)
            elif not group_data["members"]:
                groups_to_delete.append(group_name)
    for group_name in groups_to_delete:
        del groups[group_name]
    

def handle_client(conn, addr):
    print(f"Client connected with address{addr}.")

        # Authentication
    attempts = 0
    while attempts < 5:
        try:
            username = recv_packet(conn).strip()
            if not username or not VALID_USERS.get(username):
                send_packet(conn, "INVALID_USER")
                continue


                # Credentials
            stored = VALID_USERS.get(username)
            if stored:
                _, salt_hex = stored
                send_packet(conn, salt_hex)
            else:
                send_packet(conn, get_random_bytes(16).hex())
            password = recv_packet(conn).strip()

            if username in active_users:
                print(f"[DENIED] {username} attempted second login.")
                send_packet(conn, "Authentication failed.")
                attempts+= 1
                continue
            if not username or not stored:
                send_packet(conn, "Invalid username or password.")
                continue

            stored_hash, salt_hex = stored
            salt = bytes.fromhex(salt_hex)

            if bcrypt.checkpw(password.encode(), stored_hash):
                session_key = derive_key(password.encode(), salt)
                user_session_keys[username] = session_key
                encrypted = encrypt_message(session_key, "Verified.")
                send_packet(conn, encrypted)
                print(f"User '{username}' authenticated successfully.")
                active_users.add(username)
                connected_clients.append(conn)
                user_sockets[username] = conn
                history_rows = get_recent_messages(username)
                if history_rows:
                    history_lines = ["---Global Chat History ---"]
                    for sender, msg, timestamp in history_rows:
                        history_lines.append(f"[{timestamp}] {sender}: {msg}")

                    history_text = "\n".join(history_lines)
                    encrypted_history = encrypt_message(session_key, history_text)
                    send_packet(conn, encrypted_history)
                break

            send_packet(conn, "Invalid username or password.")
            print(f"Authentication failed for user '{username}'.")
            attempts += 1


        except Exception as e:
            print(f"Authentication error: {e}")
            conn.close()
            return

    if attempts >= 5:
        send_packet(conn, "Too many attempts.")
        conn.close()
        return

      # Messaging / Disconnection

    try:
        def receive_message():
            while True:
                try:
                    raw = recv_packet(conn)
                except ConnectionError:
                    print("Client disconnected.")
                    cleanup_user(username, conn)
                    break
	   # Commands
                message = decrypt_message(session_key, raw)
                raw_message = message.split("[", 1)[0].strip()

                if username in pending_group_requests:
                    lowered = raw_message.lower()

                    if lowered == "yes":
                        request = pending_group_requests[username]
                        group_name = request["group"]
                        inviter = request["inviter"]

                        if group_name in groups:
                            groups[group_name]["members"].add(username)
							add_group_member_db(group_name, username)
                            encrypted = encrypt_message(session_key, f"You joined group '{group_name}'.")
                            send_packet(conn, encrypted)

                            if inviter in user_sockets:
                                inviter_conn = user_sockets[inviter]
                                inviter_key = user_session_keys[inviter]
                                notice = f"{username} accepted your request to join '{group_name}'."
                                encrypted_notice = encrypt_message(inviter_key, notice)
                                send_packet(inviter_conn, encrypted_notice)
                            else:
                                encrypted = encrypt_message(session_key, f"Group '{group_name}' no longer exists.")
                                send_packet(conn, encrypted)
                            del pending_group_requests[username]
                            continue
                    elif lowered== "no":
                        request = pending_group_requests[username]
                        group_name = request["group"]
                        inviter = request["inviter"]
                        encrypted = encrypt_message(session_key, f"You declinded the invite to '{group_name}'.")
                        send_packet(conn, encrypted)
                        if inviter in user_sockets:
	
                            inviter_conn = user_sockets[inviter]
                            inviter_key = user_session_keys[inviter]
                            notice = f"{username} declined your request to join '{group_name}'."
                            encrypted_notice = encrypt_message(inviter_key, notice)
                            send_packet(inviter_conn, encrypted_notice)

                        del pending_group_requests[username]
                        continue

                if len(raw_message) > 256:
                    encrypted = encrypt_message(session_key, "Message exceeds max characters.")
                    send_packet(conn, encrypted)
                    continue

                if raw_message == "/who":
                    if active_users:
                        online = ", ".join(active_users)
                        response = f"Online users: {online}"
                        encrypted = encrypt_message(session_key, response)
                        send_packet(conn, encrypted)
                    else:
                        response = "No users online."
                        encrypted = encrypt_message(session_key, response)
                        send_packet(conn, encrypted)
                    continue

                     #Help menu
                if raw_message == "/help":
                    help_text = (
                        "--- Available Commands ---\n"
                        "/msg <user> <message> - Private message\n"
                        "/who - List online users\n"
                        "/help - Shows command menu\n"
                        "/exit - Disconnect\n"
                        "/history <user> - Shows private conversation history\n"
                        "@ai <question> - Conversate with Artemis AI\n"
                        "/group_create <group_name> - Create a group\n"
                        "/group_add <group_name> <user> - Add user to your group\n"
                        "/gmsg <group_name> <message> - Send message to group\n"
                        "/groups - List your groups\n"
                        "/group_leave <group_name> - Leave a group\n"
                    )
                    encrypted = encrypt_message(session_key, help_text)
                    send_packet(conn, encrypted)
                    continue

                    # Private messages
                if raw_message.startswith("/msg "):
                    parts = raw_message.split(" ", 2)
                    if len(parts) < 3:
                        sender_key = user_session_keys[username]
                        encrypted = encrypt_message(sender_key, "Usage: /msg <user> <message>")
                        send_packet(conn, encrypted)
                        continue

                    target_user = parts[1]
                    private_text = raw_message.split(" ", 2)[2]

                    if target_user not in user_sockets:
                        sender_key = user_session_keys[username]
                        encrypted = encrypt_message(sender_key, f"User {target_user} not online.")
                        send_packet(conn, encrypted)
                        continue

                    target_conn = user_sockets[target_user]

                    try:
                        target_conn = user_sockets[target_user]

                        target_key = user_session_keys[target_user]
                        sender_key = user_session_keys[username]

                        timestamp = time.strftime("%Y-%m-%d %I:%M:%S %p")
                        encrypted_private = encrypt_at_rest(private_text)
                        store_message(username, target_user, encrypted_private, "private", timestamp)
                        conversation_rows = get_private_convo(username, target_user)
                        history_lines= [f"--- Private Conversation with {target_user} ---"]
                        for sender, recipient, msg, timestamp in conversation_rows:
                            history_lines.append(f"[{timestamp}] {sender}: {msg}")
                        conversation_text = "\n".join(history_lines)

                        msg_to_target = f"[Private] {username}: {private_text}"

                        encrypted_target = encrypt_message(target_key, msg_to_target)
                        encrypted_sender = encrypt_message(sender_key, conversation_text)

                        send_packet(target_conn, encrypted_target)
                        send_packet(conn, encrypted_sender)
                    except Exception as e:
                        print(f"Private message error: {e}")
                        sender_key = user_session_keys[username]
                        encrypted = encrypt_message(sender_key, "Error delivering private message.")
                        send_packet(conn, encrypted)
                    continue

                if raw_message.startswith("/history "):
                    parts = raw_message.split(" ", 1)
                    if len(parts) < 2 or not parts[1].strip():
                        encrypted = encrypt_message(session_key, "Usage: /history <user>")
                        send_packet(conn, encrypted)
                        continue
                    target_user = parts[1].strip()
                    conversation_rows = get_private_convo(username, target_user)
                    if not conversation_rows:
                        encrypted = encrypt_message(session_key, f"No private conversation history with {target_user}.")
                        send_packet(conn, encrypted)
                        continue
                    history_lines = [f"--- Private conversation with {target_user} ---"]
                    for sender, recipient, msg, timestamp in conversation_rows:
                        history_lines.append(f"[{timestamp}] {sender}: {msg}")

                    history_text = "\n".join(history_lines)
                    encrypted = encrypt_message(session_key, history_text)
                    send_packet(conn, encrypted)
                    continue

                if raw_message.startswith("/group_create "):
                    parts = raw_message.split(" ", 1)

                    if len(parts) < 2 or not parts[1].strip():
                        encrypted = encrypt_message(session_key, "Usage: /group_create <group_name>")
                        send_packet(conn, encrypted)
                        continue
                    group_name = parts[1].strip()

                    if group_name in groups:
                        encrypted = encrypt_message(session_key, f"Group '{group_name}' already exists.")
                        send_packet(conn, encrypted)
                        continue

                    groups[group_name] = {
                        "owner": username,
                        "members": {username}
                    }
					create_group_db(group_name, username)

                    encrypted = encrypt_message(session_key, f"Group '{group_name}' created.")
                    send_packet(conn, encrypted)
                    continue

                if raw_message == "/group_add" or raw_message.startswith("/group_add "):
                    parts = raw_message.split(" ", 2)

                    if len(parts) < 3 or not parts[1].strip() or not parts[2].strip():
                        encrypted = encrypt_message(session_key, "Usage: /group_add <group_name> <user>")
                        send_packet(conn, encrypted)
                        continue

                    group_name = parts[1].strip()
                    target_user = parts[2].strip()

                    if group_name not in groups:
                        encrypted = encrypt_message(session_key, f"Group '{group_name}' does not exist.")
                        send_packet(conn, encrypted)
                        continue

                    group = groups[group_name]

                    if group["owner"] != username:
                        encrypted = encrypt_message(session_key, "Only the group owner can add members.")
                        send_packet(conn, encrypted)
                        continue

                    if target_user not in VALID_USERS:
                        encrypted = encrypt_message(session_key, f"User '{target_user}' does not exist.")
                        send_packet(conn, encrypted)
                        continue

                    if target_user in group["members"]:
                        encrypted = encrypt_message(session_key, f"User '{target_user}' is already in '{group_name}'.")
                        send_packet(conn, encrypted)
                        continue

                    if target_user in pending_group_requests:
                        encrypted = encrypt_message(session_key, f"User '{target_user}' already has a pending request.")
                        send_packet(conn, encrypted)
                        continue

                    pending_group_requests[target_user] = {
                        "group": group_name,
                        "inviter": username
                    }
                    encrypted = encrypt_message(session_key, f"Join request sent to '{target_user}'.")
                    send_packet(conn, encrypted)

                    target_conn = user_sockets[target_user]
                    target_key = user_session_keys[target_user]

                    notice = (
                        f"{username} wants to add you to a group called '{group_name}'.\n"
                        f"Reply with YES or NO."
                    )
                    encrypted_notice = encrypt_message(target_key, notice)
                    send_packet(target_conn, encrypted_notice)
                    continue

                if raw_message == "/groups":
                    user_groups = []
                    for group_name, group_data in groups.items():
                        if username in group_data["members"]:
                            role = "owner" if group_data["owner"] == username else "member"
                            user_groups.append(f"{group_name} ({role})")
                    if not user_groups:
                        encrypted = encrypt_message(session_key, "You are not in any groups.")
                        send_packet(conn, encrypted)
                        continue

                    response = "--- Your Groups ---\n" + "\n".join(user_groups)
                    encrypted = encrypt_message(session_key, response)
                    send_packet(conn, encrypted)
                    continue

                if raw_message.startswith("/group_leave "):
                    parts = raw_message.split(" ", 1)

                    if len(parts) < 2 or not parts[1].strip():
                        encrypted = encrypt_message(session_key, "Usage: /group_leave <group_name>")
                        send_packet(conn, encrypted)
                        continue

                    group_name = parts[1].strip()

                    if group_name not in groups:
                        encrypted = encrypt_message(session_key, f"Group '{group_name}' does not exist.")
                        send_packet(conn, encrypted)
                        continue
                        
                    group = groups[group_name]

                    if username not in group["members"]:
                        encrypted = encrypt_message(session_key, f"You are not a member of '{group_name}'.")
                        send_packet(conn, encrypted)
                        continue

                    if group["owner"] == username:
                        del groups[group_name]
                        encrypted = encrypt_message(session_key, f"You were the owner. Group '{group_name}' was deleted.")
                        send_packet(conn, encrypted)
                        continue

                    group["members"].remove(username)
					remove_group_member_db(group_name, username)
                    encrypted = encrypt_message(session_key, f"You left group '{group_name}'.")
                    send_packet(conn, encrypted)
                    continue

                if raw_message.startswith("/gmsg "):
                    parts = raw_message.split(" ", 2)

                    if len(parts) < 3:
                       encrypted = encrypt_message(session_key, "Usage: /gmsg <group_name> <message>")
                       send_packet(conn, encrypted)
                       continue

                    group_name = parts[1].strip()
                    group_text = parts[2].strip()

                    if not group_text:
                        encrypted = encrypt_message(session_key, "Group message cannot be empty.")
                        send_packet(conn, encrypted)
                        continue

                    if group_name not in groups:
                        encrypted = encrypt_message(session_key, f"Group '{group_name}' does not exist.")
                        send_packet(conn, encrypted)
                        continue

                    group = groups[group_name]

                    if username not in group["members"]:
                        encrypted = encrypt_message(session_key, f"You are not member of '{group_name}'.")
                        send_packet(conn, encrypted)
                        continue

                    timestamp = time.strftime("%Y-%m-%d %I:%M:%S %p")
					encrypted_group_text = encrypt_at_rest(group_text)
					store_message(username, group_name, encrypted_group_text, "group", timestamp)
					outbound = f"[Group:{group_name}] [{timestamp}] {username}: {group_text}"

                    for member in group["members"]:
                        if member in user_sockets:
                            member_conn = user_sockets[member]
                            member_key = user_session_keys[member]
                            encrypted_group_msg = encrypt_message(member_key, outbound)
                            send_packet(member_conn, encrypted_group_msg)
                    continue

				if raw_message.startswith("/group_history "):
    parts = raw_message.split(" ", 1)

    if len(parts) < 2 or not parts[1].strip():
        encrypted = encrypt_message(session_key, "Usage: /group_history <group_name>")
        send_packet(conn, encrypted)
        continue

    group_name = parts[1].strip()

    if group_name not in groups:
        encrypted = encrypt_message(session_key, f"Group '{group_name}' does not exist.")
        send_packet(conn, encrypted)
        continue

    if username not in groups[group_name]["members"]:
        encrypted = encrypt_message(session_key, f"You are not a member of '{group_name}'.")
        send_packet(conn, encrypted)
        continue

    group_rows = get_group_messages(group_name)

    if not group_rows:
        encrypted = encrypt_message(session_key, f"No group history found for '{group_name}'.")
        send_packet(conn, encrypted)
        continue

    history_lines = [f"--- Group History: {group_name} ---"]
    for sender, recipient, msg, timestamp in group_rows:
        history_lines.append(f"[{timestamp}] {sender}: {msg}")

    history_text = "\n".join(history_lines)
    encrypted = encrypt_message(session_key, history_text)
    send_packet(conn, encrypted)
    continue

                if raw_message.startswith("@ai "):
                    prompt = raw_message[len("@ai "):].strip()
                    if not prompt:
                        encrypted = encrypt_message(session_key, "Usage: @ai <question>")
                        send_packet(conn, encrypted)
                        continue
                    try:        
                        ai_reply = ai_response(prompt)
                        encrypted = encrypt_message(session_key, f"Artemis: {ai_reply}")
                        send_packet(conn, encrypted)
                    except Exception as e:
                        print(f"AI error: {e}")
                        encrypted = encrypt_message(
                            session_key, "Artemis is unavailable right now. Please try again later."
                        )
                        send_packet(conn, encrypted)
                    continue

                if raw_message == "/exit":
                    print("Client requested disconnect.")
                    cleanup_user(username, conn)
                    conn.close()
                    break

                print(f"{username}: {message}")
                timestamp = time.strftime("%Y-%m-%d %I:%M:%S %p")
                store_message(username, None, raw_message, "public", timestamp)

        threading.Thread(target=receive_message, daemon=True).start()

        time.sleep(1)

    except Exception as e:
        print(f"Error with data transfer: {e}")

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
