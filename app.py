import os
import requests
import logging
from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Add your YouTube Data API key here
YOUTUBE_API_KEY = 'AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M'

# Specify the channel ID
CHANNEL_ID = 'UCGq-a57w-aPwyi3pW7XLiHw'

def get_latest_videos(channel_id):
    url = f'https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id&order=date&maxResults=3'
    response = requests.get(url)
    data = response.json()
    logging.debug(f'Latest videos for channel {channel_id}: {data}')
    videos = []
    if 'items' in data:
        for item in data['items']:
            video_id = item['id'].get('videoId')
            title = item['snippet']['title']
            author = item['snippet']['channelTitle']
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcriptions')
def api_transcriptions():
    transcriptions = []
    latest_videos = get_latest_videos(CHANNEL_ID)
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
    return jsonify({'transcriptions': transcriptions})

@app.route('/transcription/<video_id>')
def full_transcription(video_id):
    transcription, error = get_transcription(video_id)
    title, author = None, None
    latest_videos = get_latest_videos(CHANNEL_ID)
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
