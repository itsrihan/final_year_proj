function ParticipantTile({ initial, name, role }) {
  return (
    <div className="mini-card">
      <div className="mini-video">
        <div className="avatar">{initial}</div>
      </div>
      <div className="mini-name">{name}</div>
      <div className="mini-role">{role}</div>
    </div>
  );
}

export default ParticipantTile;
