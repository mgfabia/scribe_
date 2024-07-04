import os
import requests
from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

app = Flask(__name__)

programmed_channels = [
    {'id': 'dQw4w9WgXcQ'},  # Example video ID
    {'id': 'another_video_id'},  # Add more video IDs as needed
]

# Set your YouTube Data API key here
YOUTUBE_API_KEY = 'YOUR_YOUTUBE_API_KEY'

def get_video_details(video_id):
    url = f'https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}'
    response = requests.get(url)
    data = response.json()
    if 'items' in data and len(data['items']) > 0:
        snippet = data['items'][0]['snippet']
        title = snippet['title']
        author = snippet['channelTitle']
        return title, author
    return None, None

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
    for channel in programmed_channels:
        transcription, error = get_transcription(channel['id'])
        title, author = get_video_details(channel['id'])
        if error:
            transcription_text = f"Error: {error}"
        else:
            transcription_text = ' '.join(transcription.split()[:140]) + '...'  # First 140 words
        transcriptions.append({
            'id': channel['id'],
            'title': title or 'Title not found',
            'author': author or 'Author not found',
            'transcription': transcription_text
        })
    return jsonify({'transcriptions': transcriptions})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
