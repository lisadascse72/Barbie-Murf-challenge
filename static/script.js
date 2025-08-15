// script.js

// ---------- Core Conversational AI Agent Elements ----------
const queryLLMBtn = document.getElementById("queryLLMBtn"); // Main button for VOICE chat
const textInput = document.getElementById("textInput"); // Text area for TYPED chat
const sendTextBtn = document.getElementById("sendTextBtn"); // Button to send typed text
const chatDisplay = document.getElementById("chatDisplay"); // Div for displaying chat history
const llmResponseAudio = document.getElementById("llmResponseAudio"); // Audio player for AI voice responses
const sessionIdDisplay = document.getElementById("sessionIdDisplay"); // Displays current session ID
const llmStatusMessage = document.getElementById("llmStatusMessage"); // Displays dynamic status messages

let mediaRecorderLLM; // Dedicated media recorder for voice chat
let recordedChunksLLM = [];
let isRecordingLLM = false;
let currentSessionId = null;

// --- Custom Modal/Alert Implementation (Replaces alert()) ---
function showModal(message, title = "Notification") {
    const modalId = 'customAlertModal';
    let modal = document.getElementById(modalId);

    if (!modal) {
        modal = document.createElement('div');
        modal.id = modalId;
        modal.style.cssText = `
            position: fixed;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            background-color: #333;
            border: 1px solid #555;
            border-radius: 8px;
            padding: 20px;
            z-index: 1000;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            color: #eee;
            max-width: 90%;
            text-align: center;
            font-family: 'Orbitron', sans-serif;
        `;
        const modalTitle = document.createElement('h3');
        modalTitle.style.color = '#fff';
        modalTitle.style.marginBottom = '10px';
        modalTitle.id = 'modalTitle';
        modal.appendChild(modalTitle);

        const modalMessage = document.createElement('p');
        modalMessage.style.marginBottom = '20px';
        modalMessage.id = 'modalMessage';
        modal.appendChild(modalMessage);

        const closeButton = document.createElement('button');
        closeButton.textContent = 'OK';
        closeButton.style.cssText = `
            background-color: #00fff7;
            color: black;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            font-family: 'Orbitron', sans-serif;
            box-shadow: 0 0 10px #00fff7;
            transition: transform 0.2s ease;
        `;
        closeButton.onmouseover = () => closeButton.style.transform = 'scale(1.05)';
        closeButton.onmouseout = () => closeButton.style.transform = 'scale(1)';
        closeButton.onclick = () => modal.style.display = 'none';
        modal.appendChild(closeButton);
        document.body.appendChild(modal);
    }

    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    modal.style.display = 'block';
}
// --- End Custom Modal ---

// Function to generate a unique session ID
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Function to get or set session ID from/to URL
function getOrCreateSessionId() {
    const urlParams = new URLSearchParams(window.location.search);
    let sessionId = urlParams.get('session_id');
    if (!sessionId) {
        sessionId = generateSessionId();
        urlParams.set('session_id', sessionId);
        window.history.replaceState({}, '', `${window.location.pathname}?${urlParams}`);
    }
    sessionIdDisplay.textContent = `Session ID: ${sessionId}`;
    return sessionId;
}

// Append a message to the chat display
function appendMessage(role, text) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('chat-message', role);
    messageDiv.textContent = text;
    chatDisplay.appendChild(messageDiv);
    chatDisplay.scrollTop = chatDisplay.scrollHeight; // Scroll to bottom
}

