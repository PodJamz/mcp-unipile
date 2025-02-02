from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
import json
import requests
from .server import UnipileWrapper
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()  # Load environment variables from .env file

app = FastAPI()

UNIPILE_DSN = os.getenv("UNIPILE_DSN")
UNIPILE_API_KEY = os.getenv("UNIPILE_API_KEY")

class EmailRequest(BaseModel):
    account_id: str
    subject: str
    body: str
    to: list
    cc: list = None
    bcc: list = None


logger = logging.getLogger(__name__)
unipile = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global unipile
    dsn = os.getenv("UNIPILE_DSN")
    api_key = os.getenv("UNIPILE_API_KEY")
    if not dsn or not api_key:
        raise RuntimeError("Missing UNIPILE_DSN or UNIPILE_API_KEY environment variables")
    unipile = UnipileWrapper(dsn=dsn, api_key=api_key)
    yield  # Application runs here
    # (Optional shutdown code can go here)

app = FastAPI(lifespan=lifespan, title="Unipile MCP HTTP API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/tools/unipile_get_accounts")
async def get_accounts():
    """Retrieve all connected accounts."""
    try:
        data = json.loads(unipile.get_accounts())
        return {"data": data}
    except Exception as e:
        logger.error(f"Error getting accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/unipile_reply_email")
async def reply_email(request: EmailRequest, reply_to: str, attachment: UploadFile = File(None)):
    """Reply to an email with optional attachment."""
    try:
        url = f"https://{UNIPILE_DSN}/api/v1/emails"
        headers = {
            'X-API-KEY': UNIPILE_API_KEY,
            'accept': 'application/json'
        }
        data = {
            'account_id': request.account_id,
            'subject': request.subject,
            'body': request.body,
            'to': json.dumps(request.to),
            'reply_to': reply_to
        }
        files = {'attachments': (attachment.filename, attachment.file)} if attachment else None

        response = requests.post(url, headers=headers, data=data, files=files)
        response.raise_for_status()

        return {"message": "Reply sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/tools/unipile_send_email")
async def send_email(request: Request):
    """Send an email via Unipile."""
    try:
        payload = await request.json()  # <-- Explicitly parse JSON
        url = f"https://{UNIPILE_DSN}/api/v1/emails"
        headers = {
            "X-API-KEY": UNIPILE_API_KEY,
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        response = requests.post(url, headers=headers, json=payload)  # <-- Ensure correct JSON format
        response.raise_for_status()
        return {"message": "Email sent successfully", "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))   

@app.post("/tools/unipile_get_recent_messages")
async def get_recent_messages(account_id: str, batch_size: int = 20):
    """Retrieve recent messages for an account."""
    try:
        data = json.loads(unipile.get_all_messages(account_id=account_id, limit=batch_size))
        return {"data": data}
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/unipile_get_emails")
async def get_emails(account_id: str, limit: int = 10):
    """Retrieve emails for an account and clean up response."""
    try:
        raw_data = json.loads(unipile.get_emails(account_id=account_id, limit=limit))
        emails = [
            {
                "id": email.get("id"),
                "subject": email.get("subject"),
                "date": email.get("date"),
                "from": email.get("from_attendee", {}).get("email"),
                "body": email.get("body_markdown", "").strip(),
            }
            for email in raw_data
        ]
        return {"emails": emails}
    except Exception as e:
        logger.error(f"Error getting emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 