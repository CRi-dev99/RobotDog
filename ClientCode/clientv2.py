from email import message
import socket
import keyboard


'''def client_program():
    host = "192.168.0.7"
    port = 5000  # socket server port number

    client_socket = socket.socket()  # instantiate
    client_socket.connect((host, port))  # connect to the server

    message = input(" -> ")  # take input

    while message.lower().strip() != 'bye':
        client_socket.send(message.encode())  # send message
        data = client_socket.recv(1024).decode()  # receive response

        print('Received from server: ' + data)  # show in terminal

        message = input(" -> ")  # again take input

    client_socket.close()  # close the connection


if __name__ == '__main__':
    client_program()
'''






def client_program():
    host = "192.168.0.7"
    port = 5000  # socket server port number

    client_socket = socket.socket()  # instantiate
    client_socket.connect((host, port))  # connect to the server

    print("Client GUI")
    gui = '''
        ________
        |   w   |
        |forward|
________|_______|_______
|   a   |   s   |   d   |
| left  |  down | right |
|_______|_______|_______|
        

'''
    while True:
        print(gui)
        cmd = keyboard.read_key()
        print(f"Key pressed: {cmd}")
        if cmd != "e":
            client_socket.send(cmd.encode())
            data = client_socket.recv(1024).decode()  # receive response

            print('Received from server: ' + data)
        else:
            client_socket.close()
            break


if __name__ == '__main__':
    client_program()

# Need to add this code to github