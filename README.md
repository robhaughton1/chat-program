# Chat Program

A Python secure chat application built to demonstrate networking, authentication, encryption, persistence, and access control in a multi user system.

## Features

Multi client chat server using sockets and threading  
Secure client server communication  
User authentication with hashed credentials  
Session based encrypted messaging  
Public and private messaging  
Private conversation history  
Group chat with invite and approval flow  
Persistent groups and membership  
Group message history  
Encrypted storage for sensitive messages  
Duplicate login prevention  

## Project Structure

server.py  
Handles connections, authentication, message routing, group management, and persistence  

client.py  
Connects to the server, handles user input, and displays messages  

users.db  
Stores user credentials  

chat.db  
Stores messages, groups, and membership data  

## Commands

General  
/help  
Show available commands  

/who  
List online users  

/exit  
Disconnect  

Private messaging  
/msg <user> <message>  
Send a private message  

/history <user>  
View private conversation history  

Group chat  
/group_create <group_name>  
Create a group  

/group_add <group_name> <user>  
Invite a user  

yes or no  
Accept or decline a group invite  

/groups  
List your groups  

/gmsg <group_name> <message>  
Send a group message  

/group_history <group_name>  
View group message history  

/group_leave <group_name>  
Leave a group  

AI  
@ai <question>  
Send a prompt to the assistant  

## How It Works

The server starts and waits for client connections  

A client connects and authenticates with a username and password  

After authentication, the client can send messages and commands  

The server routes messages, enforces access control, and retrieves stored data when needed  

Messages and group data remain available after restart  

## Running the Program

Requirements

```bash
pip install pycryptodome bcrypt requests

Environment setup:

export CHAT_DB_KEY="0123456789abcdef0123456789abcdef"

For windows:

set CHAT_DB_KEY="0123456789abcdef0123456789abcdef"
