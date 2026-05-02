# Frontend Architecture & Implementation Guide

## Overview

This document provides a comprehensive guide to the frontend codebase. It explains the project structure, component hierarchy, data flow, styling approach, state management, and integration points with the backend ASL (American Sign Language) prediction service.

The frontend is a React-based real-time ASL translation interface built with Vite, designed to capture webcam frames, send them to a Python backend for ASL recognition, and display live translation captions with confidence metrics and debugging telemetry.

---

## Project Structure

```
frontend/
├── src/
│   ├── App.jsx                      (Root application component)
│   ├── main.jsx                     (React entry point)
│   ├── index.css                    (Global styles)
│   │
│   ├── components/
│   │   ├── ui.jsx                   (UI wrapper component)
│   │   ├── CSS_STRUCTURE.md         (CSS documentation)
│   │   ├── FRONTEND_INFO.md         (This file)
│   │   │
│   │   ├── css/                     (Component-specific stylesheets)
│   │   │   ├── index.css            (Master CSS import file)
│   │   │   ├── global.css           (Theme variables, animations, responsive rules)
│   │   │   ├── MeetingLayout.css
│   │   │   ├── MeetingVideoStage.css
│   │   │   ├── CaptionsPanel.css
│   │   │   ├── SidePanel.css
│   │   │   ├── PeoplePanel.css
│   │   │   ├── ChatPanel.css
│   │   │   ├── ControlButton.css
│   │   │   ├── ControlsBar.css
│   │   │   ├── FloatingElements.css
│   │   │   ├── LiveCaptionTray.css
│   │   │   └── PanelTabs.css
│   │   │
│   │   └── meeting/                 (Core UI components)
│   │       ├── MeetingLayout.jsx    (Main container / layout orchestrator)
│   │       ├── MeetingVideoStage.jsx (Webcam video display + ASL overlay)
│   │       ├── MeetingTopBar.jsx    (Top navigation / header)
│   │       ├── CaptionsPanel.jsx    (ASL recognition details in side panel)
│   │       ├── ChatPanel.jsx        (Chat messages interface)
│   │       ├── PeoplePanel.jsx      (Participant list)
│   │       ├── SidePanel.jsx        (Tabbed panel container)
│   │       ├── PanelTabs.jsx        (Tab navigation)
│   │       ├── ControlsBar.jsx      (Bottom control bar with buttons)
│   │       ├── ControlButton.jsx    (Reusable button component)
│   │       ├── FloatingParticipant.jsx (Floating participant indicator)
│   │       ├── LiveCaptionTray.jsx  (Live translation text display)
│   │       └── ParticipantTile.jsx  (Individual participant card)
│   │
│   ├── hooks/                       (Custom React hooks)
│   │   ├── useAslStream.js          (Main stream management hook - WebSocket, camera, state)
│   │   └── mediaStreamUtils.js      (Media stream utility functions)
│   │
│   └── assets/                      (Static assets)
│
├── index.html                       (HTML entry point)
├── vite.config.js                   (Vite bundler configuration)
├── package.json                     (Dependencies and scripts)
├── eslint.config.js                 (Linter configuration)
└── README.md                        (Project README)
```

---

## Component Hierarchy & Data Flow

### High-Level Structure

```
App (root component, theme & state setup)
  └─ Ui (wrapper)
      └─ MeetingLayout (main orchestrator)
          ├─ MeetingVideoStage (camera feed + ASL overlay)
          ├─ LiveCaptionTray (live translation text)
          ├─ SidePanel (tabbed info panel)
          │   ├─ PanelTabs (tab navigation)
          │   ├─ CaptionsPanel (ASL details)
          │   ├─ PeoplePanel (participants list)
          │   └─ ChatPanel (chat messages)
          ├─ FloatingParticipant (participant indicator)
          ├─ ControlsBar (bottom control buttons)
          │   ├─ ControlButton (mic, camera, ASL, chat, end-call)
          └─ Floating Meeting Info (theme toggle, meeting code)
```

### Data Flow Pattern

1. **useAslStream hook** (custom hook):
   - Manages WebSocket connection to Python backend
   - Handles camera stream acquisition
   - Maintains state for all prediction results
   - Emits frame snapshots to backend
   - Receives recognition results

