// --- Chatbot UI Elements ---
const chatbox = document.getElementById("chatbox");
const chatTextInput = document.getElementById("chat-text-input");
const sendTextBtn = document.getElementById("sendTextBtn");
const startRecordingChatBtn = document.getElementById("startRecordingChatBtn");
const stopRecordingChatBtn = document.getElementById("stopRecordingChatBtn");
const llmResponseAudioPlayer = document.getElementById("llmResponseAudioPlayer");

let mediaRecorder;
let recordedChunks = [];
let websocket;
let sessionId = "user_session_" + Date.now(); // Unique session ID

// New variable to hold audio chunks from the server
let serverAudioChunks = [];

// --- Helper Functions for Chat UI ---
function addChatMessage(message, sender) {
    const messageElement = document.createElement("div");
    messageElement.classList.add("chat-message");
    messageElement.classList.add(sender === "user" ? "user-message" : "agent-message");
    messageElement.textContent = message;
    chatbox.appendChild(messageElement);
    chatbox.scrollTop = chatbox.scrollHeight; // Scroll to bottom
}

// --- WebSocket Handling ---
function connectWebSocket() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        console.log("WebSocket already open.");
        return;
    }

    // Reset the server's audio chunks every time we start a new session
    serverAudioChunks = [];
    llmResponseAudioPlayer.style.display = "none";
    
    websocket = new WebSocket(`ws://localhost:8000/ws/chat/${sessionId}`);

    websocket.onopen = (event) => {
        console.log("WebSocket opened:", event);
        // Once connected, signal the backend to start streaming the last LLM response
        websocket.send(JSON.stringify({ type: "request_audio_stream" }));
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "audio_chunk") {
            // Push each base64 audio chunk into our array
            serverAudioChunks.push(data.audio);
            // For debugging, you can log this
            console.log("Received a streaming audio chunk.");
        } else if (data.type === "finished_audio") {
            console.log("Finished receiving audio from Murf WS. Now playing the full audio.");
           
            // Combine all base64 chunks into a single string
            const fullBase64Audio = serverAudioChunks.join("");
            
            if (fullBase64Audio) {
                // Convert the combined base64 string to a Blob
                const audioBlob = new Blob([Uint8Array.from(atob(fullBase64Audio), c => c.charCodeAt(0))], { type: 'audio/wav' });

                // Create a URL for the Blob and set it as the audio player's source
                const audioUrl = URL.createObjectURL(audioBlob);
                llmResponseAudioPlayer.src = audioUrl;
                llmResponseAudioPlayer.style.display = "block";
                llmResponseAudioPlayer.play();

                // Clean up the URL after a short delay to avoid memory leaks
                llmResponseAudioPlayer.onended = () => {
                    URL.revokeObjectURL(audioUrl);
                    llmResponseAudioPlayer.style.display = "none";
                };
            } else {
                console.error("Received finished signal, but no audio chunks were collected.");
            }

        } else if (data.type === "error") {
            console.error("WebSocket Error:", data.message);
            addChatMessage(`Error: ${data.message}`, "agent");
            llmResponseAudioPlayer.style.display = "none";
        }
    };

    websocket.onclose = (event) => {
        console.log("WebSocket closed:", event);
    };

    websocket.onerror = (error) => {
        console.error("WebSocket Error:", error);
        addChatMessage("Error connecting to voice agent. Please try again.", "agent");
        llmResponseAudioPlayer.style.display = "none";
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
    serverAudioChunks = []; // Reset audio chunks before recording
    llmResponseAudioPlayer.style.display = "none";

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