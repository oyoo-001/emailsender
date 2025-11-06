import os
import secrets
import time
import uuid
import smtplib
from email.message import EmailMessage
import ssl

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Load environment variables from .env file (for local testing)
load_dotenv()

# --- Configuration & State ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT_STR = os.getenv("SMTP_PORT", "587")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
# IMPORTANT: Use the single-quoted value for the Render environment
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") 

try:
    SMTP_PORT = int(SMTP_PORT_STR)
except ValueError:
    SMTP_PORT = 587
    print(f"Warning: SMTP_PORT is invalid, defaulting to {SMTP_PORT}")

# In-memory store for OTPs: {session_id: {'otp': '123456', 'email': 'user@example.com', 'expiry': 1678886400}}
# For a production app, this should be a persistent store like Redis or Firestore.
OTP_STORE = {}
OTP_EXPIRY_SECONDS = 300  # 5 minutes

# --- Flask App Initialization ---
app = Flask(__name__)
# Allow CORS for your frontend URL for local testing/Render deployment
ALLOWED_ORIGIN = "https://connecthub-xpy1.onrender.com"
# ...
CORS(app, resources={r"/api/*": {
    "origins": [ALLOWED_ORIGIN], # 👈 Use a list for robustness
    "methods": ["GET", "POST", "OPTIONS"] # 👈 CRITICAL: Allows the preflight check
}})

# --- Core Email Sending Function (Reused) ---
def send_otp_email(receiver_email, otp_code):
    """Sends the OTP email using the validated configuration."""
    
    subject = "ConnectHub OTP Verification Code"
    body = (
        f"Your One-Time Password (OTP) is: {otp_code}\n\n"
        f"This code is valid for {OTP_EXPIRY_SECONDS // 60} minutes. "
        "Please use it to complete your verification.\n\n"
        "If you did not request this code, please ignore this email."
    )
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    msg.set_content(body)
    
    context = ssl.create_default_context()
    
    try:
        if SMTP_PORT == 465:
            # Use smtplib.SMTP_SSL for Port 465 (direct SSL connection)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        else: # Default to 587 (STARTTLS)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        return True, "OTP email sent successfully."
    except Exception as e:
        print(f"!!! SMTP Error during OTP send: {e} !!!")
        return False, "Failed to send OTP email due to authentication or connection failure."

# --- API Endpoints ---

@app.route('/api/generate-otp', methods=['POST'])
def generate_otp_endpoint():
    """Generates a new OTP, stores it, and sends it to the user's email."""
    if not request.is_json:
        return jsonify({"error": "Missing JSON in request"}), 400

    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Missing 'email' field"}), 400

    # 1. Generate OTP and Session ID
    otp_code = secrets.randbelow(900000) + 100000 # 6-digit number
    session_id = str(uuid.uuid4())
    expiry_time = time.time() + OTP_EXPIRY_SECONDS

    # 2. Store OTP in memory
    OTP_STORE[session_id] = {
        'otp': str(otp_code),
        'email': email,
        'expiry': expiry_time
    }

    # 3. Send the OTP via email
    success, message = send_otp_email(email, str(otp_code))

    if success:
        return jsonify({
            "status": "success",
            "message": "OTP sent to email.",
            "session_id": session_id,
            "expires_in_seconds": OTP_EXPIRY_SECONDS
        }), 200
    else:
        return jsonify({"status": "error", "message": message}), 500

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp_endpoint():
    """Verifies the user-provided OTP against the stored one."""
    if not request.is_json:
        return jsonify({"error": "Missing JSON in request"}), 400

    data = request.get_json()
    session_id = data.get('session_id')
    otp_code = data.get('otp_code')

    if not session_id or not otp_code:
        return jsonify({"error": "Missing 'session_id' or 'otp_code'"}), 400

    stored_otp_data = OTP_STORE.get(session_id)

    if not stored_otp_data:
        return jsonify({"status": "error", "message": "Invalid or expired session ID."}), 404

    # Check expiration
    if time.time() > stored_otp_data['expiry']:
        del OTP_STORE[session_id] # Clean up expired OTP
        return jsonify({"status": "error", "message": "OTP has expired. Please request a new one."}), 400

    # Check OTP match
    if otp_code == stored_otp_data['otp']:
        del OTP_STORE[session_id] # Consumed OTP should be removed
        return jsonify({"status": "success", "message": "OTP verified successfully."}), 200
    else:
        return jsonify({"status": "error", "message": "Invalid OTP code."}), 400

if __name__ == '__main__':
    # Ensure all required environment variables are set before starting
    if not all([SENDER_EMAIL, SENDER_PASSWORD]):
        print("!!! FATAL: SENDER_EMAIL or SENDER_PASSWORD not set. Cannot run. !!!")
    else:
        app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=False)