2. **App.jsx** (root):
   - Initializes theme from localStorage
   - Wraps data from useAslStream
   - Passes all props down to Ui

3. **Ui.jsx** (wrapper):
   - Imports CSS
   - Passes props to MeetingLayout

4. **MeetingLayout** (orchestrator):
   - Receives all state props from App
   - Controls panel visibility
   - Routes props to child components
   - Manages local UI state (panelOpen, theme toggle)

5. **Child Components** (presentation):
   - Receive data as props
   - Trigger callbacks to parent (onToggleMic, onSetActiveTab, etc.)
   - Render UI based on state

---

## Core Files & Responsibilities

### Entry Points

#### `main.jsx`
- Mounts React app to DOM element with ID `root`
- No logic; purely bootstrap code

#### `App.jsx`
**Responsibilities:**
- Initializes theme from localStorage (persistence)
- Sets HTML `data-theme` attribute for CSS theming
- Imports `useAslStream` hook for all app data
- Passes all state, callbacks, and refs to `Ui` component

**Key State:**
- `theme`: current theme ("dark" or "light")

**Key Props Passed:**
- `videoRef`, `canvasRef`: DOM refs for video/canvas elements
- `connected`, `cameraOn`, `micOn`: connection/device states
- `prediction`, `confidence`, `handsCount`: ASL recognition data
- `translationWords`: accumulated recognized signs
- `status`, `timeNow`, `inferenceDevice`, `inferenceMode`: telemetry

#### `src/components/ui.jsx`
- Minimal wrapper component
- Imports CSS from `css/index.css`
- Renders `MeetingLayout` and spreads all props

---

### Hooks (State & Logic)

#### `hooks/useAslStream.js`
**This is the most critical hook—it encapsulates all backend integration and real-time stream handling.**

**Responsibilities:**
1. **Camera Management:**
   - Requests camera permission via `getUserMedia`
   - Uses constraints: 1280×720 resolution, 16:9 aspect ratio
   - Handles attachment/detachment of media stream to video element

2. **WebSocket Connection:**
   - Establishes persistent connection to backend `/ws/asl` endpoint
   - Uses environment variable `VITE_WS_URL` if set; otherwise derives from window location
   - Handles auto-reconnection with exponential backoff

3. **Frame Capture & Transmission:**
   - Converts video stream to canvas
   - Extracts frame as base64-encoded data URL
   - Sends frame JSON payload to backend with `asl_enabled` flag
   - Transmits approximately every 33ms (30fps)

4. **Backend Response Handling:**
   - Listens for prediction results
   - Extracts and stores: `text` (prediction), `confidence`, `hands_detected`, `hands_count`, `model_name`, `inference_device`, `inference_mode`, `status`
   - Accumulates recognized words in `translationWords` array (resets on hand loss)
   - Updates telemetry for debug display

5. **State Management:**
   - `connected`: WebSocket connection status
   - `cameraOn`, `micOn`: device toggle states (persistent to localStorage)
   - `aslEnabled`: whether ASL translation is active
   - `showCaptions`: whether to display recognition overlay
   - `activeTab`: which side panel tab is active ("captions", "people", "chat")
   - `prediction`: latest recognized sign from model
   - `confidence`: confidence score of recognition
   - `handsCount`: number of hands detected in current frame
   - `translationWords`: array of accumulated recognized signs
   - Model/inference metadata: `modelName`, `inferenceDevice`, `inferenceMode`

6. **Cleanup & Lifecycle:**
   - Stops camera stream on unmount
   - Closes WebSocket on unmount
   - Clears reconnect timers
   - Handles mounted/unmounted race conditions

**Key Environment Variables:**
- `VITE_WS_URL`: (optional) Override WebSocket URL for non-standard deployments

**Key Methods:**
- `toggleCamera()`: Attach/detach video stream; state toggles independently
- `toggleAsl()`: Enable/disable ASL translation sending to backend
- `setShowCaptions()`: Show/hide ASL overlay on video
- `setMicOn()`: Toggle microphone (currently UI-only; audio not yet captured)
- `setActiveTab()`: Switch side panel tab
- Returns: object with all state vars, refs, and toggle methods

