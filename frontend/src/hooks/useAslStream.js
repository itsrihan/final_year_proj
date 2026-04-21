import { useEffect, useRef, useState } from "react";

import {
  attachVideoElement,
  detachVideoElement,
  stopMediaStream,
} from "./mediaStreamUtils";

const WS_URL = "ws://localhost:8000/ws/asl";

const CAMERA_CONSTRAINTS = {
  video: {
    facingMode: "user",
    width: { ideal: 1280 },
    height: { ideal: 720 },
    aspectRatio: { ideal: 1.7777778 }, // 16:9
  },
  audio: false,
};

export function useAslStream() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const socketRef = useRef(null);
  const streamRef = useRef(null);

  const [mediaStream, setMediaStream] = useState(null);
  const [connected, setConnected] = useState(false);
  const [cameraOn, setCameraOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [aslEnabled, setAslEnabled] = useState(true);
  const [showCaptions, setShowCaptions] = useState(true);
  const [activeTab, setActiveTab] = useState("captions");
  const [prediction, setPrediction] = useState("Waiting...");
  const [confidence, setConfidence] = useState(0);
  const [status, setStatus] = useState("Starting...");
  const [timeNow, setTimeNow] = useState("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeNow(
        now.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
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

        if (!mounted) {
          stopMediaStream(stream);
          return;
        }

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
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        setConnected(true);
        setStatus("Backend connected");
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setPrediction(data.text || "Waiting...");
        setConfidence(data.confidence || 0);
        setStatus(data.status || "Idle");
      };

      socket.onerror = () => {
        setConnected(false);
        setStatus("WebSocket error");
      };

      socket.onclose = () => {
        setConnected(false);
        setStatus("Backend disconnected");
      };
    };

    startCamera();
    connectWebSocket();

    return () => {
      mounted = false;
      stopMediaStream(streamRef.current);
      streamRef.current = null;
      detachVideoElement(videoRef.current);
      setMediaStream(null);

      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (!cameraOn) return;
      if (!videoRef.current) return;
      if (!canvasRef.current) return;
      if (!socketRef.current) return;
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

      const frame = canvas.toDataURL("image/jpeg", 0.7);

      socketRef.current.send(
        JSON.stringify({
          frame,
          asl_enabled: aslEnabled,
        })
      );
    }, 150);

    return () => clearInterval(interval);
  }, [cameraOn, aslEnabled]);

  const stopCamera = () => {
    stopMediaStream(streamRef.current);
    streamRef.current = null;
    detachVideoElement(videoRef.current);
    setMediaStream(null);
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
      return;
    }

    await startCamera();
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
    status,
    timeNow,
    setMicOn,
    setAslEnabled,
    setShowCaptions,
    setActiveTab,
    toggleCamera,
  };
}