import SignLanguageSelect from "./SignLanguageSelect";

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
        <span>Text to SL</span>

        <SignLanguageSelect value={signLanguage} onChange={onLanguageChange} />
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