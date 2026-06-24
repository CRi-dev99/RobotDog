<<<<<<< HEAD
import os
import queue
import socket
import threading
import time

import cv2
import keyboard  # pip install keyboard - library to detect keystrokes
import numpy as np
from insightface.app import FaceAnalysis


ROBOT_HOST = "192.168.0.7"
CONTROL_PORT = 5000
VIDEO_PORT = 5001

KNOWN_FACES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "known_faces",
)

RECOGNITION_THRESHOLD = 0.45
COMMAND_COOLDOWN_SECONDS = 0.35
CENTER_DEADZONE_RATIO = 0.12
TARGET_FACE_WIDTH_RATIO = 0.28
REAL_FACE_WIDTH_CM = 16.0
FOCAL_LENGTH_PIXELS = None

VALID_COMMANDS = {"w", "a", "s", "d", "z", "x", "c", "t", "e"}


def create_face_app():
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    return app


def normalize_embedding(embedding):
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm


def load_known_faces(face_app):
    known_faces = {}

    if not os.path.isdir(KNOWN_FACES_DIR):
        print(f"Known faces folder not found: {KNOWN_FACES_DIR}")
        print("Create folders like RobotDog/known_faces/person_name/1.jpg")
        return known_faces

    for person_name in os.listdir(KNOWN_FACES_DIR):
        person_folder = os.path.join(KNOWN_FACES_DIR, person_name)
        if not os.path.isdir(person_folder):
            continue

        embeddings = []

        for filename in os.listdir(person_folder):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            image_path = os.path.join(person_folder, filename)
            image = cv2.imread(image_path)
            if image is None:
                print(f"Could not read known face image: {image_path}")
                continue

            faces = face_app.get(image)
            if not faces:
                print(f"No face found in known face image: {image_path}")
                continue

            face = max(faces, key=face_area)
            embeddings.append(normalize_embedding(face.embedding))

        if embeddings:
            known_faces[person_name] = embeddings
            print(f"Loaded {len(embeddings)} known face image(s) for {person_name}")

    if not known_faces:
        print("No known faces loaded. Face tracking commands will not be sent.")

    return known_faces


def recognize_face(face, known_faces):
    if not known_faces:
        return "Unknown", 0.0

    face_embedding = normalize_embedding(face.embedding)
    best_name = "Unknown"
    best_score = 0.0

    for name, embeddings in known_faces.items():
        for known_embedding in embeddings:
            score = float(np.dot(face_embedding, known_embedding))
            if score > best_score:
                best_score = score
                best_name = name

    if best_score < RECOGNITION_THRESHOLD:
        return "Unknown", best_score

    return best_name, best_score


def face_area(face):
    x1, y1, x2, y2 = face.bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def send_frame(sock, frame):
    success, encoded_frame = cv2.imencode(".jpg", frame)
    if not success:
        return

    data = encoded_frame.tobytes()
    sock.sendall(len(data).to_bytes(4, "big"))
    sock.sendall(data)


def robot_command_sender(command_queue, stop_event):
    try:
        with socket.socket() as client_socket:
            client_socket.connect((ROBOT_HOST, CONTROL_PORT))

            while True:
                if stop_event.is_set() and command_queue.empty():
                    break

                try:
                    command = command_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                client_socket.sendall(command.encode())
                response = client_socket.recv(1024).decode()
                print(f"Sent {command!r}, received: {response}")

                if command == "e":
                    stop_event.set()
                    break

    except OSError as exc:
        print(f"Robot command socket error: {exc}")
        stop_event.set()


def keyboard_controls(command_queue, stop_event):
    print("Client GUI")
    print(
        """
        _________________
        |   w   |   e   |
        |forward|  exit |
________|_______|_______|
|   a   |   s   |   d   |
| left  |  back | right |
|_______|_______|_______|_______
        |   z   |   x   |   c   |   t   |
        |head up|head dn|camera |stp cam|
        |_______|_______|_______|_______|
"""
    )

    while not stop_event.is_set():
        command = keyboard.read_key()
        if command not in VALID_COMMANDS:
            continue

        print(f"Key pressed: {command}")
        command_queue.put(command)

        if command == "e":
            break

        time.sleep(0.2)


def face_processing(command_queue, stop_event):
    face_app = create_face_app()
    known_faces = load_known_faces(face_app)
    last_command_time = 0.0

    try:
        with socket.socket() as video_socket:
            video_socket.connect((ROBOT_HOST, VIDEO_PORT))

            while not stop_event.is_set():
                size_bytes = recv_exact(video_socket, 4)
                if size_bytes is None:
                    break

                frame_size = int.from_bytes(size_bytes, "big")
                frame_bytes = recv_exact(video_socket, frame_size)
                if frame_bytes is None:
                    break

                frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                faces = face_app.get(frame)
                annotated_frame, target_face = annotate_faces(frame, faces, known_faces)

                now = time.monotonic()
                if (
                    target_face is not None
                    and now - last_command_time >= COMMAND_COOLDOWN_SECONDS
                ):
                    command = choose_tracking_command(target_face, frame.shape)
                    if command is not None:
                        command_queue.put(command)
                        last_command_time = now

                send_frame(video_socket, annotated_frame)

    except OSError as exc:
        print(f"Video socket error: {exc}")


