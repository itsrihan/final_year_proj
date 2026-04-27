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
  const host = window.location.hostname || "localhost";
  return `${protocol}://${host}:8000/ws/asl`;
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
  const [modelName, setModelName] = useState("unknown");
  const [inferenceDevice, setInferenceDevice] = useState("unknown");
  const [inferenceMode, setInferenceMode] = useState("idle");
  const [status, setStatus] = useState("Starting...");
  const [timeNow, setTimeNow] = useState("");
  const lastCommittedWordRef = useRef("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeNow(now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

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
      if (!cameraOn) return;
      if (!videoRef.current || !canvasRef.current || !socketRef.current) return;
      if (socketRef.current.readyState !== WebSocket.OPEN) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const context = canvas.getContext("2d");
      if (!video.videoWidth || !video.videoHeight) return;

      const targetWidth = 640;
      const targetHeight = Math.round((video.videoHeight / video.videoWidth) * targetWidth);
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      socketRef.current.send(JSON.stringify({
        frame: canvas.toDataURL("image/jpeg", 0.65),
        asl_enabled: aslEnabled,
      }));
    }, 50);

    return () => clearInterval(interval);
  }, [cameraOn, aslEnabled]);

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
    translationWords,
    modelName,
    inferenceDevice,
    inferenceMode,
    status,
    timeNow,
    setMicOn,
    setAslEnabled,
    setShowCaptions,
    setActiveTab,
    toggleAsl,
    toggleCamera,
  };
}