#### `hooks/mediaStreamUtils.js`
**Utility functions for media stream lifecycle management:**

- `stopMediaStream(stream)`: Stops all tracks in a MediaStream
- `attachVideoElement(videoElement, stream)`: Assigns srcObject to video element
- `detachVideoElement(videoElement)`: Clears srcObject and pauses video

**Why separated:** Prevents tight coupling between hook and DOM manipulation; makes it testable and reusable.

---

### Components (Meeting/)

#### `MeetingLayout.jsx`
**The main orchestrator—receives all app state and routes to child components.**

**Responsibilities:**
- Renders main app container with theme
- Manages local state: `panelOpen` (side panel visibility)
- Conditionally renders side panel
- Passes props to children:
  - `MeetingVideoStage` – video feed
  - `LiveCaptionTray` – live translation text
  - `SidePanel` – tabbed info/chat panel
  - `FloatingParticipant` – other participant indicator
  - `ControlsBar` – control buttons

**Key Features:**
- Uses `captionOpen` flag to conditionally apply CSS class for layout adjustments
- Renders floating meeting code box and user indicator
- Theme toggle button in floating area

**Props Received:** 23 props total covering state, refs, and callbacks

---

#### `MeetingVideoStage.jsx`
**Displays the main video feed and ASL recognition overlay.**

**Responsibilities:**
- Renders video element with controls: `autoplay`, `muted`, `playsInline`
- Shows "Camera is off" placeholder when `cameraOn === false`
- Conditionally renders ASL overlay with:
  - Recognized sign text
  - Confidence percentage
  - Title "ASL Recognition"
- Applies styling classes based on state

**Conditional Rendering:**
```jsx
if (aslEnabled && showCaptions && cameraOn) {
  // Show ASL overlay
}
```

**Props:**
- `videoRef`: DOM ref to attach video stream
- `cameraOn`: whether to show video or "off" state
- `aslEnabled`, `showCaptions`: control overlay visibility
- `prediction`, `confidence`: text and percentage to display

---

#### `SidePanel.jsx`
**Tabbed container for captions, people, and chat.**

**Responsibilities:**
- Renders aside with tab navigation (`PanelTabs`)
- Routes active tab to appropriate child component
- Displays close button to collapse panel
- Passes telemetry and prediction data to `CaptionsPanel`

**Tabs:**
1. **Captions** → `CaptionsPanel` (ASL recognition details)
2. **People** → `PeoplePanel` (participant list)
3. **Chat** → `ChatPanel` (chat messages)

**Props:**
- `activeTab`: currently selected tab
- All prediction/telemetry data (passed to CaptionsPanel)
- `onSetActiveTab`, `onClose`: callbacks

---

#### `PanelTabs.jsx`
**Tab navigation bar.**

**Responsibilities:**
- Renders three clickable tabs: "captions", "people", "chat"
- Highlights active tab
- Calls `onSetActiveTab(tabName)` on click

---

#### `CaptionsPanel.jsx`
**Displays ASL recognition metrics and backend telemetry.**

**Responsibilities:**
- Shows "Translator ON/OFF" badge based on `aslEnabled`
- Displays latest recognized sign
- Shows recognition status
- Displays confidence score
- Shows hands detected count
- Displays model name and inference details (device, mode)

**Purpose:** Debug/observability panel for users to monitor backend performance

---

#### `PeoplePanel.jsx`
**Participant list display.**

**Responsibilities:**
- Renders list of meeting participants
- (Implementation details vary; shows participant status, avatars, etc.)

---

#### `ChatPanel.jsx`
**Chat message display.**

**Responsibilities:**
- Renders chat messages
- Shows user names and message content
- (Message sending likely handled elsewhere or stub)

---

#### `ControlsBar.jsx`
**Bottom toolbar with control buttons.**

**Responsibilities:**
- Renders 5 control buttons:
  1. **Mic** – toggle microphone audio
  2. **Camera** – toggle video feed
  3. **ASL** – toggle ASL translation
  4. **Chat/Panel** – open/close side panel
  5. **End Call** – (currently stub)

**Each button uses `ControlButton` component.**

