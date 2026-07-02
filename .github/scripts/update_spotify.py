import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.sax.saxutils

START_MARKER = "<!--SPOTIFY_START-->"
END_MARKER = "<!--SPOTIFY_END-->"
README_PATH = "README.md"
SVG_PATH = "assets/spotify-card.svg"
CARD_WIDTH = 440
CARD_HEIGHT = 100


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
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

    if "access_token" not in data:
        raise RuntimeError(f"Failed to refresh Spotify token: {data}")
    return data["access_token"]


def spotify_get(access_token: str, url: str):
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    try:
        with urllib.request.urlopen(request) as response:
            if response.status == 204:
                return None
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code == 204:
            return None
        raise


def get_currently_playing(access_token: str):
    return spotify_get(
        access_token,
        "https://api.spotify.com/v1/me/player/currently-playing",
    )


def get_recently_played(access_token: str):
    data = spotify_get(
        access_token,
        "https://api.spotify.com/v1/me/player/recently-played?limit=1",
    )
    if not data or not data.get("items"):
        return None
    return data["items"][0]["track"]


def fetch_image_base64(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response:
        content_type = response.headers.get_content_type()
        encoded = base64.b64encode(response.read()).decode()
    return f"data:{content_type};base64,{encoded}"


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def escape_xml(text: str) -> str:
    return xml.sax.saxutils.escape(text)


def build_card_svg(status: str, track_name: str, artist: str, album_art_url: str) -> str:
    title = escape_xml(truncate(track_name, 28))
    artists = escape_xml(truncate(artist, 32))
    label = escape_xml(status.upper())

    album_href = ""
    if album_art_url:
        try:
            album_href = fetch_image_base64(album_art_url)
        except urllib.error.URLError:
            album_href = ""

    album_block = ""
    if album_href:
        album_block = f"""
  <image href="{album_href}" x="14" y="14" width="72" height="72" clip-path="url(#albumClip)" preserveAspectRatio="xMidYMid slice"/>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#6d28d9"/>
      <stop offset="45%" stop-color="#3a8f8a"/>
      <stop offset="100%" stop-color="#1e2433"/>
    </linearGradient>
    <radialGradient id="glow" cx="70%" cy="100%" r="60%">
      <stop offset="0%" stop-color="#ff6600" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#ff6600" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="albumClip">
      <rect x="14" y="14" width="72" height="72" rx="12"/>
    </clipPath>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.25"/>
    </filter>
  </defs>
  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="22" fill="url(#bg)" filter="url(#shadow)"/>
  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="22" fill="url(#glow)"/>{album_block}
  <text x="100" y="30" fill="rgba(255,255,255,0.72)" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10" font-weight="600" letter-spacing="1.4">{label}</text>
  <text x="100" y="54" fill="#ffffff" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="17" font-weight="700">{title}</text>
  <text x="100" y="76" fill="rgba(255,255,255,0.88)" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="500">{artists}</text>
</svg>
"""


def build_empty_card_svg() -> str:
    return build_card_svg("Spotify", "Nothing played yet", "Connect your account", "")


def resolve_track(access_token: str) -> tuple[str, dict] | None:
    playback = get_currently_playing(access_token)
    if playback and playback.get("item") and playback.get("is_playing"):
        return "Currently listening to", playback["item"]

    recent = get_recently_played(access_token)
    if recent:
        return "Last played", recent

    if playback and playback.get("item"):
        return "Last played", playback["item"]

    return None


def build_widget(track_url: str) -> str:
    return (
        '<p align="center">\n'
        f'  <a href="{track_url}" target="_blank">\n'
        '    <img src="https://raw.githubusercontent.com/LucasBaun/LucasBaun/main/assets/spotify-card.svg" alt="Spotify now playing"/>\n'
        "  </a>\n"
        "</p>"
    )


def update_readme(content: str, widget: str) -> str:
    block = f"{START_MARKER}\n{widget}\n{END_MARKER}"
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    if not pattern.search(content):
        raise RuntimeError("Spotify markers not found in README.md")

    return pattern.sub(block, content)


def main() -> None:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("Missing Spotify secrets.", file=sys.stderr)
        sys.exit(1)

    access_token = get_access_token(client_id, client_secret, refresh_token)
    resolved = resolve_track(access_token)

    if resolved:
        status, track = resolved
        track_name = track["name"]
        artists = ", ".join(artist["name"] for artist in track["artists"])
        track_url = track["external_urls"]["spotify"]
        album_art = track["album"]["images"][0]["url"] if track["album"]["images"] else ""
        svg = build_card_svg(status, track_name, artists, album_art)
        widget = build_widget(track_url)
    else:
        svg = build_empty_card_svg()
        widget = (
            '<p align="center">\n'
            '  <img src="https://raw.githubusercontent.com/LucasBaun/LucasBaun/main/assets/spotify-card.svg" alt="Spotify"/>\n'
            "</p>"
        )

    os.makedirs(os.path.dirname(SVG_PATH), exist_ok=True)
    with open(SVG_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.write(svg)

    with open(README_PATH, encoding="utf-8") as file:
        readme = file.read()

    updated = update_readme(readme, widget)

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.write(updated)


if __name__ == "__main__":
    main()
