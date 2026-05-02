import {
  FiMic,
  FiMicOff,
  FiVideo,
  FiVideoOff,
  FiPhoneOff,
  FiGlobe,
  FiMessageCircle,
} from "react-icons/fi";
import ControlButton from "./ControlButton";

function ControlsBar({
  micOn,
  cameraOn,
  aslEnabled,
  textToSignMode,
  onToggleMic,
  onToggleCamera,
  onToggleAsl,
  onToggleTextToSign,
  onEndCall,
  onOpenPanel,
  panelOpen,
}) {
  return (
    <footer className="bottom-bar">
      <ControlButton
        onClick={onToggleMic}
        tooltip={micOn ? "Mute microphone" : "Unmute microphone"}
        className={micOn ? "" : "danger-state"}
      >
        {micOn ? <FiMic size={20} /> : <FiMicOff size={20} />}
      </ControlButton>

      <ControlButton
        onClick={onToggleCamera}
        tooltip={cameraOn ? "Turn off camera" : "Turn on camera"}
        className={cameraOn ? "" : "danger-state"}
      >
        {cameraOn ? <FiVideo size={20} /> : <FiVideoOff size={20} />}
      </ControlButton>

      <ControlButton
        onClick={onToggleAsl}
        tooltip={aslEnabled ? "Disable ASL" : "Enable ASL"}
        className={aslEnabled ? "active" : ""}
      >
        <FiGlobe size={20} />
      </ControlButton>

      <ControlButton
        tooltip={textToSignMode ? "Back to Sign to Text" : "Text to Sign"}
        className={textToSignMode ? "active" : ""}
        onClick={onToggleTextToSign}
      >
        <span className="btn-icon">✍️</span>
      </ControlButton>

      <ControlButton onClick={onOpenPanel} tooltip="Chat" className={panelOpen ? "active" : ""}>
        <FiMessageCircle size={20} />
      </ControlButton>

      <ControlButton variant="danger" tooltip="End call" onClick={onEndCall} className="end-btn-action">
        <FiPhoneOff size={20} />
      </ControlButton>
    </footer>
  );
}

export default ControlsBar;