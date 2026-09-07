"""Accessibility Statement for DASH.

Version 1.0 — Effective: September 7, 2026

This document honestly describes DASH's current accessibility state,
including known limitations.
"""

ACCESSIBILITY_VERSION = "1.0"
ACCESSIBILITY_EFFECTIVE = "2026-09-07"

ACCESSIBILITY_STATEMENT = r"""# DASH Accessibility Statement

**Version:** 1.0
**Effective Date:** September 7, 2026
**Last Updated:** September 7, 2026

---

## 1. Our Commitment

DASH is committed to making the application usable by as many people
as possible. We aim to meet WCAG 2.2 Level AA where applicable and
follow established accessibility best practices.

---

## 2. Current Accessibility Features

### 2.1 Keyboard Accessibility

- All interactive elements are reachable via keyboard (Tab, Enter,
  Space, Escape, arrow keys)
- The command palette (Ctrl+K / Cmd+K) provides keyboard-only
  navigation to any page
- Forms support logical tab order
- Dialogs can be dismissed with Escape
- Skip link ("Skip to main content") is provided for keyboard users

### 2.2 Focus Management

- Visible focus indicators are provided on all interactive elements
- Focus order follows the logical reading and interaction order
- Focus is managed when navigating between pages and opening dialogs
- The focus ring uses sufficient contrast against the background

### 2.3 Screen Reader Compatibility

- Semantic HTML structure is used (headings, landmarks, lists)
- ARIA labels are provided on interactive elements without visible
  text labels (icon buttons, the Orb)
- The Orb toggle has `role="button"`, `tabIndex={0}`, and
  `aria-label="Toggle voice input"`
- Status announcements use `aria-live="polite"` regions
- Page loading states include `role="status"` and `aria-label`

### 2.4 Form Accessibility

- All form fields have associated labels (explicit `<label>` or
  `aria-label`)
- Required fields are indicated
- Validation errors are displayed adjacent to the relevant field
- Input types are appropriate (email, password, text)
- Autocomplete attributes are set where applicable

### 2.5 Color and Contrast

- The design system uses CSS custom properties for consistent theming
- Text meets WCAG AA contrast ratios against the dark background
  (`#e0f0ff` on `#080c14` = 13.8:1)
- Status indicators use both color and text (not color alone)
- Interactive states are communicated through more than just color
  changes

### 2.6 Responsive Design

- The layout adapts to different window sizes
- The sidebar collapses to icon-only on narrow viewports
- Content is readable without horizontal scrolling
- Touch targets meet minimum size requirements

### 2.7 Motion and Animation

- Animations are used sparingly and only for functional purposes
  (loading states, status indicators, the Orb)
- Animations do not auto-play distractingly
- The Orb visual is a decorative element; the voice input
  functionality is accessible without it

---

## 3. Known Limitations

We honestly acknowledge the following accessibility limitations:

### 3.1 The Orb (3D Visual)

- The animated 3D Orb is not fully screen-reader accessible
- Voice input can be activated via the microphone button (which has
  proper aria-label), but the Orb's visual states are not described
  to assistive technology
- The Orb's state transitions (idle, thinking, speaking) are
  communicated through text labels rather than ARIA live regions

### 3.2 Charts and Data Visualization

- System monitor charts may not be fully accessible to screen
  readers
- Data trends use text-based summaries where possible

### 3.3 Color Themes

- Only one color theme is currently provided (dark mode)
- Users who require light mode or high-contrast themes may need
  to adjust system settings
- Custom color themes are not yet supported

### 3.4 Keyboard Shortcuts

- Some page-specific shortcuts are not yet implemented
- The command palette covers most navigation needs

### 3.5 Mobile/Touch

- DASH is primarily a desktop application
- Touch interaction on tablets may be limited

### 3.6 Language

- DASH currently only supports English
- Screen readers cannot switch language profiles

---

## 4. Testing

Accessibility testing includes:

- Keyboard-only navigation testing across all pages
- Focus visibility verification
- ARIA label audit on icon-only buttons
- Screen reader testing with NVDA on Windows
- Contrast ratio verification for key text elements
- Form label and error announcement testing

Automated accessibility scans are not relied upon as proof of complete
accessibility; manual testing is performed for interaction patterns.

---

## 5. Feedback

If you encounter an accessibility barrier in DASH, please report it:

- **GitHub Issues:** https://github.com/shadow909559/dash/issues
  (use the "accessibility" label)
- **Email:** accessibility@dash-ai.dev

We will review every accessibility report and prioritize fixes based
on impact.

---

## 6. Technical Specifications

DASH is built with:

- React 18 with TypeScript
- Vite for bundling
- Electron for desktop
- Semantic HTML5
- CSS custom properties for theming
- Lucide icons with aria-labels
- JetBrains Mono and Inter typefaces

---

## 7. Applicable Standards

We target compliance with:

- WCAG 2.2 Level AA
- Section 508 (where applicable)
- EN 301 549 (where applicable)
"""

__all__ = ["ACCESSIBILITY_STATEMENT", "ACCESSIBILITY_VERSION", "ACCESSIBILITY_EFFECTIVE"]
