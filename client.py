# pylint: disable=import-error
"""Encrypted chat client for secure messaging."""
import socket
from datetime import datetime
import time
import ssl
import threading
import base64
import sys
import struct
from getpass import getpass
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32

WAITING_FOR_AI = False

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

def receive_from_server(session_key):
    """Background thread that receives and decrypts messages from the server."""
    global WAITING_FOR_AI
    while True:
        try:
            ciphertext = recv_packet(client)
            if not ciphertext:
                print("Server disconnected.")
                sys.exit()
            plaintext = decrypt_message(session_key, ciphertext)
            print(f"\n{plaintext}")
            if plaintext.startswith("Artemis: "):
                WAITING_FOR_AI = False
        except (KeyError, TypeError, ValueError) as e:
            print(f"Receive thread error: {e}")
            break

context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
context.minimum_version = ssl.TLSVersion.TLSv1_2
if hasattr(ssl, "OP_NO_COMPRESSION"):
    context.options |= ssl.OP_NO_COMPRESSION
context.check_hostname = True
context.load_verify_locations("cert.pem")
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # IPv4 and TCP insertion
client = context.wrap_socket(client, server_hostname="localhost")

try:
    client.connect(("localhost", 5000)) # Port and host binding
    print("Please log in.\n")

# Authentication
    ATTEMPTS = 0
    MAX_ATTEMPTS = 5

    while ATTEMPTS < MAX_ATTEMPTS:
        username = input("Username: ").strip()
        if not username:
            print("Username cannot be empty.")
            time.sleep(1)
            continue
        while True:
            password = getpass("Password: ").strip()
            if not password:
                print("Password cannot be empty.")
                time.sleep(1)
                continue
            break
        send_packet(client, username)
        salt_hex = recv_packet(client).strip()
        if salt_hex == "INVALID_USER":
            print("Invalid username or password.")
            continue
        salt = bytes.fromhex(salt_hex)
        session_key = derive_key(password.encode(), salt)
        time.sleep(0.1)
        send_packet(client, password)
        ciphertext = recv_packet(client)

        try:
            response = decrypt_message(session_key, ciphertext)
        except Exception: # pylint: disable=broad-exception-caught
            response = ciphertext

        if "Verified" in response:
            time.sleep(0.5)
            print("Type /help for commands.\n")
            time.sleep(0.2)
            print(f"Welcome, {username}!")
            threading.Thread(target=receive_from_server, args=(session_key,), daemon=True).start()

            break

        ATTEMPTS += 1
        print("Invalid username or password.")

        if ATTEMPTS >= MAX_ATTEMPTS:
            print("Too many failed attempts. Closing connection...")
            client.close()
            sys.exit()
# Messaging
    while True:
        while True:
            time.sleep(1)

            if WAITING_FOR_AI:
                print("Waiting for Artemis to respond...")
                time.sleep(1)
                continue

            message = input("Enter your message: ").strip() # User input text

            if message.startswith("@ai"):
                if message.strip() == "@ai":
                    print("usage: @ai <question>")
                    time.sleep(1)
                    continue
                WAITING_FOR_AI = True

            if message.lower() == "/exit":
                encrypted = encrypt_message(session_key, "/exit")
                send_packet(client, encrypted)
                print("Closing connection...")
                client.close()
                sys.exit()

            if not message:
                print("Message cannot be empty.") # Basic input validation
                time.sleep(2)
                continue


            if len(message) > 256:
                print("Message exceeds max characters.") # Rate limit check
                time.sleep(2)
                continue



            break

        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p") # Date formatting

        COMMANDS = ["/msg", "/who", "/help", "/exit", "/history", "@ai", "/group_create", "/group_add", "/gmsg", "/groups", "/group_leave", "/group_history"]

        is_command = any(message.startswith(cmd) for cmd in COMMANDS)

        full_message = f"{message} [{timestamp}]" # Message formatting

        encrypted = encrypt_message(session_key, full_message)
        send_packet(client, encrypted)

        if not is_command:
            print("Message sent to server.")

except (KeyError, ValueError, TypeError) as e:

    print(f"Error connecting or sending: {e}")
client.close()
