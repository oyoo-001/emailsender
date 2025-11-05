import smtplib
from email.message import EmailMessage
import ssl
import os
from dotenv import load_dotenv  # <-- New Import

# --- Load Environment Variables ---
# This line looks for the .env file in the current directory and loads its contents
load_dotenv() 

# --- Configuration (Loaded from .env) ---
# Use os.getenv() to securely retrieve variables
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# Other variables remain in the script for now
RECEIVER_EMAIL = "user_to_respond_to@example.com"
SUBJECT = "Your Inquiry Response"
BODY = "Hello,\n\nThank you for reaching out to us. We have received your message and will follow up shortly.\n\nBest Regards,\nThe Automated Assistant"

# --- 1. Construct the Message ---
msg = EmailMessage()
msg['Subject'] = SUBJECT
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL
msg.set_content(BODY)

# --- 2. Establish Secure Connection & Send ---
context = ssl.create_default_context()

print("Attempting to connect to SMTP server...")
try:
    # Use the variables loaded from .env
    with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT)) as server: 
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()

        # Log in
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        print("Successfully logged in.")

        # Send the mail
        server.send_message(msg)
        print(f"Success! Email sent to {RECEIVER_EMAIL}")

except Exception as e:
    print(f"An error occurred: {e}")
    print("Please check your .env file, App Password, and network connection.")