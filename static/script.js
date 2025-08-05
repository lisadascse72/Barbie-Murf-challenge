// ---------- TTS Section ----------
const playBtn = document.getElementById("playBtn");
const progressBar = document.getElementById("progressBar");
const textInput = document.getElementById("text-input");
const audioPlayer = document.getElementById("audioPlayer");

playBtn.addEventListener("click", async () => {
  const text = textInput.value.trim();
  if (!text) return alert("Please enter some text.");

  playBtn.textContent = "🔄 Generating...";
  progressBar.style.width = "20%";

  try {
    const response = await fetch("http://localhost:8000/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });

    const data = await response.json();
    if (!data.audio_url) throw new Error("No audio URL received");

    audioPlayer.src = data.audio_url;
    audioPlayer.style.display = "block";
    await audioPlayer.play();

    progressBar.style.width = "100%";
    playBtn.textContent = "▶️ Play Again";
  } catch (err) {
    alert("Error: " + err.message);
    playBtn.textContent = "❌ Retry";
  } finally {
    setTimeout(() => {
      progressBar.style.width = "0%";
    }, 4000);
  }
});


// ---------- Echo Bot Section ----------
const recordToggleBtn = document.getElementById("recordToggleBtn");
const playRecordedBtn = document.getElementById("playRecordedBtn");
const recordedAudio = document.getElementById("recordedAudio");

let mediaRecorder;
let recordedChunks = [];
let isRecording = false;

recordToggleBtn.addEventListener("click", async () => {
  if (!isRecording) {
    // Start recording
    recordedChunks = [];
    recordedAudio.style.display = "none";

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: "audio/webm" });
        const audioURL = URL.createObjectURL(blob);
        recordedAudio.src = audioURL;
        recordedAudio.style.display = "block";
      };

      mediaRecorder.start();
      recordToggleBtn.textContent = "⏹️ Stop Recording";
      isRecording = true;
    } catch (err) {
      alert("Microphone access denied or unavailable.");
      console.error(err);
    }
  } else {
    // Stop recording
    mediaRecorder.stop();
    recordToggleBtn.textContent = "🎤 Start Recording";
    isRecording = false;
  }
});

playRecordedBtn.addEventListener("click", () => {
  if (recordedAudio.src) {
    recordedAudio.play();
  } else {
    alert("No recording available. Record something first.");
  }
});
