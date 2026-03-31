from flask import Blueprint, jsonify, request
#i#mport sys
#sys.path.append('../Freenove_Robot_Dog_Kit_for_Raspberry_Pi/Code/Server')
#sys.path.append("..")
try:
    from ..Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server import Control
except Exception:
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    server_dir = os.path.join(project_root, "Freenove_Robot_Dog_Kit_for_Raspberry_Pi", "Code", "Server")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)
    from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server import Led as L
    from Freenove_Robot_Dog_Kit_for_Raspberry_Pi.Code.Server import Control as C


# ---------------------------.
# Blueprint setup
# ----------------------------
api = Blueprint("api", __name__)

# ----------------------------
# Simple API key (for learning only)
# In real systems, store keys in a database or env variable.
# ----------------------------
API_KEY = "mysecretkey123"

# ----------------------------
# Simulated LED state (True = ON, False = OFF)
# ----------------------------
led_state = False



def validate_api_key():
    """
    Validates the API key sent in the Authorization header.
    Expected format: Authorization: Bearer <API_KEY>
    """
    auth_header = request.headers.get("Authorization")

    # If header missing -> unauthorized
    if not auth_header:
        return False

    # Split into ["Bearer", "<key>"]
    parts = auth_header.split()

    # If format is wrong -> unauthorized
    if len(parts) != 2 or parts[0] != "Bearer":
        return False

    # Validate key
    return parts[1] == API_KEY


def response_ok(data):
    """
    Standard success response format.
    """
    return jsonify({"success": True, "data": data, "error": None})


def response_error(message, code=400):
    """
    Standard error response format.
    """
    return jsonify({"success": False, "data": None, "error": message}), code


@api.route("/status", methods=["GET"])
def status():
    """
    GET /api/v1/status
    Returns basic server status and LED state.
    """
    # Validate API key
    if not validate_api_key():
        return response_error("Unauthorized", 401)

    return response_ok({"pi": "online", "led_state": led_state})


@api.route("/toggle", methods=["POST"])
def toggle_led():
    """
    POST /api/v1/toggle
    Toggles LED state based on JSON body:
    {"state": "on"} or {"state": "off"}
    """
    global led_state

    # Validate API key
    if not validate_api_key():
        return response_error("Unauthorized", 401)

    # Get JSON body
    data = request.get_json()
    if data is None:
        return response_error("Missing or invalid JSON", 400)

    # Get state value
    state = data.get("state")

    # Validate state value
    if state == "on":
        led_state = True
        L.Led().colorWipe([255, 0, 0])  # Example: turn LED red when ON
    elif state == "off":
        led_state = False
        L.Led().colorWipe([0, 0, 0])  # Example: turn LED off when OFF
    else:
        return response_error("Invalid state value", 400)

    return response_ok({"led_state": led_state})

@api.route("/move", methods=["POST"])
def move():
    """
    POST /api/v1/move
    Moves the robot based on JSON body:
    {"direction": "forward", "duration": 2}
    """
    # Validate API key
    if not validate_api_key():
        return response_error("Unauthorized", 401)

    # Get JSON body
    data = request.get_json()
    if data is None:
        return response_error("Missing or invalid JSON", 400)

    # Get direction and duration
    direction = data.get("direction")


    # Validate direction and duration
    if direction not in ["forward", "backward", "left", "right"]:
        return response_error("Invalid direction value", 400)


    # Call control function to move the robot
    if direction == "forward":
        C.Control().forWard()
    elif direction == "backward":
        C.Control().backWard()
    elif direction == "left":
        C.Control().stepLeft()
        print("Stepping left")
    elif direction == "right":
        C.Control().stepRight()

    return response_ok({"message": f"Moving {direction}"})
