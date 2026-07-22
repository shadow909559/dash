# Desktop Automation

## Overview

DASH provides desktop automation capabilities for mouse, keyboard, clipboard, window management, and screenshots.

## Components

### Mouse Automation

- Move cursor to coordinates
- Click (left/right/middle)
- Double-click
- Scroll
- Drag and drop

### Keyboard Automation

- Type text
- Press hotkeys
- Key combinations

### Clipboard

- Copy text to clipboard
- Read clipboard contents
- Clear clipboard

### Window Management

- List open windows
- Bring window to focus
- Minimize/Maximize/Restore
- Close windows

### Screenshots

- Capture full screen
- Capture active window
- Capture region

## Permission Levels

| Level | Description |
|-------|-------------|
| AUTO | No confirmation needed |
| CONFIRM | User must confirm action |
| RESTRICTED | Requires elevated auth |

## Example

```python
# Click at coordinates
await desktop_skill.click(x=100, y=200)

# Type text
await desktop_skill.type_text("Hello World")

# Take screenshot
screenshot = await desktop_skill.capture_screenshot()
