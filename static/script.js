// static/script.js
// --- Configuration for Local Development ---
// For local development, set the URL to your Uvicorn server.
// For deployment, this should be an empty string "" if the frontend and backend are on the same host.
// const BACKEND_URL = "http://localhost:8000";
// For deployment, change this to an empty string.
const BACKEND_URL = "";

// --- UI Elements and State ---
const chatbox = document.getElementById("chatbox");
const chatTextInput = document.getElementById("chat-text-input");
const sendTextBtn = document.getElementById("sendTextBtn");
const startRecordingChatBtn = document.getElementById("startRecordingChatBtn");
const stopRecordingChatBtn = document.getElementById("stopRecordingChatBtn");
const llmResponseAudioPlayer = document.getElementById("llmResponseAudioPlayer");

let sessionId = "user_session_" + Date.now();
let ws;
let mediaRecorder;

// --- Helper Functions for UI ---
function addChatMessage(message, sender) {
    const messageElement = document.createElement("div");
    messageElement.classList.add("chat-message");
    messageElement.classList.add(sender === "user" ? "user-message" : "agent-message");
    messageElement.textContent = message;
    chatbox.appendChild(messageElement);
    chatbox.scrollTop = chatbox.scrollHeight;
}

function handleAudioStreaming() {
    // The WebSocket URL must also point to the backend server's address
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;
    const wsUrl = `${protocol}://${host.split(':')[0]}:8000/ws/audio_stream/${sessionId}`;

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'audio_chunk' && data.audio) {
                const audioData = atob(data.audio);
                const arrayBuffer = new ArrayBuffer(audioData.length);
                const view = new Uint8Array(arrayBuffer);
                for (let i = 0; i < audioData.length; i++) {
                    view[i] = audioData.charCodeAt(i);
                }
                
                try {
                    const audioBufferSource = audioContext.createBufferSource();
                    const audioBufferDecoded = await audioContext.decodeAudioData(arrayBuffer);
                    audioBufferSource.buffer = audioBufferDecoded;
                    audioBufferSource.connect(audioContext.destination);
                    audioBufferSource.start();
                } catch (error) {
                    console.error("Error decoding audio chunk:", error);
                }
            } else if (data.type === 'finished_audio') {
                console.log("Audio streaming finished.");
                ws.close();
            } else if (data.type === 'error') {
                console.error("WebSocket Error:", data.message);
                addChatMessage(`Audio Streaming Error: ${data.message}`, "agent");
                ws.close();
            }
        } catch (e) {
            console.error("Error parsing WebSocket message:", e, event.data);
            addChatMessage(`Audio Streaming Error: An unexpected issue occurred.`, "agent");
            ws.close();
        }
    };

    ws.onclose = () => {
        console.log("WebSocket connection closed.");
    };

    ws.onerror = (error) => {
        console.error("WebSocket error observed:", error);
    };
}

// --- Event Listeners ---
sendTextBtn.addEventListener("click", async () => {
    const text = chatTextInput.value.trim();
    if (!text) return;

    addChatMessage(text, "user");
    chatTextInput.value = "";
    
    try {
        // Use the defined BACKEND_URL variable here
        const response = await fetch(`${BACKEND_URL}/agent/chat_text/${sessionId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_text: text })
        });

        if (response.ok) {
            const data = await response.json();
            addChatMessage(data.llm_response_text, "agent");
            handleAudioStreaming();
        } else {
            const errorText = await response.text();
            try {
                const data = JSON.parse(errorText);
                addChatMessage(`Error: ${data.message}`, "agent");
            } catch {
                addChatMessage(`Error: ${response.status} ${response.statusText}`, "agent");
            }
        }
    } catch (err) {
        console.error("Error sending text:", err);
        addChatMessage(`Error: ${err.message}`, "agent");
    }
});

chatTextInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        sendTextBtn.click();
    }
});

startRecordingChatBtn.addEventListener("click", async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        let recordedChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            const blob = new Blob(recordedChunks, { type: "audio/webm" });
            const formData = new FormData();
            formData.append("file", blob, "audio.webm");

            try {
                // Use the defined BACKEND_URL variable here
                const response = await fetch(`${BACKEND_URL}/agent/chat/${sessionId}`, {
                    method: "POST",
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    addChatMessage(data.user_transcript, "user");
                    addChatMessage(data.llm_response_text, "agent");
                    handleAudioStreaming();
                } else {
                    const errorText = await response.text();
                    try {
                        const data = JSON.parse(errorText);
                        addChatMessage(`Error: ${data.message}`, "agent");
                    } catch {
                        addChatMessage(`Error: ${response.status} ${response.statusText}`, "agent");
                    }
                }
            } catch (err) {
                console.error("Error sending audio:", err);
                addChatMessage(`Error: ${err.message}`, "agent");
            } finally {
                const recordingMessage = chatbox.querySelector('.chat-message.system');
                if (recordingMessage && recordingMessage.textContent === "Recording...") {
                    recordingMessage.remove();
                }
                startRecordingChatBtn.style.display = "inline-block";
                stopRecordingChatBtn.style.display = "none";
            }
        };

        mediaRecorder.start();
        startRecordingChatBtn.style.display = "none";
        stopRecordingChatBtn.style.display = "inline-block";
        addChatMessage("Recording...", "system");
    } catch (err) {
        alert("Microphone access denied or unavailable.");
        console.error(err);
    }
});

stopRecordingChatBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
    }
});

window.addEventListener('load', () => {
    console.log('Page loaded. Ready to chat!');
});