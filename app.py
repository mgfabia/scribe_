from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from pyannote.audio import Pipeline
import requests
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_generated_secret_key_here'
socketio = SocketIO(app)

# Load the speaker diarization pipeline
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")

transcriptions_history = []

@app.route('/')
def index():
    return render_template('index.html', history=transcriptions_history)

def download_audio_from_youtube(youtube_url):
    video_id = youtube_url.split('v=')[-1]
    audio_url = f"http://youtube-to-audio-api/{video_id}.mp3"  # Replace with your actual URL
    response = requests.get(audio_url)
    audio_path = f"{video_id}.mp3"
    with open(audio_path, 'wb') as f:
        f.write(response.content)
    return audio_path

def get_speaker_segments(audio_path):
    diarization = pipeline(audio_path)
    return diarization

def get_transcription(youtube_url):
    video_id = youtube_url.split('v=')[-1]
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

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    data = request.get_json()
    youtube_url = data.get('url')

    if not youtube_url:
        return jsonify({'error': 'URL is required'}), 400

    transcription, error = get_transcription(youtube_url)
    if error:
        return jsonify({'error': error}), 500

    audio_path = download_audio_from_youtube(youtube_url)
    speaker_segments = get_speaker_segments(audio_path)
    os.remove(audio_path)  # Clean up the audio file after processing

    speaker_transcription = []
    for segment in speaker_segments:
        speaker = segment['label']
        start_time = segment['start']
        end_time = segment['end']
        speaker_transcription.append(f"{speaker}: {transcription[start_time:end_time]}")

    speaker_transcription_text = "\n".join(speaker_transcription)
    transcriptions_history.append({'url': youtube_url, 'transcription': speaker_transcription_text})
    socketio.emit('transcription_update', {'transcription': speaker_transcription_text})
    return jsonify({'transcription': speaker_transcription_text}), 200

@app.route('/api/history', methods=['GET'])
def history():
    return jsonify(transcriptions_history)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
