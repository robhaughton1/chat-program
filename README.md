# Chat Program

A simple two file python chat app that deomstrates the basics of client-server communication using sockets. This project was built as part of my coursework to practice networking fundamentals.

# Overview

The program consists of two components:

1. server.py
The server listens for incoming client connections, accepts the messages, and prints them in the terminal. It remains running until stopped.

2. client.py
The client connects to the server and allows the user to send messages. Each message is transmitted over a TCP socket to the server.


# How It Works

The server binds to a host and port, then waits for a client
The client connects to the server using the same host and port
Messages that are typed within the client is sent to the server
The server receives and displays each message

# Running the Program

Open two terminals:
## Terminal 1 - Start the server

python3 server.py

## Terminal 2 - Start the client

python3 client.py

Type messages into the client terminal to send them to the server.

# Notes

I added a stopping condition to the progran logic to ensure clean shutdown behavior. 
