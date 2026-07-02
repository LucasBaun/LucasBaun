import base64
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

START_MARKER = "<!--SPOTIFY_START-->"
END_MARKER = "<!--SPOTIFY_END-->"
README_PATH = "README.md"


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
        payload = response.read().decode()

    import json

    data = json.loads(payload)
    if "access_token" not in data:
        raise RuntimeError(f"Failed to refresh Spotify token: {payload}")
    return data["access_token"]


def get_currently_playing(access_token: str):
    import json

    request = urllib.request.Request(
        "https://api.spotify.com/v1/me/player/currently-playing",
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


def build_widget(playback: dict | None) -> str:
    if not playback or not playback.get("item"):
        return (
            '<p align="center">\n'
            '  <img src="https://img.shields.io/badge/Spotify-Not_playing_right_now-1E2433?style=for-the-badge&logo=spotify&logoColor=1DB954"/>\n'
            "</p>"
        )

    track = playback["item"]
    name = track["name"]
    artists = ", ".join(artist["name"] for artist in track["artists"])
    url = track["external_urls"]["spotify"]
    album_art = track["album"]["images"][0]["url"] if track["album"]["images"] else ""

    album_img = (
        f'<img src="{album_art}" alt="Album art" width="64" height="64"/>'
        if album_art
        else ""
    )

    return (
        '<table align="center">\n'
        "  <tr>\n"
        f'    <td align="center" valign="middle">{album_img}</td>\n'
        '    <td align="left" valign="middle">\n'
        f'      <a href="{url}" target="_blank">\n'
        f"        <b>{name}</b><br/>\n"
        f"        <sub>{artists}</sub>\n"
        "      </a>\n"
        "    </td>\n"
        "  </tr>\n"
        "</table>"
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
    playback = get_currently_playing(access_token)
    widget = build_widget(playback)

    with open(README_PATH, encoding="utf-8") as file:
        readme = file.read()

    updated = update_readme(readme, widget)

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.write(updated)


if __name__ == "__main__":
    main()
