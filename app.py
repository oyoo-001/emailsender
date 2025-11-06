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
ADMIN_EMAIL = "oyoookoth42@gmail.com"
try:
    SMTP_PORT = int(SMTP_PORT_STR)
except ValueError:
    SMTP_PORT = 587
    print(f"Warning: SMTP_PORT is invalid, defaulting to {SMTP_PORT}")

# In-memory store for OTPs: {session_id: {'otp': '123456', 'email': 'user@example.com', 'expiry': 1678886400}}
OTP_STORE = {}
OTP_EXPIRY_SECONDS = 300  # 5 minutes

# --- Flask App Initialization ---
app = Flask(__name__)
# Allow CORS for your frontend URL for local testing/Render deployment
ALLOWED_ORIGIN = "https://connecthub-xpy1.onrender.com"
# Correct CORS Configuration:
# 1. CORS is applied to all routes under /api/*.
# 2. It explicitly allows the necessary methods (POST, GET, OPTIONS).
# 3. flask-cors will automatically handle the OPTIONS (preflight) request and inject headers.
CORS(app, resources={r"/api/*": {
    "origins": [ALLOWED_ORIGIN], 
    "methods": ["GET", "POST", "OPTIONS"] 
}})

# --- Core Email Sending Function (Reused) ---
def send_otp_email(receiver_email, otp_code):
    """Sends a professional OTP email using validated configuration."""

    subject = "ConnectHub OTP Verification Code"
    body = (
        f"Dear User,\n\n"
        f"Your One-Time Password (OTP) is: {otp_code}\n\n"
        f"This code will expire in {OTP_EXPIRY_SECONDS // 60} minutes. "
        f"Please use it to complete your verification process.\n\n"
        f"If you did not request this verification code, kindly disregard this email.\n\n"
        f"Best regards,\n"
        f"ConnectHub Security Team\n"
        f"no-reply@connecthub.com"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"ConnectHub  <{SENDER_EMAIL}>"
    msg["To"] = receiver_email
    msg.set_content(body)

    context = ssl.create_default_context()

    try:
        if SMTP_PORT == 465:
            # Use smtplib.SMTP_SSL for Port 465 (direct SSL connection)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        else:
            # Use smtplib.SMTP with STARTTLS for Port 587
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

# --- NEW: AI Assistant Endpoint ---
@app.route('/api/send-response', methods=['POST']) # 💥 FIX: Removed 'OPTIONS' here
def send_support_ticket():
    # 💥 FIX: Removed the manual check "if request.method == 'OPTIONS': return '', 200"
    # flask-cors middleware handles the OPTIONS request for us now.
    
    try:
        data = request.get_json()
        
        # 1. Extract required data from the frontend POST request
        user_id = data.get('userId')
        username = data.get('username')
        user_email = data.get('receiver') 
        concern = data.get('message')
        if not all([username, user_email, concern]):
            return jsonify({'success': False, 'message': 'Missing required fields (username, email, or concern).'}), 400

        # --- 2. Send Notification Email to Admin ---
        msg_admin = EmailMessage()
        msg_admin['Subject'] = f"New Support Ticket from {username}"
        msg_admin['From'] = SENDER_EMAIL
        msg_admin['To'] = ADMIN_EMAIL
        
        admin_body = f"""
        A new support ticket has been submitted:
        
        User ID: {user_id}
        Username: {username}
        Email: {user_email}
        
        Concern:
        {concern}
        
        Please address this issue promptly.
        """
        msg_admin.set_content(admin_body)

        # --- 3. Send Confirmation Email to User ---
        msg_user = EmailMessage()
        msg_user['Subject'] = "ConnectHub: We have received your support request"
        msg_user['From'] = SENDER_EMAIL
        msg_user['To'] = user_email
        
        user_body = f"""
        Dear {username},

        We have successfully received your support request regarding the following concern:

        "{concern[:100]}..." 
        
        Our team will review your message and get back to you as soon as possible.
        
        Thank you for your patience,
        The ConnectHub Team
        """
        msg_user.set_content(user_body)
        
        # --- 4. Send Emails via SMTP ---
        # Note: Using hardcoded port 465 here. If you use 587 or another port, 
        # ensure you use the logic from send_otp_email for starttls.
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg_admin)
            smtp.send_message(msg_user)

        # The Python server successfully handled the emails
        return jsonify({'success': True, 'message': 'Support ticket received and emails sent successfully.'}), 200

    except Exception as e:
        print(f"Error handling /api/send-response (Support Ticket): {e}")
        return jsonify({'success': False, 'message': 'Internal email service error.'}), 500

if __name__ == '__main__':
    # Ensure all required environment variables are set before starting
    if not all([SENDER_EMAIL, SENDER_PASSWORD]):
        print("!!! FATAL: SENDER_EMAIL or SENDER_PASSWORD not set. Cannot run. !!!")
    else:
        app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=False)