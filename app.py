from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate-audio", methods=["POST"])
def generate_audio():
    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {os.getenv('MURF_API_KEY')}"
    }

    payload = {
        "text": text,
        "voice": "en-US-William",  # You can change this to any supported voice
        "format": "mp3"
    }

    try:
        response = requests.post("https://api.murf.ai/v1/tts/generate", json=payload, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())  # This includes the audio_url
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
