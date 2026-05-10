import { useEffect, useRef, useState } from "react";

import {
  attachVideoElement,
  detachVideoElement,
  stopMediaStream,
} from "./mediaStreamUtils";

const WS_URL_OVERRIDE = import.meta.env.VITE_WS_URL;

function getWsUrl() {
  if (WS_URL_OVERRIDE) {
    return WS_URL_OVERRIDE;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname;
  // Avoid falling back to localhost addresses. If hostname is not present
  // or is a localhost address, fall back to the known WSL host IP.
  if (host && host !== "localhost" && host !== "127.0.0.1") {
    return `${protocol}://${host}:8001/ws/asl`;
  }
  return `${protocol}://172.29.100.19:8001/ws/asl`;
}

const CAMERA_CONSTRAINTS = {
  video: {
    facingMode: "user",
    width: { ideal: 1280 },
    height: { ideal: 720 },
    aspectRatio: { ideal: 1.7777778 },
  },
  audio: false,
};

export function useAslStream() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const shouldReconnectRef = useRef(true);

  const [mediaStream, setMediaStream] = useState(null);
  const [connected, setConnected] = useState(false);
  const [cameraOn, setCameraOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [aslEnabled, setAslEnabled] = useState(true);
  const [showCaptions, setShowCaptions] = useState(true);
  const [activeTab, setActiveTab] = useState("captions");
  const [prediction, setPrediction] = useState("Waiting...");
  const [confidence, setConfidence] = useState(0);
  const [handsCount, setHandsCount] = useState(0);
  const [translationWords, setTranslationWords] = useState([]);
  const [aslCaptureState, setAslCaptureState] = useState("ready");
  const [modelName, setModelName] = useState("unknown");
  const [inferenceDevice, setInferenceDevice] = useState("unknown");
  const [inferenceMode, setInferenceMode] = useState("idle");
  const [status, setStatus] = useState("Starting...");
  const [timeNow, setTimeNow] = useState("");
  const [manualMode, setManualMode] = useState(false);
  const [manualCaptureState, setManualCaptureState] = useState("manual_ready");
  const [countdownMs, setCountdownMs] = useState(0);
  const lastCommittedWordRef = useRef("");
  const cameraOffResetSentRef = useRef(false);
  const manualCommandRef = useRef(null);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeNow(now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Countdown timer for manual capture
  // Uses a ref to avoid stale closure issues with manualCommandRef
  const countdownActiveRef = useRef(false);

  useEffect(() => {
    if (countdownMs <= 0) {
      countdownActiveRef.current = false;
      return;
    }
    countdownActiveRef.current = true;

    const timer = setTimeout(() => {
      setCountdownMs(prev => {
        const next = prev - 100;
        if (next <= 0) {
          // Countdown finished — set command synchronously via ref BEFORE next render
          // (manualCommandRef is a ref, safe to write outside setState)
          manualCommandRef.current = "start";
          countdownActiveRef.current = false;
          return 0;
        }
        return next;
      });
    }, 100);

    return () => clearTimeout(timer);
  }, [countdownMs]);

  // Keyboard listener for manual mode (R = start, Esc = cancel)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!cameraOn || !manualMode) return;

      // Ignore keys if user is typing
      const tag = e.target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.target.isContentEditable) return;

      if (e.key.toLowerCase() === "r") {
        e.preventDefault();
        // Allow start only when ready/result and not already counting down or capturing
        const canStart =
          (manualCaptureState === "manual_ready" || manualCaptureState === "manual_result") &&
          countdownMs === 0;
        if (canStart) {
          setCountdownMs(1000);
          manualCommandRef.current = null; // will be set to "start" when countdown hits 0
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        if (countdownMs > 0 || manualCaptureState === "manual_capturing") {
          setCountdownMs(0);
          manualCommandRef.current = "cancel";
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [cameraOn, manualMode, manualCaptureState, countdownMs]);

  useEffect(() => {
    if (cameraOn && mediaStream) {
      attachVideoElement(videoRef.current, mediaStream);
      return;
    }
    detachVideoElement(videoRef.current);
  }, [cameraOn, mediaStream]);

  useEffect(() => {
    let mounted = true;

    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS);
        if (!mounted) { stopMediaStream(stream); return; }
        stopMediaStream(streamRef.current);
        streamRef.current = stream;
        setMediaStream(stream);
        setStatus("Camera active");
        setCameraOn(true);
      } catch (error) {
        console.error(error);
        setStatus("Camera permission denied");
        setCameraOn(false);
      }
    };

    const connectWebSocket = () => {
      if (
        socketRef.current &&
        (socketRef.current.readyState === WebSocket.OPEN ||
          socketRef.current.readyState === WebSocket.CONNECTING)
      ) return;

      console.log("WS URL:", getWsUrl());
      const socket = new WebSocket(getWsUrl());
      socketRef.current = socket;
      setStatus("Connecting to backend...");

      socket.onopen = () => {
        setConnected(true);
        setStatus("Backend connected");
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const text = typeof data.text === "string" ? data.text : "Waiting...";
          const confidenceValue = Number(data.confidence) || 0;
          const handsValue = Number.isInteger(data.hands_count) ? data.hands_count : 0;

          // Trust the backend state machine completely — no frontend overrides.
          setPrediction(text);
          setConfidence(confidenceValue);
          setHandsCount(handsValue);
          setAslCaptureState(data.asl_capture_state || "ready");
          if (data.manual_capture_state) {
            setManualCaptureState(data.manual_capture_state);
          }

          if (
            text &&
            text !== "Waiting..." &&
            text !== "null" &&
            text !== "ASL off" &&
            text !== "Model unavailable" &&
            confidenceValue > 0 &&
            text !== lastCommittedWordRef.current
          ) {
            lastCommittedWordRef.current = text;
            setTranslationWords((currentWords) => {
              const nextWords = [...currentWords, text];
              return nextWords.slice(-24);
            });
          }

          setModelName(data.model_name || "unknown");
          setInferenceDevice(data.inference_device || "unknown");
          setInferenceMode(data.inference_mode || "unknown");
          setStatus(data.status || "Idle");
        } catch (error) {
          console.error("WebSocket message parse error:", error);
          setStatus("Invalid backend message");
        }
      };

      socket.onerror = () => {
        setConnected(false);
        setStatus("WebSocket error");
      };

      socket.onclose = () => {
        setConnected(false);
        if (!shouldReconnectRef.current) { setStatus("Backend disconnected"); return; }
        setStatus("Reconnecting backend...");
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = setTimeout(connectWebSocket, 1200);
      };
    };

    startCamera();
    connectWebSocket();

    return () => {
      mounted = false;
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
      stopMediaStream(streamRef.current);
      streamRef.current = null;
      detachVideoElement(videoRef.current);
      setMediaStream(null);
      const sock = socketRef.current;
      if (sock) {
        if (sock.readyState === WebSocket.OPEN || sock.readyState === WebSocket.CONNECTING) sock.close();
        socketRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (!videoRef.current || !canvasRef.current || !socketRef.current) return;
      if (socketRef.current.readyState !== WebSocket.OPEN) return;

      console.log("[ASL] cameraOn", cameraOn, "aslCaptureState", aslCaptureState);

      // If camera is off, send reset message
      if (!cameraOn) {
        if (cameraOffResetSentRef.current) return;
        cameraOffResetSentRef.current = true;
        socketRef.current.send(JSON.stringify({
          asl_enabled: aslEnabled,
          camera_on: false,
          frame: null,
        }));
        return;
      }

      cameraOffResetSentRef.current = false;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const context = canvas.getContext("2d");
      if (!video.videoWidth || !video.videoHeight) return;

      const targetWidth = 640;
      const targetHeight = Math.round((video.videoHeight / video.videoWidth) * targetWidth);
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Consume the pending manual command (only send it once)
      const cmd = manualCommandRef.current;
      manualCommandRef.current = null;

      socketRef.current.send(JSON.stringify({
        frame: canvas.toDataURL("image/jpeg", 0.65),
        asl_enabled: aslEnabled,
        camera_on: true,
        mode: manualMode ? "manual" : "auto",
        manual_command: cmd || null,
      }));
    }, 50);

    return () => clearInterval(interval);
  }, [cameraOn, aslEnabled, manualMode]);

  const stopCamera = () => {
    stopMediaStream(streamRef.current);
    streamRef.current = null;
    detachVideoElement(videoRef.current);
    setMediaStream(null);
    setTranslationWords([]);
    lastCommittedWordRef.current = "";
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS);
      streamRef.current = stream;
      setMediaStream(stream);
      setStatus("Camera active");
      setCameraOn(true);
    } catch (error) {
      console.error(error);
      setStatus("Camera permission denied");
      setCameraOn(false);
    }
  };

  const toggleCamera = async () => {
    if (cameraOn) {
      stopCamera();
      setCameraOn(false);
      setStatus("Camera off");
      setPrediction("Waiting...");
      setConfidence(0);
      setHandsCount(0);
      setModelName("unknown");
      setInferenceDevice("idle");
      setInferenceMode("camera-off");
      setAslCaptureState("ready");
      setManualCaptureState("manual_ready");
      setCountdownMs(0);
      manualCommandRef.current = null;
      return;
    }
    await startCamera();
  };

  const toggleAsl = () => {
    setAslEnabled((previous) => {
      const nextEnabled = !previous;

      if (!nextEnabled) {
        setTranslationWords([]);
        lastCommittedWordRef.current = "";
        setPrediction("Waiting...");
        setConfidence(0);
      }

      return nextEnabled;
    });
  };

  const startManualCapture = () => {
    if (!cameraOn || !manualMode) return;
    const canStart =
      (manualCaptureState === "manual_ready" || manualCaptureState === "manual_result") &&
      countdownMs === 0;
    if (!canStart) return;
    setCountdownMs(1000);
    manualCommandRef.current = null;
  };

  const cancelManualCapture = () => {
    if (!manualMode) return;
    setCountdownMs(0);
    manualCommandRef.current = "cancel";
  };

  return {
    videoRef,
    canvasRef,
    connected,
    cameraOn,
    micOn,
    aslEnabled,
    showCaptions,
    activeTab,
    prediction,
    confidence,
    handsCount,
    aslCaptureState,
    translationWords,
    modelName,
    inferenceDevice,
    inferenceMode,
    status,
    timeNow,
    manualMode,
    manualCaptureState,
    countdownMs,
    setManualMode,
    setMicOn,
    setAslEnabled,
    setShowCaptions,
    setActiveTab,
    toggleAsl,
    toggleCamera,
    startManualCapture,
    cancelManualCapture,
  };
}