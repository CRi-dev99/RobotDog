import socket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Control import Control as C

def server_program():
    # get the hostname
    host = "0.0.0.0"
    port = 5000  # initiate port no above 1024

    server_socket = socket.socket()  # get instance
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # look closely. The bind() function takes tuple as argument
    server_socket.bind((host, port))  # bind host address and port together

    # configure how many client the server can listen simultaneously
    server_socket.listen(2)
    conn = None
    controller = C()
    try:
        conn, address = server_socket.accept()  # accept new connection
        print("Connection from: " + str(address))
        while True:
            # receive data stream. it won't accept data packet greater than 1024 bytes
            data = conn.recv(1024).decode()
            split_data = data.split(',')
            if split_data[0] == 'forward':
                counter = split_data[1]
                for i in range(int(counter)):
                    controller.forWard()
            if split_data[0] == 'backward':
                counter = split_data[1]
                for i in range(int(counter)):
                    controller.backWard()
            if split_data[0] == 'left':
                counter = split_data[1]
                for i in range(int(counter)):
                    controller.turnLeft()
            if split_data[0] == 'right':
                counter = split_data[1]
                for i in range(int(counter)):
                    controller.turnRight()
            if not data:
                # if data is not received break
                break
            print("from connected user: " + str(data))
            data = input(' -> ')
            conn.send(data.encode())  # send data to the client
    except KeyboardInterrupt:
        print("Server shutting down gracefully")
    finally:
        if conn:
            conn.close()  # close the connection
        server_socket.close()


if __name__ == '__main__':
    server_program()



# Because I had too change the robot shield, many of the sensors don't communicate in Control.py
# I've commented out the code that uses the sensors
# Most of the probleemss can from the __init__

