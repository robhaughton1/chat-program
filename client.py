import socket 
from datetime import datetime 
import time # Time validation for security
import threading

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # IPv4 and TCP insertion

try:

    client.connect(("localhost", 5000)) # Port and host binding
    print("Please log in.\n")
    
# Authentication
    attempts = 0
    MAX_ATTEMPTS = 5
    
    while attempts < MAX_ATTEMPTS:
        username = input("Username: ").strip()
        password = input("Password: ").strip()
    
        client.send(username.encode())
        time.sleep(0.1)
        client.send(password.encode())
    
        response = client.recv(1024).decode()
    
        if "Verified" in response:
                time.sleep(0.5)
                
                print("Type /help for commands.\n")
                time.sleep(0.2)
                
                print(f"Welcome, {username}!")
                
                
                
               
               
                
        
                def receive_from_server():
                        while True:
                                try:
                                        data = client.recv(1024)
                                        if not data:
                                                print("Server disconnected.")
                                                exit()
                                                break
                                        print(f"\nServer: {data.decode(errors='replace')}")
                                except:
                                        break
                threading.Thread(target=receive_from_server, daemon=True).start()
        
                break
        
        else:                                       
                attempts += 1
                print(F"Authentication failed; {MAX_ATTEMPTS - attempts}\n left.")
                
                if attempts >= MAX_ATTEMPTS:
                        print("Too many failed attempts. Closing connection...")
                        client.close()
                        exit()
# Messaging
    while True: 
        while True:
            time.sleep(1) 
            message = input("Enter your message: ").strip() # User input text 
            
            if message.lower() == "/exit":
                client.send("/exit".encode())
                print("Closing connection...")
                client.close()
                exit()

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
    
        client.send(full_message.encode())
        
        if not is_command:
                print("Message sent to server.") 
        
except Exception as e:

    print(f"Error connecting or sending: {e}")
client.close()
