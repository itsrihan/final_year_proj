import { FiMic, FiMicOff, FiVideo, FiVideoOff, FiArrowUp, FiPhoneOff, FiSun, FiMoon } from "react-icons/fi";
import ControlButton from "./ControlButton";

function ControlsBar({
  micOn,
  cameraOn,
  aslEnabled,
  onToggleMic,
  onToggleCamera,
  onToggleAsl,
  onToggleHandRaise,
  onEndCall,
  onOpenPanel,
  panelOpen,
  isDarkTheme,
  onToggleTheme,
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
        tooltip={aslEnabled ? "Disable ASL recognition" : "Enable ASL recognition"}
        className={aslEnabled ? "active" : ""}
      >
        🤟
      </ControlButton>

      <ControlButton onClick={onToggleHandRaise} tooltip="Raise hand">
        <FiArrowUp size={20} />
      </ControlButton>

      <ControlButton onClick={onOpenPanel} tooltip="Details" className={panelOpen ? "active" : ""}>
        💬
      </ControlButton>

      <ControlButton onClick={onToggleTheme} tooltip={isDarkTheme ? "Light mode" : "Dark mode"}>
        {isDarkTheme ? <FiMoon size={20} /> : <FiSun size={20} />}
      </ControlButton>

      <ControlButton variant="danger" tooltip="End call" onClick={onEndCall} className="end-btn-action">
        <FiPhoneOff size={20} />
      </ControlButton>
    </footer>
  );
}

export default ControlsBar;
