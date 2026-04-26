

import socket
import sys
import os

sendBack= False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Control import Control as C
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Servo import Servo as S

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
    head = S()
    headBaseAngle = 90
    headChannel = 15
    counter = headBaseAngle
    try:
        conn, address = server_socket.accept()  # accept new connection
        print("Connection from: " + str(address))
        head.setServoAngle(headChannel, headBaseAngle)
        while True:
            # receive data stream. it won't accept data packet greater than 1024 bytes
            data = conn.recv(1024).decode()
            if data == "w":
                for i in range(3):
                    controller.forWard()
            elif data == "s":
                for i in range(3):
                    controller.backWard()
            elif data == "a":
                for i in range(3):
                    controller.turnLeft()
            elif data == "d":
                for i in range(3):
                    controller.turnRight()
            elif data == "z":
                head.setServoAngle(headChannel, counter+10)
                counter += 10
            elif data == "x":
                head.setServoAngle(headChannel, counter-10)
                counter -= 10
                
            print("from connected user: " + str(data))
            if sendBack:
                data = input(' -> ')
            else:
                data = "Command received"
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