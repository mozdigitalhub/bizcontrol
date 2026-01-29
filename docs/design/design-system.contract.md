# BizControl — UI Design System Contract (MUST)

This document is a strict UI/UX contract.
Any UI code that violates these rules is considered INVALID.

---

## 1) Colors

1. Use ONLY colors defined in `ui-design-system.md`.
2. Primary actions MUST use Primary color.
3. Secondary actions MUST NOT use Primary color.
4. Destructive actions MUST use Danger color.
5. Introducing new colors is FORBIDDEN.

---

## 2) Typography

1. Font MUST be Inter (or system fallback).
2. Text size MUST follow defined scale.
3. Minimum font size is 12px.
4. Mixing fonts is FORBIDDEN.

---

## 3) Buttons

1. Each screen MUST have at most ONE Primary button.
2. Primary buttons are for main actions only.
3. Destructive actions MUST use Danger button.
4. Button labels MUST be explicit (no “OK”, “Yes”, “Submit”).
5. Icons (if used) MUST be placed on the left.

---

## 4) Forms & Inputs

1. Every input MUST have a visible label.
2. Placeholder MUST NOT replace label.
3. Required fields MUST show `*`.
4. Error state MUST show:
   - red border
   - clear, specific error message
5. Generic error messages are FORBIDDEN.

---

## 5) Tables & Lists

1. Tables MUST have header + pagination.
2. Text columns align left.
3. Numeric and currency columns align right.
4. Row actions MUST be on the right.
5. Destructive actions MUST be visually distinct.

---

## 6) Cards & Dashboards

1. Cards MUST use standard padding and border radius.
2. KPI cards MUST highlight value first, label second.
3. Strong colors are FORBIDDEN inside cards (except semantic icons).

---

## 7) Layout & Spacing

1. Use spacing scale: 8 / 16 / 24 / 32.
2. Layout MUST be responsive (mobile-first).
3. No random margins or paddings are allowed.

---

## 8) Feedback & States

1. Every user action MUST have visual feedback.
2. Loading MUST use skeletons when possible.
3. Toasts MUST:
   - appear top-right
   - auto-close in 3–5s
4. Silent actions are FORBIDDEN.

---

## 9) Modals

1. Modals MUST have overlay.
2. Primary action on the right.
3. Cancel action on the left.
4. Long forms inside modals are FORBIDDEN.

---

## 10) Icons

1. Use ONE icon library only.
2. Icon size MUST be 20–24px.
3. Icons MUST NOT replace text-only actions.

---

## 11) Dark Patterns (FORBIDDEN)

1. Hidden confirmations
2. Misleading buttons
3. Destructive actions without confirmation
4. Ambiguous text

---

## 12) Codex Enforcement Rules

Before generating UI code, Codex MUST:

1. Read `ui-design-system.md`
2. Validate compliance with this contract
3. Reject solutions that introduce:
   - new colors
   - new button styles
   - inconsistent spacing or typography

---

## 13) Required Codex Output

For every UI task, Codex MUST:

1. List used components (Button, Input, Card, Table, etc.)
2. Confirm compliance with this contract
3. Explicitly state: “UI follows BizControl Design System”

## 14) Colors & Contrast (MUST)

1. Text on any strong colored background (Primary/Secondary/Danger/Info/Success) MUST be #FFFFFF.
2. Badges/Chips MUST follow one of:
   - Solid: strong bg + white text
   - Soft: light bg + strong text
3. Low-contrast text (e.g., blue on blue, gray on light gray) is FORBIDDEN.

## 15) Forms & Icons (MUST)

1. Every form control MUST have a leading icon INSIDE the input/select field.
2. Icons outside inputs for form controls are FORBIDDEN.
3. Inputs MUST reserve left padding so text never overlaps the icon.
