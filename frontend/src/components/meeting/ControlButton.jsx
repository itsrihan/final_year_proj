function ControlButton({ children, onClick, variant = "default", tooltip }) {
  const className = variant === "danger" ? "end-btn" : "control-btn";

  return (
    <button className={className} onClick={onClick} title={tooltip}>
      <span className="btn-icon">{children}</span>
      {tooltip && <span className="btn-tooltip">{tooltip}</span>}
    </button>
  );
}

export default ControlButton;
