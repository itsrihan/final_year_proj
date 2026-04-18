import Ui from "./components/ui";
import { useAslStream } from "./hooks/useAslStream";

function App() {
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
    status,
    timeNow,
    setMicOn,
    setAslEnabled,
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
      status={status}
      timeNow={timeNow}
      onToggleMic={() => setMicOn((prev) => !prev)}
      onToggleCamera={toggleCamera}
      onToggleCaptions={() => setShowCaptions((prev) => !prev)}
      onToggleAsl={() => setAslEnabled((prev) => !prev)}
      onSetActiveTab={setActiveTab}
    />
  );
}

export default App;