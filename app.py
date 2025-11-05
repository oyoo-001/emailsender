import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.message import EmailMessage
import ssl

# Load environment variables from .env file (for local testing)
load_dotenv()

# --- Configuration Loading with Safety Checks (CRITICAL) ---

# Get values, but keep SMTP_PORT as string for now
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT_STR = os.getenv("SMTP_PORT")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# 1. Check for missing environment variables
required_vars = [SMTP_HOST, SMTP_PORT_STR, SENDER_EMAIL, SENDER_PASSWORD]
if not all(required_vars):
    missing = [name for name, val in zip(["SMTP_HOST", "SMTP_PORT", "SENDER_EMAIL", "SENDER_PASSWORD"], required_vars) if not val]
    print(f"!!! FATAL CONFIGURATION ERROR !!! Missing required environment variables: {', '.join(missing)}")
    # This explicit crash ensures Render logs show WHICH variable is missing.
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}. Check Render settings.")

# 2. Safely convert port to integer
try:
    SMTP_PORT = int(SMTP_PORT_STR)
except ValueError:
    print("!!! FATAL CONFIGURATION ERROR !!! SMTP_PORT must be a valid integer.")
    raise ValueError("SMTP_PORT is not a valid integer. Check Render settings.")
print(f"--- RENDER ENV DEBUG --- Password Length: {len(SENDER_PASSWORD)}, Start: {SENDER_PASSWORD[:5]}, End: {SENDER_PASSWORD[-5:]}")
# --- Flask App Initialization & CORS ---
app = Flask(__name__)

# CRITICAL: Configure CORS to ONLY allow your ConnectHub website
ALLOWED_ORIGIN = "https://connecthub-xpy1.onrender.com"
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})

# --- Core Email Sending Function ---
def send_automated_email(receiver_email, subject, body):
    """Handles the actual sending logic using credentials from environment variables."""
    
    # 1. Construct the message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    msg.set_content(body)
    
    # 2. Prepare for secure connection
    context = ssl.create_default_context()
    
    # 3. Attempt to connect and send
    try:
        # Using smtplib.SMTP_SSL for direct SSL connection (Port 465)
        with smtplib.SMTP_SSL(SMTP_HOST, 465, context=context) as server: 
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        return True, "Email sent successfully."
    except Exception as e:
        print(f"!!! SMTP Error during send: {e} !!!")
        return False, f"Failed to send email due to authentication or connection failure."


# --- Flask Route (The API Endpoint) ---
@app.route('/api/send-response', methods=['POST'])
def handle_email_request():
    if not request.is_json:
        return jsonify({"error": "Missing JSON in request"}), 400

    data = request.get_json()
    receiver = data.get('receiver')
    user_message = data.get('message')
    
    if not receiver or not user_message:
        return jsonify({"error": "Missing 'receiver' or 'message' fields in request data"}), 400

    # Automated Response Body
    response_subject = "ConnectHub: Your Inquiry Has Been Received"
    response_body = (
        f"Dear User,\n\n"
        f"Thank you for contacting us. Your message (starting with: '{user_message[:50]}...') "
        f"has been received by our assistant. We will review your full message and respond personally soon.\n\n"
        f"Best Regards,\nThe ConnectHub Assistant"
    )
    
    # Execute Sending
    success, message = send_automated_email(receiver, response_subject, response_body)
    
    if success:
        return jsonify({"status": "success", "details": message}), 200
    else:
        # Returns the 500 status on SMTP failure
        return jsonify({"status": "error", "details": message}), 500
#testpoint
@app.route('/api/status')
def status_check():
    """Simple status check endpoint for Render environment verification."""
    safe_status = {
        "status": "running ✅",
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "SENDER_EMAIL": SENDER_EMAIL,
        "env_loaded": all([SMTP_HOST, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD])
    }
    return jsonify(safe_status), 200


if __name__ == '__main__':
    # Use os.environ.get('PORT', ...) for better compatibility with Render environments
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=False)