import base64
import json
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import markdown
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

LOGGER = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def decode_env_json(env_value: str | None) -> str | None:
    if not env_value:
        return None
    env_value = env_value.strip()
    # Check if it's base64 encoded by trying to decode it
    if env_value.startswith("{") and env_value.endswith("}"):
        return env_value
    try:
        decoded = base64.b64decode(env_value).decode("utf-8")
        # Validate it's JSON
        json.loads(decoded)
        return decoded
    except Exception:
        pass
    # If not base64 or valid json inside base64, assume it might be raw json but failed to parse, or invalid.
    return env_value


def get_gmail_credentials(root_dir: Path):
    creds = None
    token_path = root_dir / "token.json"
    credentials_path = root_dir / "credentials.json"

    env_token = decode_env_json(os.getenv("GMAIL_TOKEN_JSON"))
    env_creds = decode_env_json(os.getenv("GMAIL_CREDENTIALS_JSON"))

    # Try loading token from env or file
    if env_token:
        try:
            token_info = json.loads(env_token)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception:
            LOGGER.exception("Failed to load token from GMAIL_TOKEN_JSON environment variable.")
    elif token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            LOGGER.exception("Failed to load token from %s", token_path)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            LOGGER.info("Refreshing expired token...")
            creds.refresh(Request())
        else:
            LOGGER.info("No valid token found, initiating OAuth flow...")
            flow = None
            if env_creds:
                try:
                    client_config = json.loads(env_creds)
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                except Exception:
                    LOGGER.exception("Failed to initialize OAuth flow from GMAIL_CREDENTIALS_JSON.")
            if not flow and credentials_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            
            if not flow:
                raise RuntimeError(
                    "Missing Gmail API credentials. Provide credentials.json file or GMAIL_CREDENTIALS_JSON env var."
                )

            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
            LOGGER.info("Saved new token to %s", token_path)

    return creds


def get_latest_trending_dir(root_dir: Path) -> Path | None:
    trending_dir = root_dir / "data" / "papers" / "trending"
    if not trending_dir.exists():
        return None
    
    # Exclude files like trending_papers.txt, look for YYYY-Www directories
    directories = [d for d in trending_dir.iterdir() if d.is_dir() and "-W" in d.name]
    if not directories:
        return None
    
    # Sort by name (e.g., 2026-W28, 2026-W29)
    directories.sort(key=lambda d: d.name, reverse=True)
    return directories[0]


def get_summaries(latest_dir: Path) -> list[tuple[str, str]]:
    summaries = []
    for md_file in latest_dir.glob("*.md"):
        title = md_file.stem
        content = md_file.read_text(encoding="utf-8")
        summaries.append((title, content))
    return summaries


def build_email_message(sender: str, to: str, summaries: list[tuple[str, str]], week_name: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Trending Papers Summary ({week_name})"
    msg["From"] = sender
    msg["To"] = to

    # Build plain text content
    text_content = f"Trending Papers Summary for {week_name}\n\n"
    for title, content in summaries:
        text_content += f"=== {title} ===\n\n{content}\n\n"

    # Build HTML content
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          h1 {{ color: #2c3e50; }}
          h2 {{ color: #34495e; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
          .paper {{ margin-bottom: 40px; padding: 20px; background: #f9f9f9; border-radius: 8px; }}
          .paper h3 {{ color: #16a085; margin-top: 0; }}
        </style>
      </head>
      <body>
        <h1>Trending Papers Summary ({week_name})</h1>
    """

    for title, content in summaries:
        html_content += f'<div class="paper">'
        html_content += f'<h3>{title}</h3>'
        html_content += markdown.markdown(content, extensions=["extra"])
        html_content += f'</div>'

    html_content += """
      </body>
    </html>
    """

    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")

    msg.attach(part1)
    msg.attach(part2)

    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def send_email():
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

    latest_dir = get_latest_trending_dir(root_dir)
    if not latest_dir:
        LOGGER.info("No trending paper directories found.")
        return

    week_name = latest_dir.name
    LOGGER.info("Found latest trending directory: %s", week_name)

    summaries = get_summaries(latest_dir)
    if not summaries:
        LOGGER.info("No summaries found in %s", latest_dir)
        return

    LOGGER.info("Found %d summaries. Constructing email...", len(summaries))

    try:
        # Get the authenticated user's email address
        profile = service.users().getProfile(userId="me").execute()
        sender_email = profile["emailAddress"]
    except Exception:
        LOGGER.warning("Could not determine sender email, defaulting to 'me'")
        sender_email = "me"

    for recipient in recipients:
        LOGGER.info("Sending email to %s...", recipient)
        message = build_email_message(sender_email, recipient, summaries, week_name)
        try:
            sent_message = service.users().messages().send(userId="me", body=message).execute()
            LOGGER.info("Message sent successfully. Message ID: %s", sent_message["id"])
        except HttpError as error:
            LOGGER.error("An error occurred while sending email to %s: %s", recipient, error)


if __name__ == "__main__":
    send_email()
