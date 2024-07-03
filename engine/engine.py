from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime
import requests

class Video:
    def __init__(self, video_id, title, published_date, description, channel_id):
        self.video_id = video_id
        self.title = title
        self.published_date = published_date
        self.description = description
        self.channel_id = channel_id

def get_video_ids(channel_id,api_key):
    #googleapi
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": api_key,
        "channelId": channel_id,
        "part": "snippet,id",
        "order": "date",
        "maxResults": 50
    }

    response = requests.get(url, params=params)
    print(response.status_code)

    video_data = response.json()  # Parse the response as JSON
    return video_data

def find_latest_video(videos):
    if not videos:
        return None
    return max(videos, key=lambda video: video.published_date)
   

channel_id = 'UCGq-a57w-aPwyi3pW7XLiHw'
api_key = 'AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M'
video_data = get_video_ids(channel_id,api_key)

# Create Video objects
videos = []
for item in video_data["items"]:
    video = Video(
        video_id=item["id"]["videoId"],
        title=item["snippet"]["title"],
        published_date=item["snippet"]["publishedAt"],
        description=item["snippet"]["description"],
        channel_id=item["snippet"]["channelId"]
    )
    videos.append(video)

# Example usage:
for video in videos:
    print(f"Video ID: {video.video_id}")
    print(f"Title: {video.title}")
    print(f"Published Date: {video.published_date}")
    print(f"Description: {video.description}")
    print(f"Channel ID: {video.channel_id}")
    print("\n")


latest_video = find_latest_video(videos)
if latest_video:
    print(f"Latest video: {latest_video.video_id} {latest_video.title} ({latest_video.published_date})")


video_id = latest_video.video_id
print(video_id)
# Fetch available transcripts
transcript = YouTubeTranscriptApi.get_transcript(video_id)
transcript_text = " ".join([t['text'] for t in transcript])
print(transcript_text)








# curl -X GET "https://www.googleapis.com/youtube/v3/search?key=AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M&channelId=UCGq-a57w-aPwyi3pW7XLiHw&part=snippet,id&order=date&maxResults=50"