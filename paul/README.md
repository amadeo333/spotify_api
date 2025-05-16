# Playlist Credits Analyzer

A web application that analyzes Spotify playlists and retrieves detailed credits information for each track.

## Features

- Analyze any public Spotify playlist
- View detailed credits information for each track
- Download results in CSV format
- User-friendly web interface
- Progress tracking and error handling

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API credentials:
   ```
   client_id=your_spotify_client_id
   client_secret=your_spotify_client_secret
   muso_api_key=your_muso_api_key
   ```

## Running Locally

To run the application locally:

```bash
streamlit run app.py
```

## Deployment

### Deploying to Streamlit Cloud

1. Push your code to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with your GitHub account
4. Click "New app"
5. Select your repository, branch, and main file (app.py)
6. Add your environment variables in the "Secrets" section
7. Deploy!

### Deploying to Heroku

1. Create a `Procfile`:
   ```
   web: streamlit run app.py --server.port $PORT
   ```
2. Create a `runtime.txt`:
   ```
   python-3.9.18
   ```
3. Deploy to Heroku:
   ```bash
   heroku create your-app-name
   git push heroku main
   ```
4. Set environment variables:
   ```bash
   heroku config:set client_id=your_spotify_client_id
   heroku config:set client_secret=your_spotify_client_secret
   heroku config:set muso_api_key=your_muso_api_key
   ```

## Usage

1. Open the application in your web browser
2. Paste a Spotify playlist URL
3. Click "Analyze Playlist"
4. Wait for the analysis to complete
5. View and download the results

## Notes

- The application requires valid API credentials for both Spotify and Muso
- Rate limiting is implemented to avoid API restrictions
- Results are cached to improve performance
- The application handles errors gracefully and provides user feedback
