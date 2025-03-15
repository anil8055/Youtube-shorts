import os
import openai
import requests
import ffmpeg
from googleapiclient.discovery import build
from elevenlabs import generate, save
from PIL import Image
from flask import Flask, render_template, jsonify
import threading

# Load API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__)
status = {"step": "Idle", "youtube_link": ""}

def generate_story():
    status["step"] = "Generating Story"
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "Generate a short moral children's story in Hindi."}
        ]
    )
    return response['choices'][0]['message']['content']

def generate_story_image(story_text):
    status["step"] = "Generating Story Image"
    response = openai.Image.create(
        model="dall-e-3",
        prompt=f"Pixar-style image of {story_text[:50]}...",
        size="1024x1024"
    )
    img_url = response["data"][0]["url"]
    img = requests.get(img_url).content
    with open("story_image.png", "wb") as f:
        f.write(img)
    return "story_image.png"

def generate_voiceover(story_text):
    status["step"] = "Generating Voiceover"
    audio = generate(
        text=story_text,
        voice="Arvind",
        model="eleven_multilingual_v2",
        api_key=ELEVENLABS_API_KEY
    )
    save(audio, "story_voice.mp3")
    return "story_voice.mp3"

def create_video(image_path, audio_path):
    status["step"] = "Creating Video"
    img = Image.open(image_path)
    img = img.resize((1920, 1080))
    img.save("resized_story_image.png")
    
    output_video = "story_video.mp4"
    (
        ffmpeg
        .input("resized_story_image.png", loop=1, t=10)
        .input(audio_path)
        .output(output_video, vcodec="libx264", acodec="aac", pix_fmt="yuv420p")
        .run()
    )
    return output_video

def upload_to_youtube(video_path, title, description):
    status["step"] = "Uploading to YouTube"
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["children", "Hindi", "story", "shorts"],
                "categoryId": "24"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=video_path
    )
    response = request.execute()
    status["youtube_link"] = f"https://www.youtube.com/watch?v={response['id']}"
    return response

def run_pipeline():
    story = generate_story()
    image_file = generate_story_image(story)
    voice_file = generate_voiceover(story)
    video_file = create_video(image_file, voice_file)
    upload_to_youtube(video_file, "Hindi Story Short", "A fun and engaging Hindi story for kids!")
    status["step"] = "Complete"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start_pipeline():
    threading.Thread(target=run_pipeline).start()
    return jsonify({"status": "Pipeline started"})

@app.route('/status')
def get_status():
    return jsonify(status)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
