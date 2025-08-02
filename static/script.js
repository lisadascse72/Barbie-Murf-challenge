let synth = window.speechSynthesis;
let voices = [];
let utterance;
let progressInterval;

const playBtn = document.getElementById("playBtn");
const voiceSelect = document.getElementById("voiceSelect");
const progressBar = document.getElementById("progressBar");
const textInput = document.getElementById("text-input");

function populateVoices() {
  voices = synth.getVoices();
  voiceSelect.innerHTML = '';
  voices.forEach((voice, i) => {
    const option = document.createElement("option");
    option.textContent = `${voice.name} (${voice.lang})`;
    option.value = i;
    voiceSelect.appendChild(option);
  });
}

function speak() {
  if (synth.speaking) {
    synth.cancel();
    playBtn.textContent = "▶️";
    clearInterval(progressInterval);
    progressBar.style.width = "0%";
    return;
  }

  const text = textInput.value;
  utterance = new SpeechSynthesisUtterance(text);
  utterance.voice = voices[voiceSelect.value];

  let durationEstimate = text.split(" ").length * 450;
  let startTime = Date.now();

  utterance.onstart = () => {
    playBtn.textContent = "⏸️";

    progressInterval = setInterval(() => {
      let elapsed = Date.now() - startTime;
      let progress = Math.min((elapsed / durationEstimate) * 100, 100);
      progressBar.style.width = `${progress}%`;
    }, 100);
  };

  utterance.onend = () => {
    playBtn.textContent = "▶️";
    clearInterval(progressInterval);
    progressBar.style.width = "0%";
  };

  synth.speak(utterance);
}

playBtn.addEventListener("click", speak);

if (speechSynthesis.onvoiceschanged !== undefined) {
  speechSynthesis.onvoiceschanged = populateVoices;
}
populateVoices();