**Props:**
- `micOn`, `cameraOn`, `aslEnabled`, `panelOpen`: state flags
- `onToggleMic`, `onToggleCamera`, `onToggleAsl`, `onOpenPanel`, `onEndCall`: callbacks

---

#### `ControlButton.jsx`
**Reusable button component with icon and tooltip.**

**Responsibilities:**
- Renders a button with icon (via children)
- Shows tooltip on hover
- Supports two variants: `"default"` and `"danger"`
- Applies danger styling for "end-call" button

**Props:**
- `variant`: "default" or "danger"
- `tooltip`: hover text
- `className`: additional CSS classes (e.g., "active", "danger-state")
- `onClick`: callback
- `children`: icon element (React Icon)

---

#### `LiveCaptionTray.jsx`
**Horizontal strip displaying accumulated live translation.**

**Responsibilities:**
- Shows "Live ASL Translation" label
- Displays recognized words joined as a sentence
- Shows "Start signing..." placeholder when empty
- Conditionally renders based on `visible` flag

**Props:**
- `visible`: show/hide the tray
- `translationWords`: array of recognized signs

---

#### `FloatingParticipant.jsx`
**Floating indicator for other meeting participants.**

**Responsibilities:**
- Renders a small floating card showing participant name and status
- Positioned on-screen separate from main video area
- Conditionally hidden when side panel is open

**Props:**
- `visible`: show/hide indicator
- `name`: participant name
- `initial`: first letter for avatar

---

#### `ParticipantTile.jsx`
**Individual participant display card.**

**Responsibilities:**
- Renders participant avatar, name, status indicator
- Used in PeoplePanel for each participant

---

## CSS Architecture

### Organization

CSS is organized in a dedicated `css/` directory with a master import file `css/index.css` that is imported once in `ui.jsx`.

**Benefits:**
- Component-specific styles are co-located with their JSX files (conceptually)
- Easy to locate styles for a given component
- Single import point minimizes redundant CSS imports
- Scalability: new components get their own `.css` file

### Structure

#### `css/global.css`
**Theme variables, animations, and responsive breakpoints.**

**Contents:**
- CSS custom properties (variables) for colors, spacing, shadows
- Dark theme variables (dark backgrounds, light text)
- Light theme variables (light backgrounds, dark text)
- Keyframe animations: `slideInRight`, `slideInDown`, `slideUp`, `fadeIn`
- Base HTML/body styles
- Scrollbar styling
- Responsive media queries:
  - `@media (max-width: 1024px)` – large screens
  - `@media (max-width: 768px)` – tablets (side panel becomes full-width)
  - `@media (max-width: 480px)` – mobile (hidden floating elements)

**Theme Application:**
- Selector: `html[data-theme="dark"]` and `html[data-theme="light"]`
- Applied by App.jsx setting `document.documentElement.setAttribute("data-theme", theme)`

#### Component-Specific CSS Files

Each component gets its own `.css` file:

- **`MeetingLayout.css`** – Main container layout, app wrapper
- **`MeetingVideoStage.css`** – Video display, overlay, camera-off state
- **`SidePanel.css`** – Panel container, header, tab navigation
- **`PanelTabs.css`** – Tab button styling (inherits from SidePanel)
- **`CaptionsPanel.css`** – Recognition data display, info boxes
- **`PeoplePanel.css`** – Participant list, avatars, status indicators
- **`ChatPanel.css`** – Chat message styling
- **`ControlsBar.css`** – Bottom control bar layout and button grouping
- **`ControlButton.css`** – Individual button styling, hover/active states
- **`FloatingElements.css`** – Meeting code box, theme toggle, participant indicator, floating styles
- **`LiveCaptionTray.css`** – Caption tray appearance and animations

#### Import Order (css/index.css)

```css
@import "global.css";           /* Base styles */
@import "MeetingLayout.css";    /* Layout */
@import "MeetingVideoStage.css";/* Content */
@import "SidePanel.css";
@import "CaptionsPanel.css";
@import "PeoplePanel.css";
@import "ChatPanel.css";
@import "ControlButton.css";    /* Buttons */
@import "ControlsBar.css";
@import "FloatingElements.css"; /* Overlays */
@import "LiveCaptionTray.css";
@import "PanelTabs.css";        /* Reference file */
```

