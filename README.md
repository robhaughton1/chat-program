# Chat Program

This project is a python based chat application designed to demonstrate real networking, authentication, and database concepts. It began as a simple socket demo and evolved into a multi client system with secure login, session management, and a real SQLite credential store.

# Overview

The program consists of two components:

1. server.py
The server listens for incoming client connections, accepts the messages, and prints them in the terminal. It remains running until stopped.

2. client.py
The client connects to the server and allows the user to send messages. Each message is transmitted over a TCP socket to the server.


# How It Works
1. Startup
Binds to local:5000
Loads users from users.db
Waits for incoming connections
Spawns a new thread for each client

2. Authentication
Client sends username and password. Tbe server checks the SQLite database and responds with a Verified on success, and Invalid username or password on failure. After 5 attempts, it responds with Too many attempts.

3. Messaging
Once authenticated, the client can send messages to the server.
(Currently group chat; private chat routing coming soon.)

# Running the Program

Open two terminals:
## Terminal 1 - Start the server

python3 server.py

## Terminal 2 - Start the client

python3 client.py

Type messages into the client terminal to send them to the server.

# Upcoming
Password hashing (bcrypt)
Private chats
Group chat rooms
Messaging route per user
Cleaner client UI
