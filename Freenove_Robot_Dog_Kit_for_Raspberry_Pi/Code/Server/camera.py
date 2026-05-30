import sys
from picamera2 import Picamera2


def main() -> int:
    try:
        available_cameras = Picamera2.global_camera_info()
    except Exception as exc:
        print(f"Error checking available cameras: {exc}", file=sys.stderr)
        return 1

    if not available_cameras:
        print(
            "No camera detected. Please connect a Raspberry Pi camera or enable the camera interface.",
            file=sys.stderr,
        )
        return 1

    try:
        picam2 = Picamera2()
    except Exception as exc:
        print(f"Failed to initialize Picamera2: {exc}", file=sys.stderr)
        return 1

    picam2.start_and_capture_file("image.jpg")
    print("Captured image.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())