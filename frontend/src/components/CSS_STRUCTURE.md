# CSS Structure Documentation

## Overview
The CSS has been split into component-specific files organized in a dedicated `css/` directory for better maintainability and clarity. All styles are imported via `css/index.css` which is imported in `ui.jsx`.

## Directory Structure

```
components/
├── css/
│   ├── index.css                 (Master import file)
│   ├── global.css                (Theme variables, animations, responsive)
│   ├── MeetingLayout.css         (Main container & layout)
│   ├── MeetingVideoStage.css     (Camera/video display)
│   ├── CaptionsPanel.css         (ASL recognition overlay)
│   ├── SidePanel.css             (Right side panel with tabs)
│   ├── PeoplePanel.css           (Participant list)
│   ├── ChatPanel.css             (Chat messages)
│   ├── ControlButton.css         (Individual buttons)
│   ├── ControlsBar.css           (Bottom control bar)
│   ├── FloatingElements.css      (Meeting code & person indicators)
│   └── PanelTabs.css             (Tab reference file)
├── ui.jsx                        (Main UI component, imports css/index.css)
├── CSS_STRUCTURE.md              (This file)
└── meeting/
    ├── MeetingLayout.jsx
    ├── MeetingVideoStage.jsx
    ├── CaptionsPanel.jsx
    ├── SidePanel.jsx
    └── ... (other components)
```

## File Organization

### Global Styles (`css/global.css`)
Contains theme variables, animations, scrollbar styling, and responsive breakpoints
- CSS variables for dark/light themes
- Keyframe animations (slideInRight, slideInDown, slideUp, fadeIn)
- Base HTML/body styles
- Responsive media queries (1024px, 768px, 480px)

### Component-Specific Styles (in `css/` directory)

#### Layout
- **`MeetingLayout.css`** - Main container and layout structure
  - `.app` - Root app container
  - `.main-layout` - Main flex container with row direction

#### Video Display
- **`MeetingVideoStage.css`** - Camera/video display component
  - `.video-area` - Video container with rounded borders
  - `.main-video-container` - Main video display area
  - `.video-frame` - Frame wrapper
  - `.video-element` - HTML video element
  - `.camera-off-state` - Offline camera state display
  - `.video-overlay-name` - Name overlay (You • Presenter)

#### Side Panel & Tabs
- **`SidePanel.css`** - Right slide-in panel structure
  - `.side-panel` - Main panel container with border and shadow
  - `.panel-header` - Header with close button
  - `.panel-close` - Close button styling
  - `.side-tabs` - Tab navigation bar
  - `.tab` and `.tab.active` - Tab button styling
  - `.panel-content` - Content container for tabs

#### Caption/ASL Overlay
- **`CaptionsPanel.css`** - ASL recognition overlay
  - `.asl-overlay` - Overlay container with blur effect
  - `.asl-overlay-title` - Title text
  - `.asl-overlay-text` - Recognition result text
  - `.asl-overlay-confidence` - Confidence score display

#### People/Participants List
- **`PeoplePanel.css`** - Participant list display
  - `.status-chip` - Status badge
  - `.info-box` - Information box styling
  - `.info-label` and `.info-value` - Info text styling
  - `.person-item` - Individual participant item
  - `.person-avatar` - Avatar circle
  - `.person-details` - Name and meta info
  - `.status-indicator` - Status dot (active/online)

#### Chat Messages
- **`ChatPanel.css`** - Chat messages display
  - `.chat-box` - Message container
  - `.chat-user` - Username styling
  - `.chat-message` - Message text styling

#### Control Buttons
- **`ControlButton.css`** - Individual button component
  - `.control-btn` - Regular control button
  - `.end-btn` - End call button (danger color)
  - `.btn-icon` - Icon container
  - `.btn-tooltip` - Hover tooltip display
  - Hover and active states

#### Control Bar
- **`ControlsBar.css`** - Bottom control bar
  - `.bottom-bar` - Container for all buttons
  - Button styling specific to the bar
  - Dark/light theme support

#### Floating Elements
- **`FloatingElements.css`** - Floating indicators and info
  - `.floating-meeting-info` - Meeting code display
  - `.meeting-code` - Code box styling
  - `.code-label` and `.code-value` - Code text styling
  - `.theme-toggle-float` - Theme toggle button
  - `.floating-person` - Participant indicator box
  - `.floating-person.you` and `.floating-person.other` - Positioning
  - `.person-avatar-float` - Small avatar in indicator
  - `.status-dot` - Connection status indicator

#### Panel Tabs
- **`PanelTabs.css`** - References SidePanel.css for shared tab styles

## Import Order
Files are imported in `css/index.css` in this order:
1. `global.css` - Base styles and variables
2. Layout components
3. Content components
4. Interactive components
5. Floating/overlay components

## Theming
All components support both dark and light themes via `html[data-theme="light"]` selectors.
CSS variables from `global.css` are used throughout for consistent theming.

## Responsive Design
Responsive breakpoints are defined in `global.css`:
- **Large screens (1024px)** - Minor adjustments to sizes and spacing
- **Tablets (768px)** - Side panel becomes full-width, floating elements hidden
- **Mobile (480px)** - Optimized for small screens

## How to Use
When working on a specific component:
1. Find the corresponding `.css` file in `css/` directory
2. Update only that file
3. Restart dev server if needed
4. Changes are automatically included via the `css/index.css` import

## Benefits
✅ **Clarity** - Each component file contains only its own styles  
✅ **Maintainability** - Easy to find and update specific component styles  
✅ **Scalability** - New components can have their own CSS files  
✅ **Organization** - Clear separation of concerns in a dedicated directory  
✅ **Performance** - CSS is still bundled together, no additional HTTP requests  
✅ **Navigation** - Simple `css/` directory structure makes file discovery easy  

## File Naming Convention
- Component CSS files are named after their corresponding JSX component
- Example: `MeetingLayout.jsx` → `MeetingLayout.css`
- Global styles go in `global.css`
- Master imports in `index.css`

