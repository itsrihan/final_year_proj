import ControlButton from "./ControlButton";

function ControlsBar({
  micOn,
  cameraOn,
  showCaptions,
  aslEnabled,
  onToggleMic,
  onToggleCamera,
  onToggleCaptions,
  onToggleAsl,
  onOpenPanel,
  panelOpen,
}) {
  return (
    <footer className="bottom-bar">
      <ControlButton onClick={onToggleMic} tooltip={micOn ? "Mute" : "Unmute"}>
        {micOn ? "🎤" : "🔇"}
      </ControlButton>

      <ControlButton onClick={onToggleCamera} tooltip={cameraOn ? "Turn off camera" : "Turn on camera"}>
        {cameraOn ? "📷" : "📹"}
      </ControlButton>

      <ControlButton onClick={onToggleCaptions} tooltip={showCaptions ? "Hide captions" : "Show captions"}>
        {showCaptions ? "📝" : "📄"}
      </ControlButton>

      <ControlButton onClick={onToggleAsl} tooltip={aslEnabled ? "Disable ASL" : "Enable ASL"}>
        {aslEnabled ? "🌐" : "🔤"}
      </ControlButton>

      <ControlButton onClick={onOpenPanel} tooltip="Details" className={panelOpen ? "active" : ""}>
        💬
      </ControlButton>

      <ControlButton variant="danger" tooltip="End call">
        📞
      </ControlButton>
    </footer>
  );
}

export default ControlsBar;
