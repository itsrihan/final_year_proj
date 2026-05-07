import { SUPPORTED_SIGN_LANGUAGES } from "../../data/signLexicons";

function SignLanguageSelect({ value, onChange, className = "" }) {
  return (
    <select
      className={`text-to-sign-select ${className}`.trim()}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {Object.entries(SUPPORTED_SIGN_LANGUAGES).map(([languageKey, language]) => (
        <option key={languageKey} value={languageKey}>
          {language.label}
        </option>
      ))}
    </select>
  );
}

export default SignLanguageSelect;