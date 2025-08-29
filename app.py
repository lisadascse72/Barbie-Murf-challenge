from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load .env variables from a .env file if running locally
load_dotenv()

# We need to tell Flask where to find the static files (including index.html)
app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app) 

# Base URL for the Gemini API
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

@app.route("/")
def index():
    """Serves the main HTML page from the static directory."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/chat", methods=["POST"])
def chat():
    """
    Handles chat requests by sending user input to the Gemini API
    and returning the text response.
    """
    data = request.get_json()
    user_prompt = data.get("prompt")

    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        return jsonify({"error": "GEMINI_API_KEY not set"}), 500

    headers = {
        "Content-Type": "application/json",
    }
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 200
        }
    }

    try:
        gemini_response = requests.post(
            f"{GEMINI_API_BASE_URL}?key={gemini_api_key}",
            json=payload,
            headers=headers
        )
        gemini_response.raise_for_status()

        gemini_result = gemini_response.json()
        
        if gemini_result.get("candidates") and gemini_result["candidates"][0].get("content"):
            response_text = gemini_result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            response_text = "I'm not sure how to respond to that, sweetie!"
            
        return jsonify({"response": response_text})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to get response from Barbie's magic brain: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/generate-audio", methods=["POST"])
def generate_audio():
    """
    Generates audio from text using the Murf.ai API and returns the audio URL.
    """
    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    murf_api_key = os.getenv("MURF_API_KEY")
    if not murf_api_key:
        return jsonify({"error": "MURF_API_KEY not set"}), 500

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {murf_api_key}"
    }

    payload = {
        "text": text,
        "voice": "en-US-Natalie",
        "format": "mp3"
    }

    try:
        murf_response = requests.post("https://api.murf.ai/v1/tts/generate", json=payload, headers=headers)
        murf_response.raise_for_status()
        return jsonify(murf_response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to generate audio: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
