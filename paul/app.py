import streamlit as st
import pandas as pd
from artist_info import SpotifyAPI, MusoAPI, format_final_results
import time
import logging
from io import StringIO
import base64

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize APIs
spotify_api = SpotifyAPI()
muso_api = MusoAPI()

# Set page config
st.set_page_config(
    page_title="Spotify Playlist Credits Analyzer",
    page_icon="🎵",
    layout="wide"
)

# Title and description
st.title("🎵 Spotify Playlist Credits Analyzer")
st.markdown("""
This app analyzes a Spotify playlist and retrieves detailed credits information for each track using the Muso API.
Enter a Spotify playlist URL to get started!
""")

# Input field for playlist URL
playlist_url = st.text_input("Enter Spotify Playlist URL:", placeholder="https://open.spotify.com/playlist/...")

if playlist_url:
    try:
        # Get playlist tracks
        with st.spinner("Fetching playlist tracks..."):
            track_dictionary = spotify_api.get_playlist_tracks(playlist_url)
            total_tracks = len(track_dictionary)
            st.info(f"Found {total_tracks} tracks in the playlist")

        # Process tracks
        if st.button("Analyze Credits"):
            all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Process each track in playlist order
            for idx, (track, track_info) in enumerate(track_dictionary.items(), 1):
                status_text.text(f"Processing track {idx}/{total_tracks}: {track}")
                progress_bar.progress(idx / total_tracks)

                try:
                    df = muso_api.process_track(track, track_info)
                    if df is not None:
                        all_results.append(df)
                    time.sleep(2)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error processing track {track}: {str(e)}")
                    continue

            # Create a list of all tracks in playlist order
            all_tracks = []
            for track, track_info in track_dictionary.items():
                all_tracks.append({
                    "track_name": track,
                    "artist": track_info['artist']
                })

            # Format results
            final_df = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
            formatted_df = format_final_results(final_df, all_tracks)

            # Display results
            st.success("Analysis complete! Here are the results:")

            # Display formatted results
            st.subheader("All Tracks")
            st.dataframe(formatted_df)

            # Display unmatched tracks count
            if muso_api.unmatched_tracks:
                st.warning(f"Could not find credits for {len(muso_api.unmatched_tracks)} tracks")

            # Download button
            def get_download_link(df, filename):
                csv = df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download {filename}</a>'
                return href

            st.markdown("### Download Results")
            st.markdown(get_download_link(formatted_df, "playlist_credits.csv"), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logger.error(f"Error: {str(e)}")
