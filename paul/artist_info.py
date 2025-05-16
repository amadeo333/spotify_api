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

        tracks_to_search = []
        for item in playlist_tracks['items']:
            track_name = item['track']['name']
            artist_name = item['track']['artists'][0]['name']
            tracks_to_search.append({
                'track_name': track_name,
                'artist_name': artist_name,
                'full_query': f"{track_name} {artist_name}"
            })
        return tracks_to_search

class MusoAPI:
    def __init__(self):
        self.api_key = st.secrets['muso_api_key']
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.developer.muso.ai/v4"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def search_track(self, keyword: str) -> Dict[str, Any]:
        search_data = {
            "keyword": keyword,
            "type": ["track"],
            "limit": 1
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

def format_final_results(df: pd.DataFrame) -> pd.DataFrame:
    writer_roles = ["Composer", "Lyricist", "Co-Writer"]
    producer_roles = ["Producer", "Co-Producer"]
    final_rows = []

    for track_title in df["Track"].unique():
        track_data = df[df["Track"] == track_title]

        artist_rows = track_data[track_data["Rolle"] == "Primary Artist"]
        artist_list = artist_rows["Name"].unique().tolist()
        artist = ", ".join(artist_list) if artist_list else "Unbekannt"

        writers = track_data[track_data["Rolle"].isin(writer_roles)]["Name"].unique().tolist()
        producers = track_data[track_data["Rolle"].isin(producer_roles)]["Name"].unique().tolist()

        row = {"Titel": track_title, "Artist": artist}
        for i, writer in enumerate(writers, start=1):
            row[f"Writer {i}"] = writer
        for i, producer in enumerate(producers, start=1):
            row[f"Producer {i}"] = producer

        final_rows.append(row)

    return pd.DataFrame(final_rows)

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

        for idx, track_info in enumerate(tracks_to_search, 1):
            logger.info(f"Processing track {idx}/{total_tracks}: {track_info['full_query']}")

            try:
                # Search track
                search_results = muso_api.search_track(track_info['full_query'])
                if not search_results["data"]["tracks"]["items"]:
                    logger.warning(f"No track found for: {track_info['full_query']}")
                    continue

                track = search_results["data"]["tracks"]["items"][0]
                track_id = track["id"]
                track_title = track["title"]
                logger.info(f"Found track: {track_title}")

                # Get track details
                track_details = muso_api.get_track_details(track_id)
                credits = track_details["data"].get("credits", [])

                # Process credits
                df = process_credits(credits, track_title)
                all_results.append(df)

                time.sleep(2)  # Rate limiting

            except Exception as e:
                logger.error(f"Error processing track {track_info['full_query']}: {str(e)}")
                continue

        if not all_results:
            logger.warning("No track credits loaded. Please try again later.")
            return

        # Combine and format results
        final_df = pd.concat(all_results, ignore_index=True)
        formatted_df = format_final_results(final_df)

        # Save results
        formatted_df.to_csv("playlist_credits_formatted.csv", index=False)
        final_df.to_csv("playlist_credits.csv", index=False)

        logger.info("Successfully saved results to CSV files")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
