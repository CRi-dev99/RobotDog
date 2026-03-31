from flask import Flask
from routes import api
import logging

# ----------------------------
# Logging setup (for debugging)
# ----------------------------
logging.basicConfig(level=logging.INFO)

# ----------------------------
# Create the Flask app
# ----------------------------
app = Flask(__name__)

# ----------------------------
# Register blueprint with versioned prefix
# All routes inside routes.py become:
# /api/v1/...
# ----------------------------
app.register_blueprint(api, url_prefix="/api/v1")


# ----------------------------
# Run the server when executed directly
# ----------------------------
if __name__ == "__main__":
    # host="0.0.0.0" allows access from other devices on your network
    app.run(host="0.0.0.0", port=5000)
