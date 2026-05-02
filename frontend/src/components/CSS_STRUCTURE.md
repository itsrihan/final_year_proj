# CSS Architecture & Styling Reference

> **For comprehensive frontend architecture, component details, and data flow:** See [FRONTEND_INFO.md](./FRONTEND_INFO.md)
>
> This document focuses on CSS organization, theming, and styling patterns.

---

## Quick Overview

CSS is organized in a dedicated `css/` directory with component-specific files imported via `css/index.css`. This approach provides clarity, maintainability, and scalability while keeping styles modular and easy to locate.

---

## CSS File Structure

```
components/
├── css/
│   ├── index.css                 (Master import file - single entry point)
│   ├── global.css                (Theme vars, animations, responsive queries)
│   ├── MeetingLayout.css         (App container and main layout)
│   ├── MeetingVideoStage.css     (Video display, ASL overlay)
│   ├── CaptionsPanel.css         (Recognition metrics in side panel)
│   ├── SidePanel.css             (Panel container, header, tabs)
│   ├── PeoplePanel.css           (Participant list and avatars)
│   ├── ChatPanel.css             (Chat message display)
│   ├── ControlButton.css         (Individual control button)
│   ├── ControlsBar.css           (Bottom control bar container)
│   ├── FloatingElements.css      (Meeting code, theme toggle, participant indicator)
│   ├── LiveCaptionTray.css       (Live translation text strip)
│   └── PanelTabs.css             (Tab button styling reference)
└── FRONTEND_INFO.md              (Full architecture guide)
```

---

## How CSS Is Imported

**Single import point:** `css/index.css`

```css
@import "global.css";
@import "MeetingLayout.css";
@import "MeetingVideoStage.css";
@import "SidePanel.css";
@import "CaptionsPanel.css";
@import "PeoplePanel.css";
@import "ChatPanel.css";
@import "ControlButton.css";
@import "ControlsBar.css";
@import "FloatingElements.css";
@import "LiveCaptionTray.css";
@import "PanelTabs.css";
```

This file is imported **once** in `ui.jsx`, ensuring CSS is bundled efficiently with no redundant imports.

---

## Global Styles (css/global.css)

### CSS Variables (Theme Support)

Both dark and light themes are defined using CSS custom properties:

```css
html[data-theme="dark"] {
  --color-bg: #1a1a1a;
  --color-text: #ffffff;
  --color-border: #333333;
  /* ... more variables */
}

html[data-theme="light"] {
  --color-bg: #ffffff;
  --color-text: #1a1a1a;
  --color-border: #cccccc;
  /* ... more variables */
}
```

**Theming mechanism:**
- App.jsx reads theme from localStorage
- Sets `document.documentElement.setAttribute("data-theme", theme)`
- All components use CSS variables (e.g., `background-color: var(--color-bg)`)
- Theme toggle button triggers re-render

### Animations

Keyframe animations for UI transitions:

- `slideInRight` – side panel entrance
- `slideInDown` – top element entrance
- `slideUp` – bottom element movement
- `fadeIn` – opacity fade in

### Responsive Breakpoints

Three main breakpoints defined in `global.css`:

```css
@media (max-width: 1024px) { /* Large screens */ }
@media (max-width: 768px)  { /* Tablets */ }
@media (max-width: 480px)  { /* Mobile */ }
```

**Responsive Changes:**
- **≤480px (Mobile):** Hidden floating elements, full-width video, stacked layout
- **481–768px (Tablet):** Side panel becomes full-width when open, adjusted spacing
- **≥769px (Desktop):** Side panel fixed width, side-by-side layout, all floating elements visible

---

## Component-Specific CSS Files

### Layout Components

**`MeetingLayout.css`**
- `.app` – Root container with theme attribute
- `.main-layout` – Flex container managing video + panel layout
- `.main-layout.panel-open` – Layout adjustment when side panel is visible

