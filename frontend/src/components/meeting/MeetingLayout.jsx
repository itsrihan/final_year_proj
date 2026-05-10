import { useEffect, useState } from "react";
import { FiMoon, FiSun } from "react-icons/fi";
import ControlsBar from "./ControlsBar";
import MeetingVideoStage from "./MeetingVideoStage";
import SidePanel from "./SidePanel";
import FloatingParticipant from "./FloatingParticipant";
import LiveCaptionTray from "./LiveCaptionTray";
import SignAvatarTile from "./SignAvatarTile";
import TextToSignInput from "./TextToSignInput";
import SignLanguageSelect from "./SignLanguageSelect";
import { useTextToSign } from "../../hooks/useTextToSign";
import { useSpeechToText } from "../../hooks/useSpeechToText";
import { useMicLevel } from "../../hooks/useMicLevel";

function MeetingLayout({
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
  onToggleMic,
  onToggleCamera,
  onToggleCaptions,
  onToggleAsl,
  onSetActiveTab,
  theme,
  onThemeToggle,
  aslCaptureState,
  manualMode,
  manualCaptureState,
  countdownMs,
  onToggleManualMode,
  onStartManualCapture,
  onCancelManualCapture,
}) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [textToSignMode, setTextToSignMode] = useState(false);
  const [audioToSignMode, setAudioToSignMode] = useState(false);

  const textToSign = useTextToSign();
  const speech = useSpeechToText({
    autoRestart: audioToSignMode && micOn,
    onFinalText: (text) => {
      textToSign.submitText(text);
    },
  });
  const micLevel = useMicLevel(micOn);

  const captionOpen = aslEnabled && showCaptions && !textToSignMode && !audioToSignMode;

  function handleToggleTextToSign() {
    setAudioToSignMode(false);
    setTextToSignMode((prev) => !prev);
  }

  function handleToggleAudioToSign() {
    setTextToSignMode(false);
    setAudioToSignMode((prev) => !prev);
  }

  useEffect(() => {
    if (audioToSignMode && micOn) {
      speech.startListening();
      return undefined;
    }

    speech.stopListening();
    return undefined;
  }, [audioToSignMode, micOn]);

  return (
    <div className="app" data-theme={theme}>
      <main className={`main-layout ${panelOpen ? "panel-open" : ""}`}>
        <section className={`video-caption-layout ${captionOpen ? "caption-open" : ""}`}>
          <div className={`meeting-video-grid ${(textToSignMode || audioToSignMode) ? "text-sign-layout" : ""}`}>
            <MeetingVideoStage
              videoRef={videoRef}
              cameraOn={cameraOn}
              micOn={micOn}
              aslEnabled={aslEnabled}
              showCaptions={showCaptions}
              prediction={prediction}
              confidence={confidence}
              handsCount={handsCount}
              aslCaptureState={aslCaptureState}
              manualCaptureState={manualCaptureState}
              countdownMs={countdownMs}
              micLevel={micLevel}
            />

            <SignAvatarTile
              visible={textToSignMode || audioToSignMode}
              videoSrc={textToSign.currentVideoSrc}
              currentWord={textToSign.currentWord}
              onEnded={textToSign.handleVideoEnded}
              emptyMessage={audioToSignMode ? "Speak to generate signs" : "Type a sentence to generate signs"}
            />
          </div>

          {textToSignMode ? (
            <TextToSignInput
              inputText={textToSign.inputText}
              onInputChange={textToSign.setInputText}
              onSubmit={textToSign.handleSubmit}
              signLanguage={textToSign.signLanguage}
              onLanguageChange={textToSign.setSignLanguage}
              signQueue={textToSign.signQueue}
              currentWord={textToSign.currentWord}
              missingWords={textToSign.missingWords}
            />
          ) : audioToSignMode ? (
            <div className="text-to-sign-box audio-to-sign-box">
              <div className="text-to-sign-header">
                <span>Audio to SL</span>
                <SignLanguageSelect
                  value={textToSign.signLanguage}
                  onChange={textToSign.setSignLanguage}
                />
                <span className={`audio-to-sign-state ${speech.listening ? "active" : ""}`}>
                  {speech.listening ? "Listening" : micOn ? "Ready" : "Mic off"}
                </span>
              </div>

              <div className="text-to-sign-status">
                <span>Speak naturally, then pause to submit.</span>
                {speech.heardText ? (
                  <span>
                    Heard: {speech.heardText}
                  </span>
                ) : speech.transcript ? (
                  <span>
                    Heard: {speech.transcript}
                  </span>
                ) : null}
                {speech.speechError && (
                  <span className="text-to-sign-missing">{speech.speechError}</span>
                )}
                {!micOn && (
                  <span className="text-to-sign-missing">Turn on mic to use audio-to-sign.</span>
                )}
              </div>
            </div>
          ) : (
            <LiveCaptionTray
              visible={captionOpen}
              translationWords={translationWords}
            />
          )}
        </section>

        {panelOpen && (
          <SidePanel
            activeTab={activeTab}
            aslEnabled={aslEnabled}
            showCaptions={showCaptions}
            prediction={prediction}
            confidence={confidence}
            handsCount={handsCount}
            modelName={modelName}
            inferenceDevice={inferenceDevice}
            inferenceMode={inferenceMode}
            status={status}
            manualMode={manualMode}
            manualCaptureState={manualCaptureState}
            countdownMs={countdownMs}
            cameraOn={cameraOn}
            onToggleManualMode={onToggleManualMode}
            onStartManualCapture={onStartManualCapture}
            onCancelManualCapture={onCancelManualCapture}
            onSetActiveTab={onSetActiveTab}
            onClose={() => setPanelOpen(false)}
          />
        )}
      </main>

      <div className="floating-meeting-info">
        <button
          className="theme-toggle-float"
          onClick={onThemeToggle}
          title="Toggle theme"
        >
          {theme === "dark" ? <FiMoon size={18} /> : <FiSun size={18} />}
        </button>
        <div className="meeting-code">
          <span className="code-label">Code:</span>
          <span className="code-value">abc-defg-hij</span>
        </div>
      </div>

      <div className="floating-person you">
        <div className="person-avatar-float">Y</div>
        <div className="person-info-float">
          <div className="person-name-float">You</div>
          <div className={`status-dot ${connected ? "online" : "offline"}`} />
        </div>
      </div>

      <ControlsBar
        micOn={micOn}
        cameraOn={cameraOn}
        aslEnabled={aslEnabled}
        textToSignMode={textToSignMode}
        audioToSignMode={audioToSignMode}
        onToggleMic={onToggleMic}
        onToggleCamera={onToggleCamera}
        onToggleAsl={onToggleAsl}
        onToggleTextToSign={handleToggleTextToSign}
        onToggleAudioToSign={handleToggleAudioToSign}
        onEndCall={() => {}}
        onOpenPanel={() => setPanelOpen(!panelOpen)}
        panelOpen={panelOpen}
      />

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}

export default MeetingLayout;