from email import message
import socket
import keyboard # pip install keyboard - library to detect keystrokes
import threading
import numpy as np
import cv2
from ultralytics import YOLO








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
|_______|_______|_______|_______
        |   z   |   x   |   c   |
        |head up|head dn| camera|
        |_______|_______|_______|

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
            client_socket.send(cmd.encode())
            data = client_socket.recv(1024).decode()
            client_socket.close()
            break

def yolo_processing():
    host = "192.168.0.8"
    port = 5001  # socket server port number

    client_socket = socket.socket()  # instantiate
    client_socket.connect((host, port))  # connect to the server
    model = YOLO("yolov8n.pt")

    while True:
        size_bytes = recv_exact(client_socket, 4)
        if size_bytes is None:
            break

        frame_size = int.from_bytes(size_bytes, "big")
        frame_bytes = recv_exact(client_socket, frame_size)
        if frame_bytes is None:
            break

        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

        results = model(frame)
        processed_frame = results[0].plot()

        success, encoded_frame = cv2.imencode(".jpg", processed_frame)
        if not success:
            continue

        data = encoded_frame.tobytes()
        client_socket.sendall(len(data).to_bytes(4, "big"))
        client_socket.sendall(data)




def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            break
        data += chunk
    return data

if __name__ == '__main__':
    control_thread = threading.Thread(target=client_program)
    control_thread.start()
    yolo_thread = threading.Thread(target=yolo_processing)
    yolo_thread.start()



# to run: cd "C:\Users\Cristian\OneDrive - St. Joseph's Patrician College\LC_Thonny\ClientServerDevelopment"
# & "C:\Users\Cristian\venvs\robotdog312\Scripts\python.exe" RobotDog\ClientCode\clientv2.py