**`MeetingVideoStage.css`**
- `.video-area` – Container with rounded borders and shadow
- `.main-video-container` – Video viewport wrapper
- `.video-frame` – Frame wrapper for positioning
- `.video-element` – The actual `<video>` element
- `.camera-off-state` – Placeholder when camera is disabled
- `.video-overlay-name` – "You • Presenter" label overlay
- `.asl-overlay` – ASL recognition box with blur background
- `.asl-overlay-title`, `.asl-overlay-text`, `.asl-overlay-confidence` – Recognition display

### Panel Components

**`SidePanel.css`**
- `.side-panel` – Main panel container (fixed width on desktop, full-width on mobile)
- `.panel-header` – Header with tab navigation and close button
- `.panel-close` – Close button (✕)
- `.side-tabs` – Tab navigation bar
- `.tab` – Individual tab button
- `.tab.active` – Active tab highlight
- `.panel-content` – Content area below tabs

**`PanelTabs.css`**
- References styles from `SidePanel.css` for tab buttons

**`CaptionsPanel.css`**
- `.status-chip` – "Translator ON/OFF" badge
- `.info-box` – Container for each info item
- `.info-label` – Label text (gray)
- `.info-value` – Value text (bright/prominent)
- `.info-value.small` – Smaller text for secondary values
- `.helper-text` – Explanatory text at bottom

**`PeoplePanel.css`**
- `.person-item` – Individual participant card
- `.person-avatar` – Avatar circle with initials
- `.person-details` – Name and metadata
- `.person-name` – Participant name
- `.status-indicator` – Online/offline dot

**`ChatPanel.css`**
- `.chat-box` – Message container
- `.chat-user` – Username label
- `.chat-message` – Message text
- `.chat-timestamp` – Message time

### Control Components

**`ControlButton.css`**
- `.control-btn` – Standard control button
- `.control-btn:hover` – Hover state
- `.control-btn.active` – Active/toggled state
- `.btn-icon` – Icon container
- `.btn-tooltip` – Tooltip text (shown on hover)
- `.end-btn` – Danger-variant button (red styling)

**`ControlsBar.css`**
- `.bottom-bar` – Footer container with all buttons
- Button layout and spacing
- Dark/light theme support for bar background

### Floating Elements

**`FloatingElements.css`**
- `.floating-meeting-info` – Container for meeting code and theme toggle
- `.meeting-code` – Meeting code box with label and code
- `.code-label`, `.code-value` – Code text parts
- `.theme-toggle-float` – Theme toggle button in floating area
- `.floating-person` – Floating participant indicator
- `.floating-person.you` – Current user indicator (corner position)
- `.floating-person.other` – Other participant (different corner)
- `.person-avatar-float` – Small avatar in floating card
- `.person-name-float` – Name in floating card
- `.status-dot` – Connection indicator dot (online/offline)

### Caption Display

**`LiveCaptionTray.css`**
- `.live-caption-tray` – Container for live translation text
- `.live-caption-tray.visible` – Show/hide toggle
- `.live-caption-label` – "Live ASL Translation" header
- `.live-caption-text` – Translated text display
- `.live-caption-text.empty` – Styling when no text

---

## Naming Conventions

### BEM-Inspired Pattern

**Block:** `.control-btn`
**Element:** `.btn-icon`, `.btn-tooltip`
**Modifier:** `.control-btn.active`, `.end-btn`

### State Classes

- `.active` – Active/selected state
- `.danger-state` – Danger/error state (red)
- `.visible` – Visibility toggle
- `.panel-open` – Layout state (panel is open)
- `.online` / `.offline` – Connection status
- `.empty` – Empty content state

### Responsive Classes

Applied via media queries; no specific class names (CSS handles via breakpoints).

---

## Theme Implementation

### How It Works

1. **Storage:** Theme preference saved in localStorage as `"app-theme"`
2. **Initialization:** App.jsx reads localStorage on mount
3. **Application:** `document.documentElement.setAttribute("data-theme", theme)`
4. **Scoping:** All CSS selectors use `html[data-theme="dark"]` or `html[data-theme="light"]`
5. **Fallback:** Default theme is "dark"

