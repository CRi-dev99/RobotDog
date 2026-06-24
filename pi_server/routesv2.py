

import socket
import sys
import os
from time import sleep
import threading
import cv2
import numpy as np


sendBack= False
latest_processed_frame = None
processed_frame_lock = threading.Lock()
YOLO_WINDOW_NAME = "YOLO Processed Frame"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Control import Control as C
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Servo import Servo as S
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.camera import *


def control_server():
    # get the hostname
    host = "0.0.0.0"
    port1 = 5000  # initiate port no above 1024

    server_socket = socket.socket()  # get instance
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # look closely. The bind() function takes tuple as argument
    server_socket.bind((host, port1))  # bind host address and port together

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
            elif data == "v":
                print("Starting video recording for 10 seconds...")
                Video(10)
                print("Video recording completed.")
            elif data == "q":
                print("Taking picture in 3...")
                sleep(1)
                print("Taking a picture in 2...")
                sleep(1)
                print("Taking a picture in 1...")
                Picture()
            elif data == "c":
                start_camera_capture()
            elif data == "t":
                stop_camera_capture()
            elif data == "e":
                print("Exiting the server program.")
                break
                
            print("from connected user: " + str(data))
            if sendBack:
                data = input(' -> ')
            else:
                data = "Command received"
            conn.send(data.encode())  # send data to the client
    except KeyboardInterrupt:
        print("Server shutting down gracefully")
    finally:
        stop_camera_capture()
        if conn:
            conn.close()  # close the connection
        server_socket.close()



def yolo_server():
    host = "0.0.0.0"
    port = 5001

    server_socket = socket.socket()  # get instance
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))  # bind host address and port together
    server_socket.listen(1)
    conn = None

    try:
        conn, address = server_socket.accept()  # accept new connection
        print("YOLO client connection from: " + str(address))
        start_camera_capture()

        while True:
            frame = get_latest_frame(timeout=1)
            if frame is None:
                continue

            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                continue

            data = jpeg.tobytes()
            conn.sendall(len(data).to_bytes(4, "big"))
            conn.sendall(data)
            processed_frame = receive_jpeg_frame(conn)
            if processed_frame is None:
                print("YOLO client disconnected")
                break

            set_latest_processed_frame(processed_frame)
            if not display_processed_frame(processed_frame):
                print("Closing YOLO display")
                break




    except (ConnectionError, BrokenPipeError):
        print("YOLO client disconnected")
    except cv2.error as exc:
        print(f"Could not display YOLO frame: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("YOLO server shutting down gracefully")
    finally:
        stop_camera_capture()
        if conn:
            conn.close()  # close the connection
        server_socket.close()
        cv2.destroyAllWindows()

def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


def receive_jpeg_frame(sock):
    size_bytes = recv_exact(sock, 4)
    if size_bytes is None:
        return None

    frame_size = int.from_bytes(size_bytes, "big")
    frame_bytes = recv_exact(sock, frame_size)
    if frame_bytes is None:
        return None

    frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
    return cv2.imdecode(frame_array, cv2.IMREAD_COLOR)


def set_latest_processed_frame(frame):
    global latest_processed_frame

    with processed_frame_lock:
        latest_processed_frame = frame


def get_latest_processed_frame():
    with processed_frame_lock:
        return latest_processed_frame


def display_processed_frame(frame):
    cv2.imshow(YOLO_WINDOW_NAME, frame)
    return (cv2.waitKey(1) & 0xFF) != ord("q")


if __name__ == '__main__':
    control_thread = threading.Thread(target=control_server)
    yolo_thread = threading.Thread(target=yolo_server)

    control_thread.start()
    yolo_thread.start()

    control_thread.join()
    yolo_thread.join()

# run source yolo-env/bin/activate to activate the venv
# dectivate to exit the venv



# Because I had too change the robot shield, many of the sensors don't communicate in Control.py
# I've commented out the code that uses the sensors
# Most of the probleemss can from the __init__
