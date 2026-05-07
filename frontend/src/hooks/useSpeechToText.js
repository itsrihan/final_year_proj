import { useRef, useState } from "react";

export function useSpeechToText({ onFinalText }) {
  const recognitionRef = useRef(null);
  const latestTranscriptRef = useRef("");
  const [listening, setListening] = useState(false);
  const [speechError, setSpeechError] = useState("");

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  const supported = Boolean(SpeechRecognition);

  function startListening() {
    setSpeechError("");

    if (!supported) {
      setSpeechError("Speech recognition works best in Chrome or Edge.");
      return;
    }

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      latestTranscriptRef.current = "";
      setListening(true);
    };

    recognition.onerror = (event) => {
      setSpeechError(event.error || "Speech recognition failed.");
      setListening(false);
    };

    recognition.onend = () => {
      const cleanText = latestTranscriptRef.current.trim();
      if (cleanText) {
        onFinalText(cleanText);
      }
      setListening(false);
    };

    recognition.onresult = (event) => {
      let transcript = "";

      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        transcript += result[0].transcript;
      }

      latestTranscriptRef.current = transcript;
    };

    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopListening() {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    setListening(false);
  }

  return {
    supported,
    listening,
    speechError,
    startListening,
    stopListening,
  };
}