def annotate_faces(frame, faces, known_faces):
    annotated_frame = frame.copy()
    target_face = None
    target_area = 0

    for face in faces:
        name, score = recognize_face(face, known_faces)
        x1, y1, x2, y2 = face.bbox.astype(int)
        metrics = calculate_face_metrics(face, frame.shape)

        is_known = name != "Unknown"
        color = (0, 255, 0) if is_known else (0, 0, 255)
        label = f"{name} {score:.2f} vis:{metrics['visibility']:.0f}%"

        if metrics["distance_cm"] is not None:
            label += f" {metrics['distance_cm']:.0f}cm"
        else:
            label += f" size:{metrics['face_width_ratio']:.2f}"

        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated_frame,
            label,
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )

        if is_known and metrics["area"] > target_area:
            target_face = face
            target_area = metrics["area"]

    draw_tracking_guides(annotated_frame)
    return annotated_frame, target_face


def calculate_face_metrics(face, frame_shape):
    frame_height, frame_width = frame_shape[:2]
    raw_x1, raw_y1, raw_x2, raw_y2 = face.bbox

    x1 = max(0, min(frame_width, raw_x1))
    y1 = max(0, min(frame_height, raw_y1))
    x2 = max(0, min(frame_width, raw_x2))
    y2 = max(0, min(frame_height, raw_y2))

    raw_area = max(1, (raw_x2 - raw_x1) * (raw_y2 - raw_y1))
    visible_area = max(0, x2 - x1) * max(0, y2 - y1)
    inside_ratio = visible_area / raw_area
    visibility = inside_ratio * float(face.det_score) * 100

    face_width = max(1, raw_x2 - raw_x1)
    distance_cm = None
    if FOCAL_LENGTH_PIXELS is not None:
        distance_cm = (REAL_FACE_WIDTH_CM * FOCAL_LENGTH_PIXELS) / face_width

    return {
        "area": visible_area,
        "visibility": visibility,
        "face_width_ratio": face_width / frame_width,
        "distance_cm": distance_cm,
    }


def draw_tracking_guides(frame):
    frame_height, frame_width = frame.shape[:2]
    center_x = frame_width // 2
    center_y = frame_height // 2
    deadzone_x = int(frame_width * CENTER_DEADZONE_RATIO)
    deadzone_y = int(frame_height * CENTER_DEADZONE_RATIO)

    cv2.rectangle(
        frame,
        (center_x - deadzone_x, center_y - deadzone_y),
        (center_x + deadzone_x, center_y + deadzone_y),
        (255, 255, 0),
        1,
    )


def choose_tracking_command(face, frame_shape):
    frame_height, frame_width = frame_shape[:2]
    x1, y1, x2, y2 = face.bbox

    face_center_x = (x1 + x2) / 2
    face_center_y = (y1 + y2) / 2
    face_width = x2 - x1

    error_x = face_center_x - (frame_width / 2)
    error_y = face_center_y - (frame_height / 2)
    deadzone_x = frame_width * CENTER_DEADZONE_RATIO
    deadzone_y = frame_height * CENTER_DEADZONE_RATIO
    target_face_width = frame_width * TARGET_FACE_WIDTH_RATIO

    if error_x < -deadzone_x:
        return "a"
    if error_x > deadzone_x:
        return "d"
    if error_y < -deadzone_y:
        return "z"
    if error_y > deadzone_y:
        return "x"
    if face_width < target_face_width * 0.8:
        return "w"
    if face_width > target_face_width * 1.2:
        return "s"

    return None


if __name__ == "__main__":
    commands = queue.Queue()
    stop = threading.Event()

    control_thread = threading.Thread(
        target=robot_command_sender,
        args=(commands, stop),
        daemon=True,
    )
    keyboard_thread = threading.Thread(
        target=keyboard_controls,
        args=(commands, stop),
        daemon=True,
    )
    face_thread = threading.Thread(
        target=face_processing,
        args=(commands, stop),
        daemon=True,
    )

    control_thread.start()
    keyboard_thread.start()
    face_thread.start()

    keyboard_thread.join()
    control_thread.join(timeout=2)
    face_thread.join(timeout=2)


# to run: cd "C:\Users\Cristian\OneDrive - St. Joseph's Patrician College\LC_Thonny\ClientServerDevelopment"
# & "C:\Users\Cristian\venvs\robotdog312\Scripts\python.exe" RobotDog\ClientCode\clientv2.py
=======
>>>>>>> 810c61c (the server now works - capturing frames, sending them to the client and displaying the processed ones)
