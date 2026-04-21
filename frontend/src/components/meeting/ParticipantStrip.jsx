import ParticipantTile from "./ParticipantTile";

const participants = [
  { initial: "A", name: "Alex", role: "Participant" },
  { initial: "S", name: "Sara", role: "Participant" },
];

function ParticipantStrip() {
  return (
    <div className="participants-row">
      {participants.map((participant) => (
        <ParticipantTile
          key={participant.name}
          initial={participant.initial}
          name={participant.name}
          role={participant.role}
        />
      ))}
    </div>
  );
}

export default ParticipantStrip;
