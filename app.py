import os
import requests
import logging
import random
import re
import nltk
from nltk.tokenize import sent_tokenize
from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from concurrent.futures import ThreadPoolExecutor
from typing import Union, List, Dict

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

# Add your YouTube Data API key here
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', 'AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M')

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
        return transcript, None
    except NoTranscriptFound:
        logging.error(f"No transcript found for video ID {video_id}")
        return None, "No transcript found for this video."
    except TranscriptsDisabled:
        logging.error(f"Transcripts are disabled for video ID {video_id}")
        return None, "Transcripts are disabled for this video."
    except VideoUnavailable:
        logging.error(f"The video is unavailable for video ID {video_id}")
        return None, "The video is unavailable."
    except Exception as e:
        logging.error(f"An error occurred for video ID {video_id}: {str(e)}")
        return None, f"An error occurred: {str(e)}"

nltk.download('punkt')

def format_transcription(transcript):
    if isinstance(transcript, str):
        # If it's already a string, just process it as is
        return process_chunk(transcript)
    
    formatted_transcript = ""
    current_chunk = ""
    current_chunk_start = 0
    filler_words = set(["um", "uh", "like", "you know", "sort of", "kind of"])

    for item in transcript:
        if isinstance(item, dict):
            start_time = item.get('start', 0)
            text = item.get('text', '')
        elif isinstance(item, str):
            start_time = current_chunk_start
            text = item
        else:
            continue  # Skip if it's neither a dict nor a string

        # Remove filler words
        for word in filler_words:
            text = re.sub(r'\b' + word + r'\b', '', text, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # If we're starting a new 5-minute chunk
        if int(start_time) // 300 > current_chunk_start // 300:
            if current_chunk:
                formatted_chunk = process_chunk(current_chunk)
                formatted_transcript += f"--- {current_chunk_start // 60:02d}:00 to {(current_chunk_start // 60) + 5:02d}:00 ---\n\n{formatted_chunk}\n\n"
                formatted_transcript += "------------------------------\n\n"  # Add a line between segments
            current_chunk = text
            current_chunk_start = int(start_time)
        else:
            current_chunk += " " + text

    # Add any remaining text
    if current_chunk:
        formatted_chunk = process_chunk(current_chunk)
        formatted_transcript += f"--- {current_chunk_start // 60:02d}:00 to {(current_chunk_start // 60) + 5:02d}:00 ---\n\n{formatted_chunk}\n"

    return formatted_transcript.strip()

def process_chunk(chunk):
    # Capitalize first letter of sentences
    sentences = sent_tokenize(chunk)
    sentences = [s.capitalize() for s in sentences]
    
    # Join sentences, ensuring proper spacing
    processed_chunk = ' '.join(sentences)
    
    # Fix common transcription errors
    processed_chunk = re.sub(r'\bi\b', 'I', processed_chunk)
    processed_chunk = re.sub(r'\bim\b', "I'm", processed_chunk)
    processed_chunk = re.sub(r'\bdont\b', "don't", processed_chunk)
    processed_chunk = re.sub(r'\bwont\b', "won't", processed_chunk)
    processed_chunk = re.sub(r'\bcant\b', "can't", processed_chunk)
    
    # Add periods to the end of sentences if missing
    processed_chunk = re.sub(r'(?<=[a-z])\s+(?=[A-Z])', '. ', processed_chunk)
    
        # Split into paragraphs (e.g., every 3-5 sentences)
    sentences = sent_tokenize(processed_chunk)
    paragraphs = []
    for i in range(0, len(sentences), 4):  # Change 4 to adjust paragraph size
        paragraph = ' '.join(sentences[i:i+4])
        paragraphs.append(paragraph)
    
    return '\n\n'.join(paragraphs)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcriptions')
def api_transcriptions():
    transcriptions = []

    def fetch_transcription(video):
        transcription, error = get_transcription(video['id'])
        logging.debug(f'Title: {video["title"]}, Author: {video["author"]}')
        if error:
            transcription_text = f"Error: {error}"
        else:
            try:
                # Format the raw transcription
                formatted_transcription = format_transcription(transcription)
            
                # Take the first chunk (first 5 minutes) for preview
                chunks = formatted_transcription.split("------------------------------")
                first_chunk = chunks[0].strip() if chunks else ""
                transcription_text = first_chunk
            except Exception as e:
                logging.error(f"Error formatting transcription: {str(e)}")
                transcription_text = "Error processing transcription"

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
            for video in latest_videos:
                fetch_transcription(video)

    # ... (rest of the function remains the same)

    return jsonify({'transcriptions': transcriptions})

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
