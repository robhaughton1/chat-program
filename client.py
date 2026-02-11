import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
   client.connect(("localhost", 5000))
   message = "Hello from client!"
   client.send(message.encode())
   print("Message sent to server.")

except Exception as e:
	print(f"Error connecting or sending: {e}")

client.close()
