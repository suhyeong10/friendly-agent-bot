import os
import logging
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Spotify",
    instructions="You are a Spotify API client. You can search for songs and playlists.",
    host="0.0.0.0",
    port=8007
)

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
    )
)

## Spotify API
def get_tracks_by_query(query: str, limit: int = 3) -> list:
    found_tracks = {}

    try:
        playlists = sp.search(q=query, type="playlist", limit=limit)["playlists"]["items"]

        for pl in playlists:
            try:
                tracks = sp.playlist_tracks(pl["id"], limit=10)["items"]
                for item in tracks:
                    if not isinstance(item, dict):
                        continue  # None 이거나 이상한 형식이면 무시

                    track = item.get("track", {})
                    if not isinstance(track, dict):
                        continue  # track이 None일 수도 있음

                    track_id = track.get("id")
                    if not track_id:
                        continue

                    if track_id not in found_tracks:
                        name = track.get("name", "Unknown Title")
                        artists = track.get("artists", [])
                        artist_name = artists[0]["name"] if artists else "Unknown Artist"
                        url = track.get("external_urls", {}).get("spotify", "")

                        found_tracks[track_id] = {
                            "name": name,
                            "artist": artist_name,
                            "url": url
                        }

            except Exception as e:
                logger.warning(f"[⚠️ Playlist 처리 중 오류] {pl.get('name', 'unknown')}: {e}")

    except Exception as e:
        logger.error(f"[❗Spotify 추천 실패] {query}: {e}")

    result = list(found_tracks.values())[:limit]
    logger.info(f"[🎵 추천된 노래 {len(result)}곡] 쿼리: {query} → {result}")

    return result

@mcp.tool()
def get_song_rec_tool(query: str) -> str:
    """
    Returns a list of recommended songs from Spotify based on the user's search query.

    Args:
        query: the keyword or phrase to search for relevant songs on Spotify. query is must be korean.
    """
    result = get_tracks_by_query(query, limit=5)
    result = '\n'.join([
        f"제목: {item['name']}, 아티스트: {item['artist']}, URL: {item['url']}" for item in result
    ])

    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")
