from email import message
import socket
import keyboard # pip install keyboard - library to detect keystrokes








def client_program():
    host = "192.168.0.7"
    port = 5000  # socket server port number

    client_socket = socket.socket()  # instantiate
    client_socket.connect((host, port))  # connect to the server

    print("Client GUI")
    gui = '''
        _________________
        |   w   |   e   |
        |forward|  exit |
________|_______|_______|
|   a   |   s   |   d   |
| left  |  back | right |
|_______|_______|_______|
        |   z   |   x   |
        |head up|head down
        |_______|_______|

'''
    while True:
        print(gui)
        cmd = keyboard.read_key()
        print(f"Key pressed: {cmd}")
        if cmd != "e":
            client_socket.send(cmd.encode())
            data = client_socket.recv(1024).decode()  # receive response

            print(f"Received from server: {data}")
        else:
            client_socket.close()
            break


if __name__ == '__main__':
    client_program()

# Need to add this code to github - added