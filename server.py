import socket

print("Server running with Port 5000...")
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("localhost", 5000))
server.listen(1)


conn, addr = server.accept()
print(f"Client connected with address {addr}.")

try:
	data = conn.recv(1024)
	if not data:
	   print("No data received.")
	else:
	    message = data.decode(errors="replace")
	    print(f"Client says: {message}")
except Exception as e:
	    print(f"Error with data transfer: {e}")
	    
conn.close()
server.close()
