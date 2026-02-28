# Chat Program

A python based chat application designed to demonstrate real networking, authentication, and database concepts. It began as a simple socket demo and evolved into a multi client system with secure login, session management, and a SQLite credential store.

# Overview

The program consists of two components:

1. server.py
Handles incoming client connections, authenticates users, and manages message routing. Runs continuously until stopped.
2. client.py
Connects to the server and sends messages over a TCP socket.


# How It Works
1. Startup
Binds to local:5000
Loads users from users.db
Waits for incoming connections
Spawns a new thread for each client

2. Authentication
Client sends username and password
Server validates credentials against SQLite
Responds with Verified on success
Responds with Invalid username or password on failure


4. Messaging
Once authenticated, the client can send messages to the server in a global fashion. However, there is private messaging aswell.


# Running the Program

Open two terminals:
## Terminal 1 - Start the server

python3 server.py

## Terminal 2 - Start the client

python3 client.py

Type messages into the client terminal to send them to the server. The server can also send messages back.

# Upcoming
1. Password hashing (bcrypt)
2. Private chats
3. Group chat rooms
4. Messaging route per user
5. Cleaner client UI

# Purpose

This project was built to practice real world networking and security. It focuses on socket programming, multi-client handling, authentication flows, and clean message routing.

# What I Learned

1. How to build multi client server using threads
2. How to design a simple authentication flow backed by SQLite
3. How to structure message handling for future private routing
4. How to seperate ckient/server responsibilities cleanly
5. How to think about security early (hashing, lockouts, session management)
