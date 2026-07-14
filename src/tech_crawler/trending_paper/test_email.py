import base64
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import the authentication logic from the existing script
from tech_crawler.trending_paper.send_email import get_gmail_credentials, setup_logging

LOGGER = logging.getLogger(__name__)


def build_test_email_message(sender: str, to: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Test Email from Tech Crawler"
    msg["From"] = sender
    msg["To"] = to

    # Build plain text content without any links
    text_content = (
        "Hello,\n\n"
        "This is a plain text test email sent from the Tech Crawler Gmail API integration.\n"
        "There are no links in this email.\n"
        "If you receive this, it means the Gmail API integration is working correctly and your email server accepts plain text messages from this sender.\n\n"
        "Best regards,\nTech Crawler Bot"
    )

    part1 = MIMEText(text_content, "plain")
    msg.attach(part1)

    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def send_test_email():
    setup_logging()
    load_dotenv()

    recipients_str = os.getenv("RECIPIENT_EMAILS")
    if not recipients_str:
        LOGGER.error("RECIPIENT_EMAILS environment variable is not set. Cannot send emails.")
        return

    recipients = [email.strip() for email in recipients_str.split(",") if email.strip()]
    if not recipients:
        LOGGER.error("No valid email addresses found in RECIPIENT_EMAILS.")
        return

    # Find root dir (assume script is in src/tech_crawler/trending_paper/)
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent.parent.parent

    try:
        creds = get_gmail_credentials(root_dir)
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        LOGGER.exception("Failed to initialize Gmail API service.")
        return

    try:
        # Get the authenticated user's email address
        profile = service.users().getProfile(userId="me").execute()
        sender_email = profile["emailAddress"]
    except Exception:
        LOGGER.warning("Could not determine sender email, defaulting to 'me'")
        sender_email = "me"

    for recipient in recipients:
        LOGGER.info("Sending TEST email to %s...", recipient)
        message = build_test_email_message(sender_email, recipient)
        try:
            sent_message = service.users().messages().send(userId="me", body=message).execute()
            LOGGER.info("Test message sent successfully to %s. Message ID: %s", recipient, sent_message["id"])
        except HttpError as error:
            LOGGER.error("An error occurred while sending test email to %s: %s", recipient, error)


if __name__ == "__main__":
    send_test_email()
