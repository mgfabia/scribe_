import yt_dlp
import flask

def get_latest_video_url(channel_url):
    # Extract video information from the channel URL
    ydl_opts = {
        'quiet': True,
        'skip_download': True,  # We're only extracting information, not downloading yet
        'extract_flat': True,  # Don't download, just extract information
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(channel_url, download=False)
        if 'entries' in info_dict and len(info_dict['entries']) > 0:
            latest_video = info_dict['entries'][0]  # First entry is the latest video
            return f"https://www.youtube.com/watch?v={latest_video['id']}"
        else:
            raise ValueError("No videos found on the channel.")

def download_audio(video_url, output_dir='.', format='mp3'):
    # Set download options for audio extraction
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format,
            'preferredquality': '192',  # Change this to desired quality (192 kbps for MP3)
        }],
    }

    # Download the video and convert to the specified audio format
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

def process_channels(channel_urls, output_dir='.'):
    for channel_url in channel_urls:
        try:
            latest_video_url = get_latest_video_url(channel_url)
            print(f"Latest video URL from {channel_url}: {latest_video_url}")
            download_audio(latest_video_url, output_dir, format='mp3')  # Change format as needed
            print(f"Download complete for audio from video in channel {channel_url}.")
        except Exception as e:
            print(f"An error occurred for channel {channel_url}: {e}")

# Array of YouTube channel URLs
channel_urls = [
    "https://www.youtube.com/@ycombinator",
    "https://www.youtube.com/@LexClips",
    "https://www.youtube.com/@JREClips"
]

output_dir = '.'  # Specify the output directory if needed
process_channels(channel_urls, output_dir)