// Function to handle LLM interaction (common for both audio and text inputs)
async function sendToLLM(userInput, inputType = 'audio') {
    llmStatusMessage.textContent = "🧠 Processing...";
    llmResponseAudio.style.display = "none"; // Hide audio player while processing
    llmResponseAudio.src = ''; // Clear previous audio source

    let apiEndpoint = `http://localhost:8000/agent/chat/${currentSessionId}`;
    let requestBody;
    let requestHeaders = {};
    
    if (inputType === 'audio') {
        requestBody = new FormData();
        requestBody.append("file", userInput, `chat_query_${Date.now()}.webm`);
        llmStatusMessage.textContent = "⏳ Sending audio to LLM...";
    } else { // inputType === 'text'
        apiEndpoint = `http://localhost:8000/agent/chat_text/${currentSessionId}`;
        requestBody = JSON.stringify({ user_text: userInput });
        requestHeaders = { "Content-Type": "application/json" };
        llmStatusMessage.textContent = "⏳ Sending text to LLM...";
    }

    try {
        const response = await fetch(apiEndpoint, {
            method: "POST",
            headers: requestHeaders,
            body: requestBody,
        });

        const data = await response.json();

        if (response.ok && data.llm_response_audio_url) {
            // Append user message based on input type
            if (inputType === 'audio') {
                appendMessage('user', data.user_transcript);
            } else {
                appendMessage('user', data.user_text);
            }
            appendMessage('llm', data.llm_response_text); // Add LLM's response

            llmResponseAudio.src = data.llm_response_audio_url;
            llmResponseAudio.style.display = "block"; // Make audio player visible
            llmStatusMessage.textContent = "🔊 Playing LLM response...";

            llmResponseAudio.play();
            llmResponseAudio.onended = () => {
                // Automatically start recording again ONLY if the last user input was audio
                if (inputType === 'audio' && isRecordingLLM) { // Check isRecordingLLM to ensure it wasn't manually stopped
                    startRecordingLLM(); // Continue the voice conversation
                } else {
                    llmStatusMessage.textContent = "✅ Ready for new input.";
                }
            };
        } else {
            llmStatusMessage.textContent = `❌ Agent response failed: ${data.detail || 'Unknown error'}`;
            showModal(`Agent response failed: ${data.detail || 'Unknown error'}`, "Agent Error");
        }
    } catch (err) {
        console.error("Agent chat error:", err);
        llmStatusMessage.textContent = `❌ Agent chat request failed: ${err.message}`;
        showModal(`Agent chat request failed: ${err.message}`, "Network Error");
    } finally {
        // Ensure buttons are reset if processing failed
        if (inputType === 'audio' && isRecordingLLM === false) { // If audio was stopped or failed
             queryLLMBtn.textContent = "🎤 Start Voice Chat";
             queryLLMBtn.classList.remove('recording-active');
        }
        textInput.value = ''; // Clear text input after sending
    }
}

// Function to start recording audio for LLM chat
async function startRecordingLLM() {
    recordedChunksLLM = [];
    llmStatusMessage.textContent = "🟢 Recording your voice...";
    queryLLMBtn.textContent = "⏹️ Stop Recording";
    queryLLMBtn.classList.add('recording-active'); // Add class for visual feedback

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorderLLM = new MediaRecorder(stream);

        mediaRecorderLLM.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunksLLM.push(e.data);
        };

        mediaRecorderLLM.onstop = async () => {
            isRecordingLLM = false; // Reset recording state
            queryLLMBtn.classList.remove('recording-active'); // Remove active recording class

            if (recordedChunksLLM.length === 0) {
                llmStatusMessage.textContent = "No audio recorded. Click 'Start Voice Chat' to try again.";
                queryLLMBtn.textContent = "🎤 Start Voice Chat";
                return;
            }

            const blob = new Blob(recordedChunksLLM, { type: "audio/webm" });
            await sendToLLM(blob, 'audio');
        };

        mediaRecorderLLM.start();
        isRecordingLLM = true;

    } catch (err) {
        showModal("Microphone access denied or error starting voice chat. Please ensure microphone permissions are granted.", "Microphone Error");
        console.error(err);
        llmStatusMessage.textContent = "🔴 Microphone access denied for voice chat.";
        queryLLMBtn.textContent = "🎤 Start Voice Chat";
        queryLLMBtn.classList.remove('recording-active');
    }
}

// Event listener for the main button (Start/Stop Voice Chat)
queryLLMBtn.addEventListener("click", () => {
    if (!isRecordingLLM) {
        // Removed the check and confirm that clears chatDisplay.innerHTML
        llmResponseAudio.style.display = "none"; // Hide audio player initially
        llmResponseAudio.src = ''; // Clear audio source
        
        startRecordingLLM(); // Start the voice conversation
    } else {
        // Stop the voice conversation
        mediaRecorderLLM.stop();
        isRecordingLLM = false;
        queryLLMBtn.textContent = "🎤 Start Voice Chat";
        llmStatusMessage.textContent = "Voice conversation stopped. You can also type messages.";
    }
});

// Event listener for the Send Text button
sendTextBtn.addEventListener("click", async () => {
    const userText = textInput.value.trim();
    if (!userText) {
        showModal("Please type a message to send.", "Empty Message");
        return;
    }

    // If currently recording voice, stop it before sending text
    if (isRecordingLLM) {
        mediaRecorderLLM.stop();
        isRecordingLLM = false;
        queryLLMBtn.textContent = "🎤 Start Voice Chat";
        queryLLMBtn.classList.remove('recording-active');
        llmStatusMessage.textContent = "Voice recording stopped. Sending your text message...";
    }

    await sendToLLM(userText, 'text');
});

// Initialize session ID on page load
document.addEventListener('DOMContentLoaded', () => {
    currentSessionId = getOrCreateSessionId();
    llmStatusMessage.textContent = "Welcome! Type your message or click 'Start Voice Chat'.";
});
