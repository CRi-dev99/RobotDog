import requests

# ----------------------------
# Server configuration
# ----------------------------
BASE_URL = "http://192.168.0.7:5000/api/v1"
API_KEY = "mysecretkey123"

# Standard headers sent with every request
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def send_request(method, endpoint, json_data=None):
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=HEADERS,
            json=json_data,
            timeout=5
        )
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return None

    return response


def get_status():
    response = send_request("GET", "/status")
    if not response:
        return

    if response.status_code == 200:
        print("Status:", response.json())
    else:
        print("Error:", response.text)


def toggle_led(state):
    response = send_request("POST", "/toggle", {"state": state})
    if not response:
        return

    if response.status_code == 200:
        print("LED response:", response.json())
    else:
        print("Error:", response.text)

def moveForward():
    response = send_request("POST", "/move", {"direction": "forward"})
    if not response:
        return

    if response.status_code == 200:
        print("Move response:", response.json())
    else:
        print("Error:", response.text)

def moveBackward():
    response = send_request("POST", "/move", {"direction": "backward"})
    if not response:
        return

    if response.status_code == 200:
        print("Move response:", response.json())
    else:
        print("Error:", response.text)

def moveRight():
    response = send_request("POST", "/move", {"direction": "right"})
    if not response:
        return

    if response.status_code == 200:
        print("Move response:", response.json())
    else:
        print("Error:", response.text)

def moveLeft():
    response = send_request("POST", "/move", {"direction": "left"})
    if not response:
        return

    if response.status_code == 200:
        print("Move response:", response.json())
    else:
        print("Error:", response.text)


if __name__ == "__main__":
    get_status()
    toggle_led("on")
    toggle_led("off")
    while True:
        cmd = input("Enter command (status/toggle on/toggle off/forward/backward/right/left/exit): ").strip().lower()
        if cmd == "status":
            get_status()
        elif cmd == "toggle on":
            toggle_led("on")
        elif cmd == "toggle off":
            toggle_led("off")
        elif cmd == "forward":
            moveForward()
        elif cmd == "backward":
            moveBackward()
        elif cmd == "right":
            moveRight()
        elif cmd == "left":
            moveLeft()
            print("left")
        elif cmd == "exit":
            break
        else:
            print("Unknown command. Please try again.")
