import { useEffect, useState } from "react";

export function useMicLevel(enabled) {
  const [level, setLevel] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setLevel(0);
      return undefined;
    }

    let mounted = true;
    let animationFrameId = null;
    let audioContext = null;
    let analyser = null;
    let source = null;
    let stream = null;

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (!mounted) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        audioContext = new window.AudioContext();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
          if (!mounted || !analyser) return;

          analyser.getByteFrequencyData(dataArray);

          let sum = 0;
          for (let i = 0; i < dataArray.length; i += 1) {
            sum += dataArray[i];
          }

          const nextLevel = Math.min(1, sum / dataArray.length / 128);
          setLevel(nextLevel);
          animationFrameId = window.requestAnimationFrame(tick);
        };

        tick();
      } catch (error) {
        console.error("Mic level error:", error);
        setLevel(0);
      }
    };

    start();

    return () => {
      mounted = false;
      if (animationFrameId) window.cancelAnimationFrame(animationFrameId);
      if (source) source.disconnect();
      if (analyser) analyser.disconnect();
      if (audioContext) audioContext.close();
      if (stream) stream.getTracks().forEach((track) => track.stop());
      setLevel(0);
    };
  }, [enabled]);

  return level;
}