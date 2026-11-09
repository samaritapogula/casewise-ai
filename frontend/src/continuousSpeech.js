/** Continuous browser speech recognition; session transcripts are kept locally for review. */
export function createContinuousSpeech({ Recognition, lang, onTranscript, onInterim, onListening, onError, onStatus = () => {}, schedule = setTimeout, cancelSchedule = clearTimeout, clock = Date.now }) {
  let requested = false;
  let stopping = false;
  let current = null;
  let pendingRestart = null;
  let collected = "";
  let earlyEnds = 0;
  const joinParts = (...parts) => parts.map(s => (s || "").trim()).filter(Boolean).join(" ");

  function clearRestart() {
    if (pendingRestart !== null) {
      cancelSchedule(pendingRestart);
      pendingRestart = null;
    }
  }

  function startSession() {
    if (!requested || stopping) return;
    const base = collected;
    const recognition = new Recognition();
    current = recognition;
    const sessionStarted = clock();
    let receivedSpeech = false;

    recognition.lang = lang;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = event => {
      if (current !== recognition || (!requested && !stopping)) return;
      const finalResults = [];
      const interimResults = [];
      for (let index = 0; index < event.results.length; index += 1) {
        const item = event.results[index];
        const words = item[0]?.transcript || "";
        if (item.isFinal) finalResults.push(words);
        else interimResults.push(words);
      }
      const finalText = joinParts(...finalResults);
      if (finalText) {
        receivedSpeech = true;
        const updated = joinParts(base, finalText).slice(0, 2000);
        if (updated !== collected) {
          collected = updated;
          onTranscript(updated);
        }
      }
      onInterim(joinParts(...interimResults));
    };

    recognition.onerror = event => {
      if (current !== recognition || (!requested && !stopping)) return;
      const code = event.error || "unknown";
      if (code === "no-speech") {
        onStatus("Waiting for speech… reconnecting if needed");
        return;
      }
      if (code === "aborted" && !requested) return;
      const errors = {
        "not-allowed": "Microphone permission was denied. Allow access in browser settings.",
        "service-not-allowed": "The browser blocked its speech service. Try Chrome or type your message.",
        "language-not-supported": "Speech recognition is not available for this language in your browser.",
        "audio-capture": "No microphone was found, or it is unavailable.",
        "network": "The speech recognition service is unavailable. Check your connection.",
      };
      requested = false;
      stopping = false;
      clearRestart();
      current = null;
      try { recognition.abort(); } catch { /* Browser already ended recognition. */ }
      onListening(false);
      onInterim("");
      onError(errors[code] || "Speech recognition stopped unexpectedly. You can restart it or type.");
    };

    recognition.onend = () => {
      if (current !== recognition) return;
      current = null;
      onInterim("");
      if (!requested || stopping) {
        stopping = false;
        onListening(false);
        onStatus("Stopped — review your transcription");
        return;
      }
      // Some browsers end a session even with continuous=true. Restart after a pause.
      // Bail out only if the browser repeatedly rejects startup immediately.
      earlyEnds = receivedSpeech || clock() - sessionStarted >= 1300 ? 0 : earlyEnds + 1;
      if (earlyEnds >= 5) {
        requested = false;
        onListening(false);
        onStatus("Not recording");
        onError("The browser repeatedly ended microphone sessions. Check microphone permissions or try another browser.");
        return;
      }
      onStatus("Reconnecting microphone after pause…");
      clearRestart();
      pendingRestart = schedule(() => {
        pendingRestart = null;
        startSession();
      }, 400);
    };

    try {
      recognition.start();
      onStatus("Listening — pauses are OK. Press Stop when finished.");
    } catch {
      if (current !== recognition) return;
      current = null;
      requested = false;
      stopping = false;
      onListening(false);
      onInterim("");
      onError("The browser could not restart speech recognition. Try the microphone again.");
    }
  }

  return {
    start(initialText = "") {
      if (requested || stopping) return;
      collected = String(initialText || "").slice(0, 2000);
      requested = true;
      earlyEnds = 0;
      onError("");
      onListening(true);
      startSession();
    },
    stop() {
      if (!requested || stopping) return;
      requested = false;
      clearRestart();
      if (!current) {
        onListening(false);
        onInterim("");
        onStatus("Stopped — review your transcription");
        return;
      }
      stopping = true;
      onStatus("Finishing transcription…");
      try {
        current.stop(); // Allows the last recognized words to arrive before onend.
      } catch {
        current = null;
        stopping = false;
        onListening(false);
        onInterim("");
      }
    },
    cancel() {
      requested = false;
      stopping = false;
      clearRestart();
      const recognition = current;
      current = null;
      try { recognition?.abort(); } catch { /* Nothing active. */ }
      onListening(false);
      onInterim("");
    },
  };
}
