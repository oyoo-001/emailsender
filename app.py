import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS  # <-- New Import for CORS
import smtplib
from email.message import EmailMessage
import ssl

# Load environment variables from .env file
load_dotenv()

# --- Configuration Loading ---
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT")) # Ensure port is an integer
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# --- Flask App Initialization ---
app = Flask(__name__)

# ---------------------------------------------------------------------
# CRITICAL: Configure CORS to ONLY allow your ConnectHub website to access this API.
ALLOWED_ORIGIN = "https://connecthub-xpy1.onrender.com"
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})
# ---------------------------------------------------------------------

# --- Core Email Sending Function ---
def send_automated_email(receiver_email, subject, body):
    """Handles the actual sending logic using credentials from .env"""
    
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
        # Use smtplib.SMTP for port 587 and STARTTLS
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        return True, "Email sent successfully."
    except Exception as e:
        # Log the detailed error for debugging (this will appear in your server console)
        print(f"SMTP Error: {e}")
        # Return a sanitized error message to the frontend
        return False, f"Failed to send email due to server misconfiguration."


# --- Flask Route (The API Endpoint) ---
@app.route('/api/send-response', methods=['POST'])
def handle_email_request():
    # Ensure the request is JSON
    if not request.is_json:
        return jsonify({"error": "Missing JSON in request"}), 400

    data = request.get_json()
    
    # Extract necessary data from the incoming JSON request
    # These keys MUST match the payload sent by the frontend: { "receiver": ..., "message": ... }
    receiver = data.get('receiver')
    user_message = data.get('message')
    
    if not receiver or not user_message:
        return jsonify({"error": "Missing 'receiver' or 'message' fields in request data"}), 400

    # --- Automated Response Body ---
    response_subject = "ConnectHub: Your Inquiry Has Been Received"
    # Create an automated body, echoing a snippet of the user's message
    response_body = (
        f"Dear User,\n\n"
        f"Thank you for contacting us. Your message (starting with: '{user_message[:50]}...') "
        f"has been received by our assistant. We will review your full message and respond personally soon.\n\n"
        f"Best Regards,\nThe ConnectHub Assistant"
    )
    
    # --- Execute Sending ---
    success, message = send_automated_email(receiver, response_subject, response_body)
    
    if success:
        # Success status 200
        return jsonify({"status": "success", "details": message}), 200
    else:
        # Server-side error status 500
        return jsonify({"status": "error", "details": message}), 500


if __name__ == '__main__':
    # You MUST set debug=False when deploying to a public server!
    app.run(host='0.0.0.0', port=5000, debug=False)