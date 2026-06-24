import os
import queue
import sys
import threading
from time import sleep

from libcamera import ColorSpace
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder


CAMERA_FPS = 15
RES_X = 640
RES_Y = 480

camera_device_lock = threading.Lock()
camera_stream_lock = threading.Lock()
camera_stop = None
camera_thread = None
camera_frame_queue = None


def start_camera_capture():
    global camera_stop, camera_thread, camera_frame_queue

    with camera_stream_lock:
        if camera_thread and camera_thread.is_alive():
            print("Camera capture is already running")
            return True

        if not camera_device_lock.acquire(blocking=False):
            print("Camera is already in use", file=sys.stderr)
            return False

        camera_stop = threading.Event()
        camera_frame_queue = queue.Queue(maxsize=1)
        camera_thread = threading.Thread(
            target=captureCameraFrames,
            args=(camera_frame_queue, camera_stop),
            name="Camera-Capture",
            daemon=True,
        )

        try:
            camera_thread.start()
        except Exception as exc:
            print(f"Failed to start camera capture: {exc}", file=sys.stderr)
            camera_stop.set()
            camera_stop = None
            camera_thread = None
            camera_frame_queue = None
            releaseCameraDeviceLock()
            return False

        return True


def stop_camera_capture(timeout=5):
    global camera_stop, camera_thread, camera_frame_queue

    with camera_stream_lock:
        stop_event = camera_stop
        thread = camera_thread

    if stop_event is not None:
        stop_event.set()

    if thread is not None:
        thread.join(timeout=timeout)

    if thread is not None and thread.is_alive():
        print("Camera capture thread did not stop cleanly", file=sys.stderr)
        return False

    with camera_stream_lock:
        camera_stop = None
        camera_thread = None
        camera_frame_queue = None

    return True


def get_frame_queue():
    return camera_frame_queue


def get_latest_frame(timeout=1):
    if camera_frame_queue is None:
        return None

    try:
        return camera_frame_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def putLatest(queue_obj, item):
    while True:
        try:
            queue_obj.put_nowait(item)
            return
        except queue.Full:
            try:
                queue_obj.get_nowait()
            except queue.Empty:
                pass


def captureCameraFrames(frame_queue, stop_event):
    picam2 = None

    try:
        picam2 = initCamera()
        if not picam2:
            stop_event.set()
            return None

        config = picam2.create_video_configuration(
            main={"size": (RES_X, RES_Y), "format": "RGB888"},
            controls={"FrameRate": CAMERA_FPS},
        )
        picam2.configure(config)
        picam2.start()

        while not stop_event.is_set():
            frame = picam2.capture_array()
            putLatest(frame_queue, frame)

    except Exception as exc:
        print(f"Error capturing camera frames: {exc}", file=sys.stderr)
        stop_event.set()
        return None
    finally:
        if picam2:
            closeCamera(picam2)
        releaseCameraDeviceLock()


def releaseCameraDeviceLock():
    try:
        camera_device_lock.release()
    except RuntimeError:
        pass


def closeCamera(picam2):
    try:
        picam2.stop()
    except Exception as exc:
        print(f"Error stopping camera: {exc}", file=sys.stderr)

    try:
        picam2.close()
    except Exception as exc:
        print(f"Error closing camera: {exc}", file=sys.stderr)


def initCamera():
    try:
        available_cameras = Picamera2.global_camera_info()
    except Exception as exc:
        print(f"Error checking available cameras: {exc}", file=sys.stderr)
        return None

    if not available_cameras:
        print(
            "No camera detected. Please connect a Raspberry Pi camera or enable the camera interface.",
            file=sys.stderr,
        )
        return None

    try:
        return Picamera2()
    except Exception as exc:
        print(f"Failed to initialize Picamera2: {exc}", file=sys.stderr)
        return None


def Video(time):
    if not camera_device_lock.acquire(blocking=False):
        print("Camera is already in use", file=sys.stderr)
        return None

    picam2 = None
    recording_started = False

    try:
        picam2 = initCamera()
        if not picam2:
            return None

        config = picam2.create_video_configuration(colour_space=ColorSpace.Sycc())
        picam2.configure(config)
        encoder = H264Encoder(10000000)

        picam2.start_recording(encoder, f"/home/pi/robot_dog111111/videos/{savingNewVideos()}")
        recording_started = True
        sleep(time)
        picam2.stop_recording()
        recording_started = False

    except Exception as exc:
        print(f"Error recording video: {exc}", file=sys.stderr)
        return None
    finally:
        if picam2:
            if recording_started:
                try:
                    picam2.stop_recording()
                except Exception as exc:
                    print(f"Error stopping video recording: {exc}", file=sys.stderr)

            closeCamera(picam2)
        releaseCameraDeviceLock()


def savingNewVideos():
    counter = 1
    files = os.listdir("/home/pi/robot_dog111111/videos")
    if not files:
        return "video1.h264"

    for filename in files:
        if filename.startswith("video") and filename.endswith(".h264"):
            num = int(filename[5:-5])
            if counter <= num:
                counter = num

    counter += 1
    return f"video{counter}.h264"


def Picture():
    if not camera_device_lock.acquire(blocking=False):
        print("Camera is already in use", file=sys.stderr)
        return None

    picam2 = None

    try:
        picam2 = initCamera()
        if not picam2:
            return None

        config = picam2.create_still_configuration(colour_space=ColorSpace.Sycc())
        picam2.configure(config)
        picam2.start()
        sleep(2)
        picam2.capture_file(f"/home/pi/robot_dog111111/pictures/{savingNewPictures()}")

    except Exception as exc:
        print(f"Error capturing picture: {exc}", file=sys.stderr)
        return None
    finally:
        if picam2:
            closeCamera(picam2)
        releaseCameraDeviceLock()


def savingNewPictures():
    counter = 1
    files = os.listdir("/home/pi/robot_dog111111/pictures")
    if not files:
        return "picture1.jpg"

    for filename in files:
        if filename.startswith("picture") and filename.endswith(".jpg"):
            num = int(filename[7:-4])
            if counter <= num:
                counter = num

    counter += 1
    return f"picture{counter}.jpg"
