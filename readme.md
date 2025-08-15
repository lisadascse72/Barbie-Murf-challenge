# Murf-AI 30 Days Challenge

Welcome to the **Murf-AI 30 Days Challenge**!  
This project documents the journey of building advanced AI Voice Agents in 30 days, inspired by Murf AI. The repository contains daily progress, code samples, architectures, and learnings.

---

## 🚀 Project Overview

**Murf-AI 30 Days** is a hands-on exploration of AI-powered voice agents.  
The objectives include:
- Creating intelligent voice bots
- Integrating with APIs
- Experimenting with speech-to-text and text-to-speech
- Building scalable microservices for conversational AI

---

## 🛠️ Technologies Used

- **Python** (Core scripts & backend API)
- **Flask / FastAPI** (API server)
- **SpeechRecognition** (Speech-to-text)
- **gTTS** / **pyttsx3** (Text-to-speech)
- **OpenAI API** (Language model integration)
- **Docker** (Containerization)
- **GitHub Actions** (CI/CD)
---

## ✨ Features

- Natural voice conversations
- Customizable voice personas
- Context-aware responses
- RESTful API endpoints
- Daily progress & code samples
- Easy setup & deployment
- (Optional) Web UI for testing

---

## ⚡ Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/lisadascse72/Murf-AI-30-days.git
cd Murf-AI-30-days
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file in the root directory with the following:
```
OPENAI_API_KEY=your_openai_key_here
FLASK_ENV=development
SECRET_KEY=your_secret_key
# Add other keys as needed for TTS/STT providers
```

### 4. Run the API server
```bash
# For Flask
python app.py

# For FastAPI
uvicorn main:app --reload
```

### 5. Test the Voice Agent
Use `curl`, Postman, or the provided web UI to interact with your agent.

---

## 📚 Contributing

Feel free to fork, submit issues, or suggest improvements!

---

## 📄 License

MIT License

---

## 🙌 Connect

Share your journey on [LinkedIn](https://www.linkedin.com/) with a screenshot of this README!

---
