import socket

def server_program():
    host = socket.gethostname()
    port = 5000

    server_socket = socket.socket()
    server_socket.bind((host, port))
    server_socket.listen(2)

    print("Server listening on port 5000...")

    conn, address = server_socket.accept()
    print("Connection from:", address)

    while True:
        data = conn.recv(1024).decode()
        if not data:
            break
        print("Received:", data)
        response = input("Reply: ")
        conn.send(response.encode())

    conn.close()

if __name__ == '__main__':
    server_program()