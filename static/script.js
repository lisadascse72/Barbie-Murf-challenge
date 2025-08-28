// --- UI Elements and State ---
const chatbox = document.getElementById("chatbox");
const chatTextInput = document.getElementById("chat-text-input");
const sendTextBtn = document.getElementById("sendTextBtn");
const startRecordingChatBtn = document.getElementById("startRecordingChatBtn");
const stopRecordingChatBtn = document.getElementById("stopRecordingChatBtn");
const llmResponseAudioPlayer = document.getElementById("llmResponseAudioPlayer");

// API Key UI elements (removed from HTML, but variables kept for now)
const openSidebarBtn = document.getElementById("open-sidebar-btn");
const closeSidebarBtn = document.getElementById("close-sidebar-btn");
const sidebar = document.getElementById("settings-sidebar");
const apiKeyForm = document.getElementById("api-key-form");

let mediaRecorder;
let recordedChunks = [];
let sessionId = "user_session_" + Date.now(); // Unique session ID

// No longer storing keys from UI, will use .env keys via the backend
let apiKeys = {
    gemini: null,
    murf: null,
    assemblyai: null
};

// --- Helper Functions for UI ---
function addChatMessage(message, sender) {
    const messageElement = document.createElement("div");
    messageElement.classList.add("chat-message");
    messageElement.classList.add(sender === "user" ? "user-message" : "agent-message");
    messageElement.textContent = message;
    chatbox.appendChild(messageElement);
    chatbox.scrollTop = chatbox.scrollHeight;
}

function playAudioFromUrl(url) {
    llmResponseAudioPlayer.src = url;
    llmResponseAudioPlayer.style.display = "block";
    llmResponseAudioPlayer.play();
}


// --- Event Listeners ---

// Send text message
sendTextBtn.addEventListener("click", async () => {
    const text = chatTextInput.value.trim();
    if (!text) return;

    addChatMessage(text, "user");
    chatTextInput.value = "";
    llmResponseAudioPlayer.style.display = "none";

    // Build the request body without API keys
    const requestBody = { user_text: text };

    try {
        const response = await fetch(`http://localhost:8000/agent/chat_text/${sessionId}`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();
        if (response.ok) {
            addChatMessage(data.llm_response_text, "agent");
            if (data.llm_response_audio_url) {
                playAudioFromUrl(data.llm_response_audio_url);
            }
        } else {
            addChatMessage(`Error: ${data.message}`, "agent");
            throw new Error(data.message || "Failed to get LLM response");
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

// Start Recording for Chat
startRecordingChatBtn.addEventListener("click", async () => {
    recordedChunks = [];
    llmResponseAudioPlayer.style.display = "none";

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            const blob = new Blob(recordedChunks, { type: "audio/webm" });
            
            const formData = new FormData();
            formData.append("file", blob, "audio.webm");

            try {
                const response = await fetch(`http://localhost:8000/agent/chat/${sessionId}`, {
                    method: "POST",
                    headers: {}, // No headers needed as keys are now from .env
                    body: formData
                });

                const data = await response.json();
                if (response.ok) {
                    addChatMessage(data.user_transcript, "user");
                    addChatMessage(data.llm_response_text, "agent");
                    if (data.llm_response_audio_url) {
                        playAudioFromUrl(data.llm_response_audio_url);
                    }
                } else {
                    addChatMessage(`Error: ${data.message}`, "agent");
                    throw new Error(data.message || "Failed to process audio chat");
                }
            } catch (err) {
                console.error("Error sending audio:", err);
                addChatMessage(`Error: ${err.message}`, "agent");
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
        startRecordingChatBtn.style.display = "inline-block";
        stopRecordingChatBtn.style.display = "none";
        const recordingMessage = chatbox.querySelector('.chat-message.system');
        if (recordingMessage && recordingMessage.textContent === "Recording...") {
            recordingMessage.remove();
        }
    }
});

window.addEventListener('load', () => {
    console.log('Page loaded. Ready to chat!');
});