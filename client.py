# pylint: disable=import-error
"""Encrypted chat client for secure messaging."""
import socket
from datetime import datetime
import time
import ssl
import threading
import base64
import sys
from getpass import getpass
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

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

def receive_from_server(session_key):
    """Background thread that receives and decrypts messages from the server."""
    while True:
        try:
            data = client.recv(1024)
            if not data:
                print("Server disconnected.")
                sys.exit()
            ciphertext = data.decode(errors="replace")
            plaintext = decrypt_message(session_key, ciphertext)
            print(f"\nServer: {plaintext}")
        except Exception: # pylint: disable=broad-exception-caught
            break

context = ssl.create_default_context()
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
        client.send(username.encode())
        salt_hex = client.recv(1024).decode().strip()
        if salt_hex == "INVALID_USER":
            print("Invalid username or password.")
            continue
        salt = bytes.fromhex(salt_hex)
        session_key = derive_key(password.encode(), salt)
        time.sleep(0.1)
        client.send(password.encode())
        ciphertext = client.recv(1024).decode()

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
        print(f"Authentication failed; {MAX_ATTEMPTS - ATTEMPTS} left.")

        if ATTEMPTS >= MAX_ATTEMPTS:
            print("Too many failed attempts. Closing connection...")
            client.close()
            sys.exit()
# Messaging
    while True:
        while True:
            time.sleep(1)
            message = input("Enter your message: ").strip() # User input text

            if message.lower() == "/exit":
                encrypted = encrypt_message(session_key, "/exit")
                client.send(encrypted.encode())
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

        COMMANDS = ["/msg", "/who", "/help", "/exit"]

        is_command = any(message.startswith(cmd) for cmd in COMMANDS)

        full_message = f"{message} [{timestamp}]" # Message formatting

        encrypted = encrypt_message(session_key, full_message)
        client.send(encrypted.encode())

        if not is_command:
            print("Message sent to server.")

except Exception as e: # pylint: disable=broad-exception-caught

    print(f"Error connecting or sending: {e}")
client.close()
