import os
import logging
import re
import nltk
import torch
import io
import requests
import sys
import yt_dlp as youtube_dl
from google.cloud import speech
from pytube import YouTube
from google.cloud import speech_v1p1beta1 as speech
from google.oauth2 import service_account
from transformers import BertTokenizer, BertForMaskedLM
from functools import lru_cache
from nltk.tokenize import sent_tokenize
from flask import Flask, render_template, jsonify
from concurrent.futures import ThreadPoolExecutor
from googleapiclient.discovery import build

app = Flask(__name__)

# Initialize BERT model and tokenizer
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = BertForMaskedLM.from_pretrained('bert-base-uncased').to(device)
model.eval()  # Set the model to evaluation mode

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

# Add your YouTube Data API key here
YOUTUBE_API_KEY = 'AIzaSyAz66SV-TruGZfyss14inB6d0MjuNfWBSY'

# Initialize the YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Specify the channel IDs
CHANNEL_IDS = {
    'Interviews': ['UCQ-rrUCsJLNjFdPtKq0YOfA'],  # Diary of a CEO
    'Business': ['UCGq-a57w-aPwyi3pW7XLiHw', 'UC1E1SVcVyU3ntWMSQEp38Yw'],  # Founders Podcast, The Prof G Show
    'Real Estate': ['UC-yRDvpR99LUc5l7i7jLzew', 'UCf0PBRjhf0rF8fWBIxTuoWA']  # Bg2 Pod, 20VC - The Twenty Minute VC
}

executor = ThreadPoolExecutor(max_workers=10)

nltk.download('punkt', quiet=True)

# Initialize Google Cloud Speech-to-Text client
credentials = service_account.Credentials.from_service_account_file("C:/Users/Connor Fata/project/scribe/scribe_/the-scribe-429016-9163b1182029.json")
speech_client = speech.SpeechClient(credentials=credentials)

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
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=max_results,
        order="date"
    )
    response = request.execute()
    logging.debug(f'Latest videos for channel {channel_id}: {response}')
    videos = []
    if 'items' in response:
        for item in response['items']:
            video_id = item['id'].get('videoId')
            title = item['snippet']['title']
            author = item['snippet']['channelTitle']
            if video_id:
                videos.append({'id': video_id, 'title': title, 'author': author})
    return videos

def transcribe_audio(speech_file_uri):
    audio = speech.RecognitionAudio(uri=speech_file_uri)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US"
    )
    
    operation = speech_client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=90)
    
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript + " "
    
    return transcript

def transcribe_audio_from_url(audio_url):
    # Fetch the audio file from the URL
    response = requests.get(audio_url)
    audio_content = io.BytesIO(response.content)
    
    # Initialize the Google Cloud Speech client
    client = speech.SpeechClient()
    
    # Read the audio content
    audio = speech.RecognitionAudio(content=audio_content.read())
    
    # Configure the recognition parameters
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    
    # Perform the transcription
    response = client.recognize(config=config, audio=audio)
    
    # Extract and return the transcript
    transcripts = [result.alternatives[0].transcript for result in response.results]
    return ' '.join(transcripts)

def get_transcription(video_id):
    try:
        # Extract audio using pytube
        yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        # Download the audio to a buffer
        buffer = io.BytesIO()
        audio_stream.stream_to_buffer(buffer)
        buffer.seek(0)

        # Transcribe the audio
        audio = speech.RecognitionAudio(content=buffer.read())
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=44100,
            language_code="en-US"
        )
        
        response = speech_client.recognize(config=config, audio=audio)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        
        return transcript, None
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
        elif transcription is None:
            transcription_text = "Transcription failed: No transcript returned"
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
        if isinstance(result['transcription'], str):
            result['transcription'] = ' '.join(result['transcription'].split()[:140]) + '...'  # First 140 words
        else:
            result['transcription'] = 'Error: Unable to process transcription'
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
    elif transcription is None:
        full_transcription_text = "Transcription failed: No transcript returned"
    else:
        full_transcription_text = format_transcription(transcription)
    return render_template('transcription.html', title=title, author=author, transcription=full_transcription_text)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
