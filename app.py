import os
import requests
import logging
import random
import time
from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Add your YouTube Data API key here
YOUTUBE_API_KEY = 'AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M'

# Specify the channel IDs (please verify these are correct)
CHANNEL_IDS = [
    'UCGq-a57w-aPwyi3pW7XLiHw',  # Founders Podcast
    'UCQ-rrUCsJLNjFdPtKq0YOfA',  # Diary of a CEO
    'UC1E1SVcVyU3ntWMSQEp38Yw',  # The Prof G Show
    'UC-yRDvpR99LUc5l7i7jLzew',  # Bg2 Pod
    'UCf0PBRjhf0rF8fWBIxTuoWA'   # 20VC - The Twenty Minute VC
]

# Simple cache dictionary
CACHE = {}
CACHE_EXPIRATION = 3600  # 1 hour

def get_latest_videos(channel_id, max_results=10):
    if channel_id in CACHE and time.time() - CACHE[channel_id]['timestamp'] < CACHE_EXPIRATION:
        logging.debug(f'Using cached data for channel {channel_id}')
        return CACHE[channel_id]['data']

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
    CACHE[channel_id] = {'data': videos, 'timestamp': time.time()}
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcriptions')
def api_transcriptions():
    transcriptions = []
    additional_videos = []

    # Fetch the latest video from each channel
    for channel_id in CHANNEL_IDS:
        latest_videos = get_latest_videos(channel_id, max_results=1)
        logging.debug(f'Latest video for channel {channel_id}: {latest_videos}')
        for video in latest_videos:
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

    # Fetch additional videos from each channel
    for channel_id in CHANNEL_IDS:
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

    return jsonify({'transcriptions': transcriptions})

@app.route('/transcription/<video_id>')
def full_transcription(video_id):
    transcription, error = get_transcription(video_id)
    title, author = None, None
    for channel_id in CHANNEL_IDS:
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

@app.route('/category/<category>')
def category_transcriptions(category):
    channel_id = None
    if category == 'interviews':
        channel_id = 'UCQ-rrUCsJLNjFdPtKq0YOfA'  # Diary of a CEO
    elif category == 'business':
        channel_id = 'UC1E1SVcVyU3ntWMSQEp38Yw'  # The Prof G Show
    elif category == 'real_estate':
        channel_id = 'UC-yRDvpR99LUc5l7i7jLzew'  # Bg2 Pod

    if channel_id:
        transcriptions = []
        latest_videos = get_latest_videos(channel_id, max_results=3)
        for video in latest_videos:
            transcription, error = get_transcription(video['id'])
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
        return render_template('category.html', category=category.capitalize(), transcriptions=transcriptions)
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
