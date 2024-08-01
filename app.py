import os
import requests
import logging
import random
from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Add your YouTube Data API key here
YOUTUBE_API_KEY = 'AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M'

# Add your Alpha Vantage API key here
ALPHA_VANTAGE_API_KEY = 'QJ6Po979I5HXQJVL'

# Specify the channel IDs
CHANNEL_IDS = {
    'Interviews': ['UCQ-rrUCsJLNjFdPtKq0YOfA'],  # Diary of a CEO
    'Business': ['UCGq-a57w-aPwyi3pW7XLiHw', 'UC1E1SVcVyU3ntWMSQEp38Yw'],  # Founders Podcast, The Prof G Show
    'Real Estate': ['UC-yRDvpR99LUc5l7i7jLzew', 'UCf0PBRjhf0rF8fWBIxTuoWA']  # Bg2 Pod, 20VC - The Twenty Minute VC
}

executor = ThreadPoolExecutor()

def get_latest_videos(channel_id, max_results=10):
    url = f'https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id&order=date&maxResults={max_results}'
    response = requests.get(url)
    data = response.json()
    logging.debug(f'Latest videos for channel {channel_id}: {data}')
    videos = []
    if 'items' in data:
        for item in data['items']:
            video_id = item['id'].get('videoId')
            title = item['snippet']['title']
            author = item['snippet']['channelTitle']
            if video_id:
                videos.append({'id': video_id, 'title': title, 'author': author})
    return videos

def get_transcription(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        cleaned_transcript = ' '.join([item['text'].strip() for item in transcript])
        return cleaned_transcript, None
    except NoTranscriptFound:
        return None, "No transcript found for this video."
    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."
    except VideoUnavailable:
        return None, "The video is unavailable."
    except Exception as e:
        return None, f"An error occurred: {str(e)}"

def get_market_news_and_sentiment(tickers='AAPL,MSFT,GOOG'):
    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'NEWS_SENTIMENT',
        'tickers': tickers,
        'apikey': ALPHA_VANTAGE_API_KEY
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json(), None
    else:
        return None, f"Error: {response.status_code} - {response.text}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcriptions')
def api_transcriptions():
    transcriptions = []
    additional_videos = []

    def fetch_transcription(video):
        transcription, error = get_transcription(video['id'])
        logging.debug(f'Title: {video["title"]}, Author: {video["author"]}')
        if error:
            transcription_text = f"Error: {error}"
        else:
            transcription_text = ' '.join(transcription.split()[:140]) + '...'  # First 140 words
        transcriptions.append({
            'id': video['id'],
            'title': video['title'] or 'Title not found',
            'author': video['author'] or 'Author not found',
            'transcription': transcription_text
        })

    # Fetch the latest video from each channel
    for category, channels in CHANNEL_IDS.items():
        for channel_id in channels:
            latest_videos = get_latest_videos(channel_id, max_results=1)
            logging.debug(f'Latest video for channel {channel_id}: {latest_videos}')
            for video in latest_videos:
                executor.submit(fetch_transcription, video)

    # Fetch additional videos from each channel
    for category, channels in CHANNEL_IDS.items():
        for channel_id in channels:
            latest_videos = get_latest_videos(channel_id, max_results=10)
            logging.debug(f'Additional videos for channel {channel_id}: {latest_videos[1:]}')
            for video in latest_videos[1:]:  # Skip the first video as it is already added
                additional_videos.append(video)

    # Log the additional videos to ensure they are fetched correctly
    logging.debug(f'Additional videos: {additional_videos}')

    # Randomly select 5 additional videos
    random.shuffle(additional_videos)
    additional_videos = additional_videos[:5]

    # Add the additional videos to the transcriptions list
    for video in additional_videos:
        executor.submit(fetch_transcription, video)

    return jsonify({'transcriptions': transcriptions})

@app.route('/api/market-news')
def api_market_news():
    app.logger.debug("Fetching market news and sentiment data.")
    news_data, error = get_market_news_and_sentiment()
    if error:
        app.logger.error(f"Market news error: {error}")
        return jsonify({'error': error}), 500
    app.logger.debug(f"Market news data: {news_data}")
    return jsonify(news_data)

@app.route('/api/category/<category>')
def api_category(category):
    if category not in CHANNEL_IDS:
        return jsonify({'error': 'Invalid category'}), 400

    transcriptions = []

    def fetch_transcription(video):
        transcription, error = get_transcription(video['id'])
        logging.debug(f'Title: {video["title"]}, Author: {video["author"]}')
        if error:
            transcription_text = f"Error: {error}"
        else:
            transcription_text = ' '.join(transcription.split()[:140]) + '...'  # First 140 words
        transcriptions.append({
            'id': video['id'],
            'title': video['title'] or 'Title not found',
            'author': video['author'] or 'Author not found',
            'transcription': transcription_text
        })

    for channel_id in CHANNEL_IDS[category]:
        latest_videos = get_latest_videos(channel_id, max_results=3)
        logging.debug(f'Latest videos for category {category}, channel {channel_id}: {latest_videos}')
        for video in latest_videos:
            executor.submit(fetch_transcription, video)

    return jsonify({'transcriptions': transcriptions})

@app.route('/transcription/<video_id>')
def full_transcription(video_id):
    transcription, error = get_transcription(video_id)
    title, author = None, None
    for channels in CHANNEL_IDS.values():
        for channel_id in channels:
            latest_videos = get_latest_videos(channel_id)
            for video in latest_videos:
                if video['id'] == video_id:
                    title, author = video['title'], video['author']
                    break
    if error:
        full_transcription_text = f"Error: {error}"
    else:
        full_transcription_text = transcription
    return render_template('transcription.html', title=title, author=author, transcription=full_transcription_text)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
