import { FiMic, FiMicOff, FiVideo, FiVideoOff, FiPhoneOff } from "react-icons/fi";
import ControlButton from "./ControlButton";

function ControlsBar({
  micOn,
  cameraOn,
  aslEnabled,
  onToggleMic,
  onToggleCamera,
  onToggleAsl,
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
        tooltip={aslEnabled ? "Disable ASL (I love you)" : "Enable ASL"}
        className={aslEnabled ? "active" : ""}
      >
        🤟
      </ControlButton>

      <ControlButton onClick={onOpenPanel} tooltip="Chat" className={panelOpen ? "active" : ""}>
        💬
      </ControlButton>

      <ControlButton variant="danger" tooltip="End call" onClick={onEndCall} className="end-btn-action">
        <FiPhoneOff size={20} />
      </ControlButton>
    </footer>
  );
}

export default ControlsBar;
