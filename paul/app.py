import streamlit as st
import pandas as pd
from artist_info import SpotifyAPI, MusoAPI, process_credits, format_final_results
import time

st.set_page_config(
    page_title="Playlist Credits Analyzer",
    page_icon="🎵",
    layout="wide"
)

def main():
    st.title("🎵 Playlist Credits Analyzer")
    st.markdown("""
    This tool analyzes a Spotify playlist and retrieves detailed credits information for each track.
    Simply paste your Spotify playlist URL below to get started!
    """)

    # Input section
    with st.form("playlist_form"):
        playlist_url = st.text_input(
            "Spotify Playlist URL",
            placeholder="https://open.spotify.com/playlist/..."
        )
        submit_button = st.form_submit_button("Analyze Playlist")

    if submit_button and playlist_url:
        try:
            with st.spinner("Initializing..."):
                spotify_api = SpotifyAPI()
                muso_api = MusoAPI()

            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Get playlist tracks
            tracks_to_search = spotify_api.get_playlist_tracks(playlist_url)
            total_tracks = len(tracks_to_search)

            if total_tracks == 0:
                st.error("No tracks found in the playlist. Please check the URL and try again.")
                return

            st.info(f"Found {total_tracks} tracks in the playlist. Starting analysis...")

            all_results = []

            # Process each track
            for idx, track_info in enumerate(tracks_to_search, 1):
                status_text.text(f"Processing track {idx}/{total_tracks}: {track_info['track_name']}")
                progress_bar.progress(idx / total_tracks)

                try:
                    # Search track
                    search_results = muso_api.search_track(track_info['full_query'])
                    if not search_results["data"]["tracks"]["items"]:
                        st.warning(f"No track found for: {track_info['track_name']}")
                        continue

                    track = search_results["data"]["tracks"]["items"][0]
                    track_id = track["id"]
                    track_title = track["title"]

                    # Get track details
                    track_details = muso_api.get_track_details(track_id)
                    credits = track_details["data"].get("credits", [])

                    # Process credits
                    df = process_credits(credits, track_title)
                    all_results.append(df)

                    time.sleep(2)  # Rate limiting

                except Exception as e:
                    st.error(f"Error processing track {track_info['track_name']}: {str(e)}")
                    continue

            if not all_results:
                st.error("No track credits loaded. Please try again later.")
                return

            # Combine and format results
            final_df = pd.concat(all_results, ignore_index=True)
            formatted_df = format_final_results(final_df)

            # Display results
            st.success("Analysis complete! Here are the results:")

            # Show formatted results
            st.subheader("Formatted Results")
            st.dataframe(formatted_df)

            # Show detailed results
            st.subheader("Detailed Results")
            st.dataframe(final_df)

            # Download buttons
            st.download_button(
                label="Download Formatted Results (CSV)",
                data=formatted_df.to_csv(index=False).encode('utf-8'),
                file_name="playlist_credits_formatted.csv",
                mime='text/csv',
            )

            st.download_button(
                label="Download Detailed Results (CSV)",
                data=final_df.to_csv(index=False).encode('utf-8'),
                file_name="playlist_credits.csv",
                mime='text/csv',
            )

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
