import requests
import pandas as pd
import spotipy
import time
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import os
from typing import List, Dict, Any
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

import streamlit as st
client_id = st.secrets["client_id"]
client_secret = st.secrets["client_secret"]
muso_api_key = st.secrets["muso_api_key"]


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SpotifyAPI:
    def __init__(self):
        self.client_id = st.secrets['client_id']
        self.client_secret = st.secrets['client_secret']
        self.auth_manager = SpotifyClientCredentials(client_id=self.client_id, client_secret=self.client_secret)
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    def get_playlist_tracks(self, playlist_url: str) -> List[Dict[str, str]]:
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        playlist_tracks = self.sp.playlist_tracks(playlist_id)

        track_dictionary = {}
        for item in playlist_tracks['items']:
            track_name = item['track']['name']
            track_dictionary[track_name] = {
                'artist': item['track']['artists'][0]['name'].lower().strip(),
                'release_date': item['track']['album']['release_date'],
                'album': item['track']['album']['name'].lower().strip(),
                'search_string': f"{item['track']['artists'][0]['name']} : {track_name}"
            }
        return track_dictionary

class MusoAPI:
    def __init__(self):
        self.api_key = st.secrets['muso_api_key']
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.developer.muso.ai/v4"
        self.relevante_kategorien = ["Composer", "Lyricist", "Co-Writer", "Primary Artist", "Producer", "Co-Producer"]
        self.unmatched_tracks = []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def search_track(self, keyword: str) -> Dict[str, Any]:
        search_data = {
            "keyword": keyword,
            "type": ["track"],
            "limit": 10
        }
        response = requests.post(
            f"{self.base_url}/search",
            headers=self.headers,
            json=search_data
        )
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_track_details(self, track_id: str) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/track/id/{track_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def process_track(self, track: str, track_info: Dict[str, str]) -> pd.DataFrame:
        search_results = self.search_track(track_info['search_string'])
        if not search_results["data"]["tracks"]["items"]:
            logger.warning(f"No track found for: {track}")
            self.unmatched_tracks.append({
                "track_name": track,
                "artist": track_info['artist']
            })
            return None

        found_match = False
        for potential_match in search_results["data"]["tracks"]["items"]:
            title_match = potential_match["title"].lower().strip() == track.lower().strip()
            album_match = potential_match["album"]["title"].lower().strip() == track_info['album'].lower().strip()

            if title_match and album_match:
                track_id = potential_match["id"]
                track_title = potential_match["title"]
                track_release_date = potential_match.get("releaseDate", "")
                track_popularity = potential_match.get("popularity", None)
                track_isrcs = ", ".join(potential_match.get("isrcs", []))
                album = potential_match.get("album", {})
                album_id = album.get("id", "")
                album_title = album.get("title", "")
                album_art = album.get("albumArt", "")
                artist_list = [artist["name"] for artist in potential_match.get("artists", [])]
                artists_combined = ", ".join(artist_list)

                track_details = self.get_track_details(track_id)
                credits = track_details["data"].get("credits", [])
                daten = []

                for eintrag in credits:
                    for credit_item in eintrag.get("credits", []):
                        rolle = credit_item.get("child", "")
                        if rolle in self.relevante_kategorien:
                            for person in credit_item.get("collaborators", []):
                                name = person.get("name", "Unbekannt")
                                daten.append({
                                    "Track": track_title,
                                    "Name": name,
                                    "Rolle": rolle,
                                    "track_id": track_id,
                                    "release_date": track_release_date,
                                    "popularity": track_popularity,
                                    "isrcs": track_isrcs,
                                    "album_title": album_title,
                                    "album_id": album_id,
                                    "album_art": album_art,
                                    "artists": artists_combined
                                })

                if daten:
                    df = pd.DataFrame(daten).drop_duplicates().sort_values(by=["Track", "Rolle", "Name"])
                    found_match = True
                    return df

        if not found_match:
            logger.warning(f"No matching track found for: {track}")
            self.unmatched_tracks.append({
                "track_name": track,
                "artist": track_info['artist']
            })
            return None

def process_credits(credits: List[Dict], track_title: str) -> pd.DataFrame:
    relevante_kategorien = ["Composer", "Lyricist", "Co-Writer", "Primary Artist", "Producer", "Co-Producer"]
    daten = []

    for eintrag in credits:
        for credit_item in eintrag.get("credits", []):
            rolle = credit_item.get("child", "")
            if rolle in relevante_kategorien:
                for person in credit_item.get("collaborators", []):
                    name = person.get("name", "Unbekannt")
                    daten.append({"Track": track_title, "Name": name, "Rolle": rolle})

    return pd.DataFrame(daten).drop_duplicates().sort_values(by=["Track", "Rolle", "Name"])

def format_final_results(df: pd.DataFrame, unmatched_tracks: List[Dict[str, str]] = None) -> pd.DataFrame:
    writer_roles = ["Composer", "Lyricist", "Co-Writer"]
    producer_roles = ["Producer", "Co-Producer"]
    final_rows = []

    # Process matched tracks
    for track_title in df["Track"].unique():
        track_data = df[df["Track"] == track_title]
        artist_rows = track_data[track_data["Rolle"] == "Primary Artist"]
        artist_list = artist_rows["Name"].unique().tolist()
        artist = ", ".join(artist_list) if artist_list else ""
        writers = track_data[track_data["Rolle"].isin(writer_roles)]["Name"].unique().tolist()
        producers = track_data[track_data["Rolle"].isin(producer_roles)]["Name"].unique().tolist()

        row = {
            "Song": track_title,
            "Artist": artist
        }

        # Add writers
        for i, writer in enumerate(writers, start=1):
            row[f"Writer {i}"] = writer

        # Add producers
        for i, producer in enumerate(producers, start=1):
            row[f"Producer {i}"] = producer

        final_rows.append(row)

    # Add unmatched tracks
    if unmatched_tracks:
        for track_info in unmatched_tracks:
            row = {
                "Song": track_info["track_name"],
                "Artist": track_info["artist"]
            }
            final_rows.append(row)

    # Create DataFrame and ensure all columns exist
    result_df = pd.DataFrame(final_rows)

    # Add empty writer and producer columns if they don't exist
    max_writers = max([len(row.get("Writer", [])) for row in final_rows if "Writer" in row], default=0)
    max_producers = max([len(row.get("Producer", [])) for row in final_rows if "Producer" in row], default=0)

    for i in range(1, max_writers + 1):
        if f"Writer {i}" not in result_df.columns:
            result_df[f"Writer {i}"] = ""

    for i in range(1, max_producers + 1):
        if f"Producer {i}" not in result_df.columns:
            result_df[f"Producer {i}"] = ""

    return result_df

def main():
    try:
        # Initialize APIs
        spotify_api = SpotifyAPI()
        muso_api = MusoAPI()

        # Get playlist tracks
        playlist_url = "https://open.spotify.com/playlist/3K0LuUqyUCRGKDBIhmJNm3"
        tracks_to_search = spotify_api.get_playlist_tracks(playlist_url)

        all_results = []
        total_tracks = len(tracks_to_search)

        for idx, track_info in enumerate(tracks_to_search.items(), 1):
            track = track_info[0]
            logger.info(f"Processing track {idx}/{total_tracks}: {track}")

            try:
                # Process track
                df = muso_api.process_track(track, track_info[1])
                if df is None:
                    continue
                all_results.append(df)

                time.sleep(2)  # Rate limiting

            except Exception as e:
                logger.error(f"Error processing track {track}: {str(e)}")
                continue

        if not all_results:
            logger.warning("No track credits loaded. Please try again later.")
            return

        # Combine and format results
        final_df = pd.concat(all_results, ignore_index=True)
        formatted_df = format_final_results(final_df, muso_api.unmatched_tracks)

        # Save results
        formatted_df.to_csv("playlist_credits_formatted.csv", index=False)
        final_df.to_csv("playlist_credits.csv", index=False)

        logger.info("Successfully saved results to CSV files")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
