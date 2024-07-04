from flask import Flask, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

app = Flask(__name__)

programmed_channels = [
    {'id': 'dQw4w9WgXcQ', 'title': 'Title of Video 1', 'author': 'Author 1'},
    {'id': 'another_video_id', 'title': 'Title of Video 2', 'author': 'Author 2'},
    # Add more channels as needed
]

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
        if error:
            transcription_text = f"Error: {error}"
        else:
            transcription_text = ' '.join(transcription.split()[:140]) + '...'  # First 140 words
        transcriptions.append({
            'id': channel['id'],
            'title': channel['title'],
            'author': channel['author'],
            'transcription': transcription_text
        })
    return jsonify({'transcriptions': transcriptions})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
