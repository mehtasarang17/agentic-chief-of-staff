"""Generate a Google Calendar refresh token for local setup."""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main() -> None:
    client_id = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise SystemExit("Set GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET first.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    redirect_uri = "http://localhost:8080/"
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES, redirect_uri=redirect_uri)
    auth_url, _ = flow.authorization_url(prompt="consent")
    print("Open this URL in your browser:\n")
    print(auth_url)
    print("\nAfter approving, you'll be redirected to localhost:8080 with a code in the URL.")
    print("Copy the value of the `code` parameter from the URL and paste it here.")
    code = input("\nPaste the authorization code here: ").strip()
    flow.fetch_token(code=code)
    creds = flow.credentials

    print("\nRefresh token:")
    print(creds.refresh_token)
    print("\nSet this in your .env as GOOGLE_CALENDAR_REFRESH_TOKEN.")


if __name__ == "__main__":
    main()
