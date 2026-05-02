function TextToSignInput({
  inputText,
  onInputChange,
  onSubmit,
  signLanguage,
  onLanguageChange,
  signQueue,
  currentWord,
  missingWords,
}) {
  function handleKeyDown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="text-to-sign-box">
      <div className="text-to-sign-header">
        <span>Text to Sign</span>

        <select
          className="text-to-sign-select"
          value={signLanguage}
          onChange={(event) => onLanguageChange(event.target.value)}
        >
          <option value="asl">ASL</option>
          <option value="russian">Russian Sign</option>
        </select>
      </div>

      <input
        className="text-to-sign-input"
        value={inputText}
        onChange={(event) => onInputChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type here..."
      />

      <div className="text-to-sign-status">
        {signQueue.length > 0 ? (
          <>
            <span>Queue: {signQueue.join(" → ")}</span>
            {currentWord && <strong>Now: {currentWord}</strong>}
          </>
        ) : (
          <span>Press Enter to play sign sequence</span>
        )}

        {missingWords?.length > 0 && (
          <span className="text-to-sign-missing">
            Skipped: {missingWords.join(", ")}
          </span>
        )}
      </div>
    </div>
  );
}

export default TextToSignInput;