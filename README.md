# 💖 Barbie's Magical Voice Agent 💖

This project is a conversational AI voice agent built as part of the **#30DaysofVoiceAgents** challenge by Murf AI. It features a custom "Barbie" persona with specialized skills, all accessible through a simple and engaging web interface.

## 🚀 Key Features

* **Custom Barbie Persona:** The agent responds in a positive, bubbly, and encouraging tone, using classic Barbie catchphrases like "Hi, Barbie!" and "You can be anything!"
* **Specialized Skills:** The agent has two prompt-based special skills:
    * **Barbie Stylist:** Provides fun and vibrant fashion advice for any occasion.
    * **Day Planner:** Creates a fun, structured plan for the day based on a user's goals.
* **End-to-End Conversational Flow:** The agent handles everything from transcribing spoken queries to generating a real-time voice response.
* **Robust Audio Playback:** The backend uses a reliable HTTP POST model with Murf AI to generate and serve audio, ensuring a seamless voice experience.
* **Cloud Deployment:** The agent is deployed and accessible to the public on Render.com.

## ⚙️ How It Works

The project is built on a a simple, cohesive architecture:
1.  **User Input:** You speak or type your query into the web interface.
2.  **Transcription:** The backend uses **AssemblyAI** to transcribe the spoken query into text.
3.  **LLM Processing:** The text is sent to the **Gemini AI** model, which uses the specialized Barbie persona to generate a text response.
4.  **Text-to-Speech:** The backend takes this text and sends it to **Murf AI** to convert it into a voice.
5.  **Audio Playback:** The URL for the generated audio file is sent back to the frontend, where it is immediately played.

## 🔧 Getting Started

### Prerequisites
* Python 3.8+
* API keys for Murf AI, Gemini, and AssemblyAI.

### Installation
1.  Clone this repository.
2.  Set up a Python virtual environment: `python -m venv venv`.
3.  Install dependencies: `pip install -r requirements.txt`.
4.  Create a `.env` file in the root directory and add your API keys:
    ```
    MURF_API_KEY=your_murf_api_key
    VITE_GEMINI_API_KEY=your_gemini_api_key
    ASSEMBLYAI_API_KEY=your_assemblyai_api_key
    ```

### Running the Application
1.  Start your server from the root directory: `uvicorn main:app --reload`.
2.  Visit `http://localhost:8000` in your browser.

## 🔗 Live Demo

You can interact with the live agent here:
[https://barbie-bot-stylist.onrender.com/](https://barbie-bot-stylist.onrender.com/)

---

## 🌟 Credits

This project was developed as part of the **30 Days of AI Voice Agents** challenge.
