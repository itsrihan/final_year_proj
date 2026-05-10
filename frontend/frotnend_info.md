# Frotnend Info

This file merges the important frontend architecture and CSS notes into one short guide for humans and AI.

## What the frontend does
- Renders the meeting-style ASL interface.
- Captures webcam frames and sends them to the backend ASL WebSocket.
- Displays live prediction captions, confidence, and telemetry.
- Supports text-to-sign and audio-to-sign flows.
- Keeps the UI theme, panels, controls, and avatar playback organized in separate components.

## Main runtime flow
1. `App.jsx` loads the app theme and pulls state from `useAslStream()`.
2. `Ui.jsx` acts as a thin wrapper and imports the global CSS bundle.
3. `MeetingLayout.jsx` orchestrates the page layout and local UI state.
4. `useAslStream.js` manages camera, socket connection, frame sending, and ASL results.
5. Child components render the video stage, side panel, caption tray, controls, and avatar tile.

## Key files
- `App.jsx` - root component and theme persistence.
- `useAslStream.js` - camera, websocket, and ASL stream state.
- `MeetingLayout.jsx` - main layout orchestrator.
- `MeetingVideoStage.jsx` - camera view and ASL overlay.
- `ControlsBar.jsx` - bottom action bar.
- `SidePanel.jsx` - captions, people, and chat tabs.
- `LiveCaptionTray.jsx` - live translation strip.
- `TextToSignInput.jsx` - manual text-to-sign input.
- `SignAvatarTile.jsx` - sign video/avatar playback and speed control.
- `useTextToSign.js` - text-to-sign conversion and playback queue.
- `useSpeechToText.js` - browser SpeechRecognition with fallback behavior.
- `useMicLevel.js` - mic level visualizer.
- `css/index.css` - central CSS import file.

## Current data flow
- `useAslStream.js` captures webcam frames and sends them to `/ws/asl`.
- Backend responses populate `prediction`, `confidence`, `handsCount`, `status`, and telemetry.
- `translationWords` keeps the accumulated recognized words for the live caption tray.
- `useTextToSign.js` converts entered or spoken text into sign video playback.
- `useSpeechToText.js` feeds final transcripts into `onFinalText(...)`, which still routes into `useTextToSign.js`.

## Current UI modes
- ASL camera recognition.
- Text-to-sign.
- Audio-to-sign.
- Side panel tabs for captions, people, and chat.

## Recent frontend updates
- Vite dev server is exposed on `0.0.0.0` for LAN testing.
- WebSocket URL still supports `VITE_WS_URL` override and safe fallback from the current host.
- Audio-to-sign still uses browser SpeechRecognition as the active path, with fallback handling kept in place.
- The audio-to-sign UI now keeps the heard transcript visible and restarts listening carefully without breaking the app.
- `SignAvatarTile` now includes a playback-speed dropdown and a dark themed avatar panel.
- Idle avatar state shows the avatar image instead of placeholder text.
 - `MeetingVideoStage` now renders a minimal ASL indicator ring around the camera window when ASL is enabled: red = translating, yellow = hand detected, green = waiting/done. The effect is implemented with a subtle pseudo-element and transitions for an elegant appearance.
 - No frontend changes are required to support a backend frame-window change (e.g. `FRAMES = 35`); the frontend remains agnostic to the model frame length.

## CSS organization
- CSS lives in `src/components/css/`.
- `css/index.css` imports all component CSS once.
- `global.css` defines theme variables, animations, and responsive breakpoints.
- Each major component has its own style file for maintainability.

## Theme system
- Theme is stored in localStorage under `app-theme`.
- `App.jsx` sets `document.documentElement[data-theme]`.
- Styles use CSS variables instead of hardcoded colors.
- Dark and light themes are both supported.

## Important environment settings
- `VITE_WS_URL` - optional frontend WebSocket override.
- `npm run dev` uses Vite; the host exposure is enabled in `vite.config.js`.

## Practical notes
- Keep business logic in hooks.
- Keep components presentational where possible.
- Keep ASL stream logic in `useAslStream.js`.
- Keep text-to-sign conversion logic in `useTextToSign.js`.
- Keep browser speech support in `useSpeechToText.js` as fallback-friendly logic.

## Short version
This frontend is a React/Vite meeting-style ASL interface. Hooks handle the live stream and speech logic, components handle layout and presentation, and CSS is split by component for clarity and easy maintenance.
