import sys
from picamera2 import Picamera2, Preview
from libcamera import ColorSpace
from picamera2.encoders import H264Encoder
from time import sleep
import os
import threading
import multiprocessing as mp
import queue
import cv2


camera_stop = None
camera_processes = []
camera_frame_queue = None
camera_result_queue = None
camera_process_lock = threading.Lock()
camera_device_lock = threading.Lock()
CV_CAPTURE_CPU = 0
CV_YOLO_CPUS = (1, 3)
CV_DISPLAY_CPU = 2
CV_FPS = 15
RES_X = 640
RES_Y = 480
YOLO_IMG_SIZE = 320
YOLO_CONF = 0.4
YOLO_MAX_DET = 10
YOLO_EVERY_N_FRAMES = 1
YOLO_TORCH_THREADS = 2
YOLO_INTEROP_THREADS = 1


def start_camera_processes():
    global camera_stop, camera_processes, camera_frame_queue, camera_result_queue

    with camera_process_lock:
        live_processes = [process for process in camera_processes if process.is_alive()]
        if live_processes:
            print("Computer vision processes are already running")
            return False

        if camera_device_lock.locked():
            print("Camera is already in use", file=sys.stderr)
            return False

        if not camera_device_lock.acquire(blocking=False):
            print("Camera is already in use", file=sys.stderr)
            return False

        camera_stop = mp.Event()
        camera_frame_queue = mp.Queue(maxsize=1)
        camera_result_queue = mp.Queue(maxsize=1)

        camera_processes = [
            mp.Process(
                target=captureCVFrames,
                args=(camera_frame_queue, camera_stop),
                name="CV-Capture",
            ),
            mp.Process(
                target=runYoloDetection,
                args=(camera_frame_queue, camera_result_queue, camera_stop),
                name="CV-YOLO",
            ),
            mp.Process(
                target=displayCVResults,
                args=(camera_result_queue, camera_stop),
                name="CV-Display",
            ),
        ]

        try:
            for process in camera_processes:
                process.start()
        except Exception as exc:
            print(f"Failed to start computer vision processes: {exc}", file=sys.stderr)
            camera_stop.set()
            for process in camera_processes:
                if process.is_alive():
                    process.terminate()
            for process in camera_processes:
                process.join(timeout=1)
            _close_queue(camera_frame_queue)
            _close_queue(camera_result_queue)
            camera_stop = None
            camera_processes = []
            camera_frame_queue = None
            camera_result_queue = None
            _release_camera_device_lock()
            return False

        return True


def stop_camera_processes(timeout=5):
    global camera_stop, camera_processes, camera_frame_queue, camera_result_queue

    with camera_process_lock:
        stop_event = camera_stop
        processes = list(camera_processes)
        frame_queue = camera_frame_queue
        result_queue = camera_result_queue

    if stop_event is not None:
        stop_event.set()

    for process in processes:
        process.join(timeout=timeout)

    for process in processes:
        if _process_is_alive(process):
            print(f"Terminating {process.name}", file=sys.stderr)
            process.terminate()

    for process in processes:
        process.join(timeout=1)

    for process in processes:
        if _process_is_alive(process) and hasattr(process, "kill"):
            print(f"Killing {process.name}", file=sys.stderr)
            process.kill()

    for process in processes:
        process.join(timeout=1)

    stopped = all(not _process_is_alive(process) for process in processes)

    for process in processes:
        try:
            process.close()
        except ValueError:
            pass

    _close_queue(frame_queue)
    _close_queue(result_queue)

    with camera_process_lock:
        camera_stop = None
        camera_processes = []
        camera_frame_queue = None
        camera_result_queue = None

    _release_camera_device_lock()
    return stopped


def start_camera_thread():
    return start_camera_processes()


def stop_camera_thread(timeout=5):
    return stop_camera_processes(timeout)


def _release_camera_device_lock():
    try:
        camera_device_lock.release()
    except RuntimeError:
        pass


def _close_queue(queue_obj):
    if queue_obj is None:
        return

    try:
        queue_obj.close()
        queue_obj.join_thread()
    except Exception as exc:
        print(f"Error closing queue: {exc}", file=sys.stderr)