### Theming

All colors are defined as CSS variables in `global.css` and can be toggled via `html[data-theme]` attribute.

**User Interaction:**
- Theme toggle button in floating area calls `onThemeToggle()`
- Sets React state in App.jsx
- Updates localStorage for persistence
- Updates DOM attribute for CSS scoping

---

## State Management Summary

### App-Level State (App.jsx)
- `theme`: "dark" | "light" (persisted to localStorage)

### Hook State (useAslStream.js)
The hook maintains 20+ state variables:

**Connection & Device:**
- `connected`: boolean (WebSocket connection status)
- `cameraOn`: boolean (camera video toggled)
- `micOn`: boolean (microphone toggled; UI-only currently)

**ASL Features:**
- `aslEnabled`: boolean (translation active)
- `showCaptions`: boolean (overlay visible)
- `prediction`: string (latest recognized sign)
- `confidence`: float (0.0–1.0)
- `handsCount`: integer (hands detected in frame)
- `translationWords`: array of strings (accumulated signs)

**UI Navigation:**
- `activeTab`: "captions" | "people" | "chat"

**Backend Telemetry:**
- `modelName`: string (e.g., "phrase_lstm.keras")
- `inferenceDevice`: string (e.g., "GPU:0", "CPU:0")
- `inferenceMode`: string (e.g., "tf-function", "cpu-fallback")
- `status`: string (backend status message)
- `timeNow`: string (current time, updated every 1s)

### Local Component State
- `MeetingLayout`: `panelOpen` (side panel visibility toggle)

---

## Integration with Backend

### WebSocket Protocol

**Endpoint:** `ws://localhost:8000/ws/asl` (or `wss://` for HTTPS)

**Client → Server (every ~33ms):**
```json
{
  "frame": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "asl_enabled": true
}
```

**Server → Client:**
```json
{
  "text": "hello",
  "confidence": 0.92,
  "status": "ASL on | hand detected",
  "model_name": "phrase_lstm.keras",
  "hands_detected": true,
  "hands_count": 2,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "GPU:0",
  "inference_mode": "tf-function"
}
```

### Frame Transmission Logic

1. Canvas copy of video element is created
2. Frame is drawn onto canvas
3. Canvas is converted to base64 data URL
4. Sent to backend via WebSocket as JSON payload
5. Backend extracts frame, runs MediaPipe + model
6. Backend returns prediction and telemetry
7. React state updated; components re-render

### Handling Backend Unavailability

If backend is unreachable:
- `connected` state remains `false`
- Status displays "Starting..." or connection error
- Captions panel shows "Predictor unavailable"
- No frames are sent; graceful degradation

---

## Styling Patterns

### CSS Classes & Naming

**BEM-inspired naming:**
- `.control-btn` – block
- `.control-btn.active` – modifier
- `.btn-icon` – element of control-btn
- `.btn-tooltip` – element of control-btn

**State Classes:**
- `.active` – active state
- `.danger-state` – danger/off state
- `.visible` – visibility toggle
- `.panel-open` – layout modifier

### Responsive Design

**Breakpoints (global.css):**

1. **Mobile (≤480px):**
   - Floating elements hidden
   - Video full-width
   - Adjusted padding/margins

2. **Tablet (481–768px):**
   - Side panel becomes full-width when open
   - Video scaling adjustments
   - Control bar reflow

3. **Desktop (>768px):**
   - Side panel fixed width
   - Video + panel side-by-side
   - Full floating elements

---

## Development Workflow

### Setup

```bash
npm install              # Install dependencies
npm run dev             # Start dev server (Vite)
```

Vite dev server runs on `http://localhost:5173` with hot module reloading.

### Build & Deploy

```bash
npm run build           # Production build (outputs to dist/)
npm run preview         # Preview production build locally
```

### Linting

```bash
npm run lint            # Run ESLint
```

### Environment Configuration

**Environment variables (`.env` file):**
```
VITE_WS_URL=ws://custom-backend:8000/ws/asl
```

If not set, WebSocket URL is derived from current window location.

### Adding New Components

