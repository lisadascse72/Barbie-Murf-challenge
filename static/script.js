// --- Chatbot UI Elements ---
const chatbox = document.getElementById("chatbox");
const chatTextInput = document.getElementById("chat-text-input");
const sendTextBtn = document.getElementById("sendTextBtn");
const startRecordingChatBtn = document.getElementById("startRecordingChatBtn");
const stopRecordingChatBtn = document.getElementById("stopRecordingChatBtn");
const llmResponseAudioPlayer = document.getElementById("llmResponseAudioPlayer");

let mediaRecorder;
let recordedChunks = [];
let audioContext;
let audioSource;
let audioQueue = [];
let isPlayingAudio = false;
let websocket;
let sessionId = "user_session_" + Date.now(); // Unique session ID

// --- Helper Functions for Chat UI ---
function addChatMessage(message, sender) {
    const messageElement = document.createElement("div");
    messageElement.classList.add("chat-message");
    messageElement.classList.add(sender === "user" ? "user-message" : "agent-message");
    messageElement.textContent = message;
    chatbox.appendChild(messageElement);
    chatbox.scrollTop = chatbox.scrollHeight; // Scroll to bottom
}

// Function to play base64 audio chunks
async function playAudioChunk(base64Audio) {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    const audioData = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0)).buffer;

    try {
        const audioBuffer = await audioContext.decodeAudioData(audioData);
        audioQueue.push(audioBuffer);
        if (!isPlayingAudio) {
            playNextAudioChunk();
        }
    } catch (e) {
        console.error("Error decoding audio data:", e);
    }
}

function playNextAudioChunk() {
    if (audioQueue.length > 0 && !isPlayingAudio) {
        isPlayingAudio = true;
        const audioBuffer = audioQueue.shift();
        audioSource = audioContext.createBufferSource();
        audioSource.buffer = audioBuffer;
        audioSource.connect(audioContext.destination);
        audioSource.start(0);

        audioSource.onended = () => {
            isPlayingAudio = false;
            playNextAudioChunk(); // Play the next chunk after current one ends
        };
    } else if (audioQueue.length === 0 && !isPlayingAudio) {
        // All chunks played, hide audio player or reset state
        llmResponseAudioPlayer.style.display = "none";
    }
}

// --- WebSocket Handling ---
function connectWebSocket() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        console.log("WebSocket already open.");
        return;
    }

    websocket = new WebSocket(`ws://localhost:8000/ws/chat/${sessionId}`);

    websocket.onopen = (event) => {
        console.log("WebSocket opened:", event);
        // Once connected, signal the backend to start streaming the last LLM response
        websocket.send(JSON.stringify({ type: "request_audio_stream" }));
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "audio_chunk") {
            playAudioChunk(data.audio);
            llmResponseAudioPlayer.style.display = "block"; // Show player if not visible
        } else if (data.type === "finished_audio") {
            console.log("Finished receiving audio from Murf WS.");
            // Ensure any buffered audio plays out
            if (audioQueue.length === 0 && !isPlayingAudio) {
                llmResponseAudioPlayer.style.display = "none";
            }
        } else if (data.type === "error") {
            console.error("WebSocket Error:", data.message);
            addChatMessage(`Error: ${data.message}`, "agent");
            llmResponseAudioPlayer.style.display = "none";
        }
    };

    websocket.onclose = (event) => {
        console.log("WebSocket closed:", event);
        if (event.wasClean) {
            console.log(`Code: ${event.code} Reason: ${event.reason}`);
        } else {
            console.error("WebSocket connection abruptly closed!");
        }
        isPlayingAudio = false; // Reset audio state
        audioQueue = [];
    };

    websocket.onerror = (error) => {
        console.error("WebSocket Error:", error);
        addChatMessage("Error connecting to voice agent. Please try again.", "agent");
        llmResponseAudioPlayer.style.display = "none";
        isPlayingAudio = false; // Reset audio state
        audioQueue = [];
    };
}


// --- Event Listeners ---

// Send text message
sendTextBtn.addEventListener("click", async () => {
    const text = chatTextInput.value.trim();
    if (!text) return;

    addChatMessage(text, "user");
    chatTextInput.value = ""; // Clear input

    try {
        const response = await fetch(`http://localhost:8000/agent/chat_text/${sessionId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_text: text })
        });

        const data = await response.json();
        if (response.ok) {
            addChatMessage(data.llm_response_text, "agent");
            // Initiate WebSocket for streaming audio
            connectWebSocket();
        } else {
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
    audioQueue = []; // Clear any pending audio
    isPlayingAudio = false;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            const blob = new Blob(recordedChunks, { type: "audio/webm" });
            
            // Send audio to backend for transcription and LLM processing
            const formData = new FormData();
            formData.append("file", blob, "audio.webm");

            try {
                const response = await fetch(`http://localhost:8000/agent/chat/${sessionId}`, {
                    method: "POST",
                    body: formData
                });

                const data = await response.json();
                if (response.ok) {
                    addChatMessage(data.user_transcript, "user");
                    addChatMessage(data.llm_response_text, "agent");
                    // Now, connect to the WebSocket for streaming audio
                    connectWebSocket();
                } else {
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
        addChatMessage("Recording...", "system"); // Indicate recording
    } catch (err) {
        alert("Microphone access denied or unavailable.");
        console.error(err);
    }
});

// Stop Recording for Chat
stopRecordingChatBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        startRecordingChatBtn.style.display = "inline-block";
        stopRecordingChatBtn.style.display = "none";
        // "Recording..." message will be replaced by actual transcription
        const recordingMessage = chatbox.querySelector('.chat-message.system');
        if (recordingMessage && recordingMessage.textContent === "Recording...") {
            recordingMessage.remove(); // Remove temporary message
        }
    }
});


// Initial check for WebSocket state on page load (optional)
window.addEventListener('load', () => {
    console.log('Page loaded. Ready to chat!');
});