import { useState, useEffect } from "react";
import Ui from "./components/ui";
import { useAslStream } from "./hooks/useAslStream";

function App() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("app-theme");
    return saved || "dark";
  });

  useEffect(() => {
    localStorage.setItem("app-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const {
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
    toggleAsl,
    setShowCaptions,
    setActiveTab,
    toggleCamera,
  } = useAslStream();

  return (
    <Ui
      videoRef={videoRef}
      canvasRef={canvasRef}
      connected={connected}
      cameraOn={cameraOn}
      micOn={micOn}
      aslEnabled={aslEnabled}
      showCaptions={showCaptions}
      activeTab={activeTab}
      prediction={prediction}
      confidence={confidence}
      handsCount={handsCount}
      translationWords={translationWords}
      modelName={modelName}
      inferenceDevice={inferenceDevice}
      inferenceMode={inferenceMode}
      status={status}
      timeNow={timeNow}
      onToggleMic={() => setMicOn((prev) => !prev)}
      onToggleCamera={toggleCamera}
      onToggleCaptions={() => setShowCaptions((prev) => !prev)}
      onToggleAsl={toggleAsl}
      onSetActiveTab={setActiveTab}
      theme={theme}
      onThemeToggle={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
    />
  );
}

export default App;