1. Create `.jsx` file in `components/meeting/`
2. Create corresponding `.css` file in `components/css/`
3. Import CSS in `css/index.css`
4. Import component where needed
5. Wire up props and callbacks from parent

---

## Key Design Decisions

### Why useAslStream Hook?

- **Encapsulation:** All WebSocket, camera, and state logic in one place
- **Reusability:** Can be used in multiple components or future projects
- **Testability:** Logic can be unit tested independently
- **Separation:** UI components remain presentational; hook contains business logic

### Why Separate CSS Files?

- **Maintainability:** Easier to locate styles for a specific component
- **Scalability:** New components don't require merging monolithic CSS files
- **Organization:** Clear relationship between `.jsx` and `.css` files
- **Performance:** CSS is still bundled once; no extra HTTP requests

### Why Theme Toggle in Floating Area?

- **Accessibility:** Always visible, doesn't compete with panel content
- **Non-intrusive:** Floating design keeps main UI clean
- **Responsive:** Hides on mobile via media query

### Why Redux/Context Not Used?

- **Scope:** App is relatively small with linear data flow
- **Simplicity:** Props drilling is manageable; reduces bundle size
- **Future:** Can be refactored if complexity grows

---

## Known Limitations & Future Improvements

### Current Limitations

1. **Microphone:** `micOn` toggle exists but audio is not yet captured or sent
2. **Chat:** `ChatPanel` is a stub; message sending not implemented
3. **Participants:** `PeoplePanel` is a stub; no real participant data
4. **End Call:** Button exists but has no logic
5. **Recording:** No option to record video/captions
6. **Accessibility:** Limited ARIA labels and keyboard navigation

### Potential Improvements

1. **Real-time Audio:** Capture mic and send audio stream or transcription alongside video
2. **Chat Sync:** WebSocket message type for chat messages
3. **Participant Management:** Real participant list with video tiles
4. **Screen Sharing:** Add screen share functionality
5. **Accessibility:** Full keyboard navigation, ARIA annotations, high-contrast mode
6. **Performance:** Optimize frame encoding (JPEG quality), throttle sending
7. **Offline Support:** Service workers for offline captions cache
8. **Undo/Redo:** Captions history and edit capability

---

## Debugging Tips

### Check WebSocket Connection

In browser console:
```javascript
// App.jsx adds socket ref; check via React DevTools
// Or monitor Network tab in DevTools (WS filter)
```

### Monitor State

Use React DevTools browser extension to inspect:
- App.jsx: `theme`
- MeetingLayout: `panelOpen`
- Components receiving props from useAslStream

### Backend Communication

Check browser Network tab:
1. WebSocket connection (Messages tab shows frame/response payload)
2. Check backend logs to confirm frames are being received

### CSS Issues

1. Inspect element using browser DevTools
2. Check `data-theme` attribute on `<html>` element
3. Verify CSS imports are in correct order in `css/index.css`
4. Check responsive breakpoints match actual screen size

---

## File Mapping Summary

| File/Folder | Purpose |
|-----------|---------|
| `App.jsx` | Root component, theme management |
| `useAslStream.js` | WebSocket, camera, state hook |
| `MeetingLayout.jsx` | Main orchestrator, routes props |
| `MeetingVideoStage.jsx` | Video display + ASL overlay |
| `SidePanel.jsx` | Tabbed info/chat panel |
| `CaptionsPanel.jsx` | ASL recognition metrics |
| `ControlsBar.jsx` | Bottom control buttons |
| `ControlButton.jsx` | Reusable button component |
| `FloatingParticipant.jsx` | Participant indicator |
| `LiveCaptionTray.jsx` | Live translation text |
| `css/global.css` | Theme variables, responsive rules |
| `css/*` | Component-specific styles |

---

## Summary

This frontend is a focused, real-time ASL translation interface built with React and Vite. It captures webcam frames, sends them to a Python backend for processing, and displays results with live captions and debugging telemetry. The architecture prioritizes clarity through separation of concerns: hooks handle business logic, components handle presentation, CSS is organized per-component, and data flows unidirectionally from state to props. The codebase is production-ready and designed for easy extension (new components, new features, theme variations).