### Using Theme Variables in Components

In any CSS file, reference variables:

```css
.my-component {
  background-color: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}
```

No additional logic needed; CSS automatically applies correct colors based on active theme.

### Adding New Theme Variables

1. Open `css/global.css`
2. Add variable to both `html[data-theme="dark"]` and `html[data-theme="light"]`
3. Use in other CSS files via `var(--variable-name)`

---

## Responsive Design Strategy

### Mobile-First Approach

Styles are written for mobile first, then enhanced for larger screens via media queries.

### Breakpoint Strategy

```css
/* Base styles (mobile: 0–480px) */
.my-element { width: 100%; }

/* Tablet: 481–768px */
@media (min-width: 481px) {
  .my-element { width: 50%; }
}

/* Desktop: 769px+ */
@media (min-width: 769px) {
  .my-element { width: 33%; }
}
```

### Layout Changes by Screen Size

| Feature | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Side Panel | Full-width, modal | Full-width, modal | Fixed width, always visible |
| Floating Code | Hidden | Hidden | Visible, fixed position |
| Floating Participant | Hidden | Hidden | Visible, corner |
| Video Size | Full viewport | Full viewport | Reduced for panel |
| Control Bar | Full-width | Full-width | Centered |

---

## Common CSS Patterns

### Flex Layout

Most containers use flexbox:

```css
.main-layout {
  display: flex;
  flex-direction: row;
  gap: 16px;
}

@media (max-width: 768px) {
  .main-layout {
    flex-direction: column;
  }
}
```

### Overlay Pattern

For overlays (ASL recognition box, tooltips):

```css
.asl-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  border-radius: 8px;
  padding: 16px;
  z-index: 10;
}
```

### State-Driven Styling

Toggle visibility and color based on data attributes:

```css
.control-btn.active {
  background-color: var(--color-accent);
  color: white;
}

.control-btn:hover:not(.active) {
  opacity: 0.8;
}
```

---

## Performance Considerations

1. **Single Import:** CSS imported once in `ui.jsx`, not scattered across components
2. **CSS Variables:** Used instead of inline styles for theme switching
3. **Animations:** `transform` and `opacity` used (GPU-accelerated)
4. **Responsive:** Media queries used instead of JavaScript-driven resizing
5. **No Unused CSS:** Each file contains only styles for its component

---

## How to Update Styles

### For Existing Components

1. Find the corresponding `.css` file in `components/css/`
2. Locate the class name in the JSX component
3. Update the CSS in the appropriate file
4. Save; dev server hot-reloads automatically

### For New Components

1. Create `NewComponent.jsx` in `components/meeting/`
2. Create `NewComponent.css` in `components/css/`
3. Import CSS in `css/index.css` at appropriate position
4. Use class names from the new CSS file in the JSX
5. Dev server automatically applies new styles

---

## Debugging CSS Issues

### Check Applied Theme

In browser DevTools Console:
```javascript
document.documentElement.getAttribute("data-theme")
```

### Inspect Element

1. Right-click element → Inspect
2. Check computed styles
3. Verify `data-theme` attribute is correct
4. Check CSS variable values

### Check CSS Import Order

CSS specificity issue? Check `css/index.css` import order. Later imports override earlier ones.

### Media Query Testing

1. Open DevTools
2. Toggle device toolbar (Ctrl+Shift+M / Cmd+Shift+M)
3. Drag to different sizes
4. Check which breakpoint is active via console

---

## Summary

CSS is organized per-component in a dedicated `css/` directory. Theme support is implemented via CSS variables and the `data-theme` attribute. Responsive design uses mobile-first approach with three main breakpoints. BEM-inspired naming keeps selectors clear and maintainable. Single import point in `css/index.css` ensures efficient bundling and prevents duplicate CSS in production.

For full architectural details, component explanations, and data flow, see [FRONTEND_INFO.md](./FRONTEND_INFO.md).

