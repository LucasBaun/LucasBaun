#!/usr/bin/env python3
"""
Run locally once to get your Spotify refresh token.

Usage:
  set SPOTIFY_CLIENT_ID=your_client_id
  set SPOTIFY_CLIENT_SECRET=your_client_secret
  python scripts/get_spotify_token.py
"""

import base64
import json
import os
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIRECT_URI = "http://127.0.0.1:8080/callback"
SCOPES = "user-read-currently-playing user-read-playback-state user-read-recently-played"
PORT = 8080


class CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            CallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<h2>Spotify connected.</h2><p>You can close this tab and return to the terminal.</p>"
            )
            return

        self.send_response(400)
        self.end_headers()

    def log_message(self, format, *args):
        return


def main() -> None:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise SystemExit("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first.")

    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        }
    )
    auth_url = f"https://accounts.spotify.com/authorize?{params}"

    print("Opening Spotify login in your browser...")
    print(f"If it does not open automatically, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(("127.0.0.1", PORT), CallbackHandler)
    server.handle_request()

    if not CallbackHandler.auth_code:
        raise SystemExit("No authorization code received.")

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": CallbackHandler.auth_code,
            "redirect_uri": REDIRECT_URI,
        }
    ).encode()

    request = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode())

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise SystemExit(f"Could not get refresh token: {data}")

    print("\nSuccess! Add this as a GitHub secret named SPOTIFY_REFRESH_TOKEN:\n")
    print(refresh_token)
    print("\nAlso add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET as GitHub secrets.")


if __name__ == "__main__":
    main()
