

import socket
import sys
import os
from time import sleep, monotonic
import threading
import cv2
import numpy as np


sendBack= False
latest_processed_frame = None
processed_frame_lock = threading.Lock()
YOLO_WINDOW_NAME = "YOLO Processed Frame"
SOCKET_TIMEOUT_SECONDS = 0.5
shutdown_event = threading.Event()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Control import Control as C
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.Servo import Servo as S
from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server.camera import *


def wait_for_connection(server_socket):
    while not shutdown_event.is_set():
        try:
            return server_socket.accept()
        except socket.timeout:
            continue

    return None, None


def close_socket(sock):
    if sock is None:
        return

    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass

    try:
        sock.close()
    except OSError:
        pass


def control_server():
    # get the hostname
    host = "0.0.0.0"
    port1 = 5000  # initiate port no above 1024

    server_socket = socket.socket()  # get instance
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
    # look closely. The bind() function takes tuple as argument
    server_socket.bind((host, port1))  # bind host address and port together

    # configure how many client the server can listen simultaneously
    server_socket.listen(2)
    conn = None
    headBaseAngle = 120
    headChannel = 15
    counter = headBaseAngle
    try:
        conn, address = wait_for_connection(server_socket)  # accept new connection
        if conn is None:
            return

        conn.settimeout(SOCKET_TIMEOUT_SECONDS)
        print("Connection from: " + str(address))

        controller = C()
        head = S()
        head.setServoAngle(headChannel, headBaseAngle)
        while not shutdown_event.is_set():
            # receive data stream. it won't accept data packet greater than 1024 bytes
            try:
                raw_data = conn.recv(1024)
            except socket.timeout:
                continue

            if not raw_data:
                print("Control client disconnected")
                shutdown_event.set()
                break

            data = raw_data.decode().strip()
            response = "Command received"

            if data == "w":
                    controller.forWard()
            elif data == "s":
                    controller.backWard()
            elif data == "a":
                    controller.turnLeft()
            elif data == "d":
                    controller.turnRight()
            elif data == "z":
                head.setServoAngle(headChannel, counter+1)
                counter += 0.5
            elif data == "x":
                head.setServoAngle(headChannel, counter-1)
                counter -= 0.5
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
                response = "Server exiting"
                shutdown_event.set()
                
            print("from connected user: " + str(data))
            if sendBack and data != "e":
                response = input(' -> ')

            try:
                conn.sendall(response.encode())  # send data to the client
            except OSError:
                print("Control client disconnected before response")
                shutdown_event.set()
                break

            if data == "e":
                break
    except KeyboardInterrupt:
        print("Server shutting down gracefully")
        shutdown_event.set()
    except OSError as exc:
        if not shutdown_event.is_set():
            print(f"Control server socket error: {exc}")
            shutdown_event.set()
    finally:
        shutdown_event.set()
        stop_camera_capture()
        close_socket(conn)
        close_socket(server_socket)



def yolo_server():
    host = "0.0.0.0"
    port = 5001

    server_socket = socket.socket()  # get instance
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
    server_socket.bind((host, port))  # bind host address and port together
    server_socket.listen(1)
    conn = None

    try:
        conn, address = wait_for_connection(server_socket)  # accept new connection
        if conn is None:
            return

        conn.settimeout(SOCKET_TIMEOUT_SECONDS)
        print("YOLO client connection from: " + str(address))
        if not start_camera_capture():
            print("Could not start camera capture", file=sys.stderr)
            shutdown_event.set()
            return
        
        frame_count = 0
        last_fps_time = monotonic()

        while not shutdown_event.is_set():
            frame = get_latest_frame(timeout=1)
            if frame is None:
                continue

            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                continue

            data = jpeg.tobytes()
            try:
                conn.sendall(len(data).to_bytes(4, "big"))
                conn.sendall(data)
            except OSError:
                if not shutdown_event.is_set():
                    print("YOLO client disconnected")
                    shutdown_event.set()
                break

            processed_frame = receive_jpeg_frame(conn)
            height, width = processed_frame.shape[:2]
            print(f"Received processed frame of size: {width}x{height}")
            if processed_frame is None:
                if not shutdown_event.is_set():
                    print("YOLO client disconnected")
                    shutdown_event.set()
                break

            set_latest_processed_frame(processed_frame)

            frame_count += 1
            now = monotonic()
            if now - last_fps_time >= 1.0:
                fps = frame_count / (now - last_fps_time)
                print(f"FPS: {fps:.2f}")
                frame_count = 0
                last_fps_time = now
            if not display_processed_frame(processed_frame):
                print("Closing YOLO display")
                shutdown_event.set()
                break




    except (ConnectionError, BrokenPipeError):
        print("YOLO client disconnected")
        shutdown_event.set()
    except OSError as exc:
        if not shutdown_event.is_set():
            print(f"YOLO server socket error: {exc}", file=sys.stderr)
            shutdown_event.set()
    except cv2.error as exc:
        print(f"Could not display YOLO frame: {exc}", file=sys.stderr)
        shutdown_event.set()
    except KeyboardInterrupt:
        print("YOLO server shutting down gracefully")
        shutdown_event.set()
    finally:
        shutdown_event.set()
        stop_camera_capture()
        close_socket(conn)
        close_socket(server_socket)
        cv2.destroyAllWindows()

def recv_exact(sock, size):
    data = b""
    while len(data) < size and not shutdown_event.is_set():
        try:
            packet = sock.recv(size - len(data))
        except socket.timeout:
            continue

        if not packet:
            return None
        data += packet

    if shutdown_event.is_set():
        return None

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
    shutdown_event.clear()

    control_thread = threading.Thread(target=control_server, name="Control-Server")
    yolo_thread = threading.Thread(target=yolo_server, name="YOLO-Server")
    threads = [control_thread, yolo_thread]

    try:
        for thread in threads:
            thread.start()

        while any(thread.is_alive() for thread in threads):
            if shutdown_event.is_set():
                break
            sleep(0.1)

    except KeyboardInterrupt:
        print("Server shutting down gracefully")
        shutdown_event.set()

    finally:
        shutdown_event.set()
        stop_camera_capture()

        for thread in threads:
            thread.join(timeout=2)

        still_running = [thread.name for thread in threads if thread.is_alive()]
        if still_running:
            print(f"Threads did not stop cleanly: {', '.join(still_running)}")

        cv2.destroyAllWindows()
        print("Server closed.")

# run source yolo-env/bin/activate to activate the venv
# dectivate to exit the venv



# Because I had too change the robot shield, many of the sensors don't communicate in Control.py
# I've commented out the code that uses the sensors
# Most of the probleemss can from the __init__