def _process_is_alive(process):
    try:
        return process.is_alive()
    except ValueError:
        return False


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


def pinCurrentProcess(cpus):
    allowed = os.sched_getaffinity(0)
    if isinstance(cpus, int):
        requested = {cpus}
    else:
        requested = set(cpus)

    selected = requested & allowed
    if not selected:
        selected = {min(allowed)}

    os.sched_setaffinity(os.getpid(), selected)


def displayAndCVVideo():
    return start_camera_processes()


def captureCVFrames(frame_queue, stop_event):
    picam2 = None

    try:
        pinCurrentProcess(CV_CAPTURE_CPU)

        picam2 = initCamera()
        if not picam2:
            stop_event.set()
            return None

        config = picam2.create_video_configuration(
            main={"size": (RES_X, RES_Y), "format": "RGB888"},
            controls={"FrameRate": CV_FPS}
        )
        picam2.configure(config)
        picam2.start()

        while not stop_event.is_set():
            frame = picam2.capture_array()
            putLatest(frame_queue, frame)

    except Exception as exc:
        print(f"Error capturing CV frames: {exc}", file=sys.stderr)
        stop_event.set()
        return None
    finally:
        if picam2:
            closeCamera(picam2)


def runYoloDetection(frame_queue, result_queue, stop_event):
    try:
        pinCurrentProcess(CV_YOLO_CPUS)
        cv2.setNumThreads(1)

        import torch
        torch.set_num_threads(YOLO_TORCH_THREADS)
        try:
            torch.set_num_interop_threads(YOLO_INTEROP_THREADS)
        except RuntimeError as exc:
            print(f"Could not set YOLO interop threads: {exc}", file=sys.stderr)

        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        frame_counter = 0

        while not stop_event.is_set():
            try:
                frame = frame_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            frame_counter += 1
            if frame_counter % YOLO_EVERY_N_FRAMES != 0:
                continue

            results = model.predict(
                frame,
                imgsz=YOLO_IMG_SIZE,
                conf=YOLO_CONF,
                max_det=YOLO_MAX_DET,
                verbose=False,
            )
            annotated_frame = results[0].plot()
            putLatest(result_queue, annotated_frame)

    except Exception as exc:
        print(f"Error running YOLO detection: {exc}", file=sys.stderr)
        stop_event.set()
        return None


def displayCVResults(result_queue, stop_event):
    try:
        pinCurrentProcess(CV_DISPLAY_CPU)

        while not stop_event.is_set():
            try:
                annotated_frame = result_queue.get(timeout=0.2)
            except queue.Empty:
                cv2.waitKey(1)
                continue

            cv2.imshow("YOLO Camera", annotated_frame)
            if cv2.waitKey(1) == ord("q"):
                stop_event.set()
                break

    except Exception as exc:
        print(f"Error displaying CV results: {exc}", file=sys.stderr)
        stop_event.set()
        return None
    finally:
        cv2.destroyAllWindows()


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
        picam2 = Picamera2()
        return picam2
    except Exception as exc:
        print(f"Failed to initialize Picamera2: {exc}", file=sys.stderr)




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
        print(f"Error displaying video: {exc}", file=sys.stderr)
        return None
    finally:
        if picam2:
            if recording_started:
                try:
                    picam2.stop_recording()
                except Exception as exc:
                    print(f"Error stopping video recording: {exc}", file=sys.stderr)

            closeCamera(picam2)
        camera_device_lock.release()


def savingNewVideos():
    counter = 1
    files = os.listdir("/home/pi/robot_dog111111/videos")
    if not files:
        return "video1.h264"
    for i in files:
        if i.startswith("video") and i.endswith(".h264"):
            num = int(i[5:-5])
            if counter <= num:
                counter = num
    counter += 1
    new_name = f"video{counter}.h264"
    return new_name


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
        camera_device_lock.release()

def savingNewPictures():
    counter = 1
    files = os.listdir("/home/pi/robot_dog111111/pictures")
    if not files:
        return "picture1.jpg"
    for i in files:
        if i.startswith("picture") and i.endswith(".jpg"):
            num = int(i[7:-4])
            if counter <= num:
                counter = num
    counter += 1
    new_name = f"picture{counter}.jpg"
    return new_name
