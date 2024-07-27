import os
import requests
import logging
import re
import nltk
import torch
from transformers import BertTokenizer, BertForMaskedLM
from functools import lru_cache
from nltk.tokenize import sent_tokenize
from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Initialize BERT model and tokenizer
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = BertForMaskedLM.from_pretrained('bert-base-uncased').to(device)
model.eval()  # Set the model to evaluation mode

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

executor = ThreadPoolExecutor(max_workers=10)

nltk.download('punkt', quiet=True)

@lru_cache(maxsize=1000)
def improve_text_with_bert(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    
    predictions = outputs.logits.argmax(dim=-1)
    improved_tokens = tokenizer.convert_ids_to_tokens(predictions.squeeze().tolist())
    improved_text = tokenizer.convert_tokens_to_string(improved_tokens)
    
    return improved_text

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

def clean_text(text):
    # Remove filler words
    filler_words = ["um", "uh", "like", "you know", "sort of", "kind of"]
    for word in filler_words:
        text = re.sub(r'\b' + word + r'\b', '', text, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Fix common transcription errors
    text = re.sub(r'\bi\b', 'I', text)
    text = re.sub(r'\bim\b', "I'm", text)
    text = re.sub(r'\bdont\b', "don't", text)
    text = re.sub(r'\bwont\b', "won't", text)
    text = re.sub(r'\bcant\b', "can't", text)
    
    return text

def format_transcription(transcription):
    if isinstance(transcription, list):
        full_text = ' '.join(item['text'] for item in transcription)
    else:
        full_text = transcription
    
    # Clean the text
    cleaned_text = clean_text(full_text)
    
    # Improve text with BERT
    improved_text = improve_text_with_bert(cleaned_text)
    
    # Split text into sentences
    sentences = sent_tokenize(improved_text)
    
    formatted_paragraphs = []
    current_paragraph = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            current_paragraph.append(sentence)
            if len(current_paragraph) >= 3:
                formatted_paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
    
    if current_paragraph:
        formatted_paragraphs.append(' '.join(current_paragraph))
    
    return '\n\n'.join(formatted_paragraphs)

def fetch_transcription(video):
    try:
        transcription, error = get_transcription(video['id'])
        if error:
            transcription_text = f"Error: {error}"
        else:
            transcription_text = format_transcription(transcription)
    except Exception as e:
        logging.error(f"Error processing transcription for video {video['id']}: {str(e)}")
        transcription_text = f"Error processing transcription: {str(e)}"

    return {
        'id': video['id'],
        'title': video.get('title', 'Title not found'),
        'author': video.get('author', 'Author not found'),
        'transcription': transcription_text
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcriptions')
def api_transcriptions():
    transcriptions = []
    futures = []
    for category, channels in CHANNEL_IDS.items():
        for channel_id in channels:
            latest_videos = get_latest_videos(channel_id, max_results=1)
            for video in latest_videos:
                futures.append(executor.submit(fetch_transcription, video))

    for future in futures:
        transcriptions.append(future.result())

    return jsonify({'transcriptions': transcriptions})

@app.route('/api/category/<category>')
def api_category(category):
    if category not in CHANNEL_IDS:
        return jsonify({'error': 'Invalid category'}), 400

    transcriptions = []
    futures = []

    for channel_id in CHANNEL_IDS[category]:
        latest_videos = get_latest_videos(channel_id, max_results=3)
        logging.debug(f'Latest videos for category {category}, channel {channel_id}: {latest_videos}')
        for video in latest_videos:
            futures.append(executor.submit(fetch_transcription, video))

    for future in futures:
        result = future.result()
        result['transcription'] = ' '.join(result['transcription'].split()[:140]) + '...'  # First 140 words
        transcriptions.append(result)

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
        full_transcription_text = format_transcription(transcription)
    return render_template('transcription.html', title=title, author=author, transcription=full_transcription_text)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
