import { useEffect, useRef, useState } from "react";

export function useSpeechToText({ onFinalText, autoRestart = false }) {
  const recognitionRef = useRef(null);
  const networkRetryRef = useRef(null);
  const restartRef = useRef(null);
  const networkRetryCountRef = useRef(0);
  const autoRestartRef = useRef(autoRestart);
  const stopRequestedRef = useRef(false);
  const [listening, setListening] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const [transcript, setTranscript] = useState("");
  const [heardText, setHeardText] = useState("");

  useEffect(() => {
    autoRestartRef.current = autoRestart;
  }, [autoRestart]);

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  const supported = Boolean(SpeechRecognition);

  function startListening() {
    setSpeechError("");
    stopRequestedRef.current = false;

    if (restartRef.current) {
      clearTimeout(restartRef.current);
      restartRef.current = null;
    }

    if (networkRetryRef.current) {
      clearTimeout(networkRetryRef.current);
      networkRetryRef.current = null;
    }

    if (!supported) {
      setSpeechError("Speech recognition works best in Chrome or Edge.");
      return;
    }

    if (recognitionRef.current) {
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      networkRetryCountRef.current = 0;
      setListening(true);
    };

    recognition.onerror = (event) => {
      if (event.error === "aborted") {
        setListening(false);
        recognitionRef.current = null;
        return;
      }

      if (event.error === "network" && networkRetryCountRef.current < 1) {
        networkRetryCountRef.current += 1;
        setSpeechError("Speech service had a network error. Retrying...");
        networkRetryRef.current = window.setTimeout(() => {
          networkRetryRef.current = null;
          startListening();
        }, 1000);
        setListening(false);
        return;
      }

      setSpeechError(event.error || "Speech recognition failed.");
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;

      if (!stopRequestedRef.current && autoRestartRef.current && !restartRef.current) {
        networkRetryCountRef.current = 0;
        restartRef.current = window.setTimeout(() => {
          restartRef.current = null;
          startListening();
        }, 650);
      }
    };

    recognition.onresult = (event) => {
      let nextTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const resultText = result[0].transcript.trim();

        if (result.isFinal && resultText) {
          onFinalText(resultText);
          setHeardText((currentHeardText) => {
            const nextHeardText = currentHeardText
              ? `${currentHeardText} ${resultText}`
              : resultText;
            return nextHeardText;
          });
        } else {
          nextTranscript = result[0].transcript;
        }
      }

      setTranscript(nextTranscript);
    };

    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopListening() {
    stopRequestedRef.current = true;

    if (restartRef.current) {
      clearTimeout(restartRef.current);
      restartRef.current = null;
    }

    if (networkRetryRef.current) {
      clearTimeout(networkRetryRef.current);
      networkRetryRef.current = null;
    }

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
    transcript,
    heardText,
    startListening,
    stopListening,
  };
}