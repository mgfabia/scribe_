import base64
import functions_framework
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime
import requests
import json 
from google.cloud import storage


class Video:
    def __init__(self, video_id, title, published_date, description, channel_id):
        self.video_id = video_id
        self.title = title
        self.published_date = published_date
        self.description = description
        self.channel_id = channel_id
     
    def to_dict(self):
        return {
          'title' : self.title,
          'video_id' : self.video_id,
          'channel_id' : self.channel_id,
          'description' : self.description,
          'published_date' : self.published_date
        }

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


def upload_video(video_json, bucket_name, blob_name, folder_name):
    """
    Uploads a video JSON object to a specified folder within a bucket in Google Cloud Storage.

    Args:
        video_json (dict): The video data in JSON format.
        bucket_name (str): Name of the target bucket.
        blob_name (str): Name of the blob (object) within the bucket.
        folder_name (str): Name of the folder within the bucket.
    """
    # Initialize the Google Cloud Storage client
    client = storage.Client()

    # Get the bucket
    bucket = client.get_bucket(bucket_name)

    # Convert the video_json object to a JSON string
    video_json_str = json.dumps(video_json, indent=4)

    # Construct the full blob name (including folder path)
    full_blob_name = f"{folder_name}/{blob_name}"

    # Upload the JSON string to the blob
    blob = bucket.blob(full_blob_name)
    blob.upload_from_string(video_json_str, content_type='application/json')

    print(f"Video data saved to {full_blob_name} in bucket {bucket_name}")



# curl -X GET "https://www.googleapis.com/youtube/v3/search?key=AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M&channelId=UCGq-a57w-aPwyi3pW7XLiHw&part=snippet,id&order=date&maxResults=50"
# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def start(cloud_event):
  print("starting")
  api_key = 'AIzaSyBq-xfGtyUbbV1UjLVAf18FuYc4iJ_g2-M'
  channel_ids = {
      'DiaryOfCEO': 'UCGq-a57w-aPwyi3pW7XLiHw',
      'LexFriedman': 'UCFItIX8SIs4zqhJCHpbeV1A'
  }
  latest_video_arr = []
  count = 0
  for channel_name, channel_id in channel_ids.items():
      video_data = get_video_ids(channel_id, api_key)
      print("videoData")
      print(video_data)
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
      print(latest_video)
      if latest_video:
          print(f"Latest video: {latest_video.video_id} {latest_video.title} ({latest_video.published_date})")


      video_id = latest_video.video_id
      latest_video_arr.append(latest_video)
      print(video_id)
      # Fetch available transcripts
      transcript = YouTubeTranscriptApi.get_transcript(video_id)
      transcript_text = " ".join([t['text'] for t in transcript])
      print(transcript_text)
      count += 1
      print("####################")
      print(count)
      videoObj = latest_video.to_dict()
      video_object = {
        "latest_video": videoObj,
        "transcript_text": transcript_text
      }
    
      upload_video(video_object, "video-transcripts-scribe" , channel_name, channel_id)