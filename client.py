import socket # Socket insertion
from datetime import datetime # Timestamp library
import time # Time validation for security

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # IPv4 and TCP insertion

try:

    client.connect(("localhost", 5000)) # Port and host binding

    while True:
        message = input("Enter your message: ").strip() # User input text 

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

    full_message = f"{message} [{timestamp}]" # Message formatting
    
    client.send(full_message.encode())
    print("Message sent to server.")

except Exception as e:

    print(f"Error connecting or sending: {e}")

client.close()
