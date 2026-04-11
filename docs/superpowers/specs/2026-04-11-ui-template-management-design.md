# UI & Template Management Design

**Date:** 2026-04-11  
**Status:** Approved  
**Scope:** Generation screen, Suggest Template flow, Template Setup screen

---

## Context

Document-to-Deck converts PDF research into populated Google Slides presentations. The tool is used by a small internal team at BrowserStack. The existing app has a single hardcoded template (Competitor Battlecard) and no template selection UI.

This spec covers:
1. How the tool communicates what it does to new users
2. How end users generate decks (generation screen)
3. How the AI suggestion flow works
4. How power users create and configure templates

---

## Users

| Role | Description |
|---|---|
| Regular user | Uploads a PDF, picks or suggests a template, generates a deck. No template internals exposed. |
| Power user (template manager) | Designated team members who create and maintain the template library. 2–3 people max. |

---

## Screen 1 — Generation Screen

### Value communication

Two clickable entry banners sit at the top of the main card, before the template row. They communicate what the tool does and double as entry points into each path:

- **⚡ Quick Generate** — "Describe your goal, AI handles the rest." Clicking opens the natural language input inline (see Screen 2).
- **🎛 Custom Build** — "Pick a template, set your target, upload." Clicking highlights the template row below for manual selection.

Both paths converge into the same form below the banners. The banners serve as orientation and shortcut — not a mandatory mode choice.

### Template row

Always visible. Contains:
- **✦ Suggest** button (emerald `#059669`) — triggers the Suggest Template flow
- One tile per available template
- **+ Add Template** link (top-right corner, visible to power users only)

After a template is selected, the banners collapse to a single slim status bar showing the active path and selected template, with a "Change" link.

### Variable field

One dynamic input field. The label and placeholder hint are defined per template at setup time:
- Competitor Battlecard → label: "Competitor Name", hint: "e.g. Sauce Labs"
- Industry Pitch Deck → label: "Client Industry", hint: "e.g. Fintech, Healthcare"

This field appears after a template is selected.

### PDF upload

Standard file drop zone. Accepts one PDF. Appears after the variable field.

### Slide configuration

Not shown to end users. Slide defaults (on/off) are configured once during template setup. End users never see or interact with slide toggles.

### Generate CTA

Full-width `#1E1B4B` button. Active once template, variable, and PDF are all filled.

---

## Screen 2 — Suggest Template Flow

Triggered by clicking the Quick Generate banner or the ✦ Suggest button. Expands inline between the banners and the template row — no modal.

### States

**State 1 — Input**  
A natural language textarea appears within an indigo-tinted panel. Banners collapse to a slim "Quick Generate active" bar with a cancel option. Template row dims behind the input.

Prompt: "What do you need?" with placeholder text like *"I need a deck comparing BrowserStack to Sauce Labs for an enterprise fintech prospect..."*

**State 2 — AI Suggestion**  
AI returns a recommended template with a one-sentence reason:  
> "Your description mentions a head-to-head comparison with Sauce Labs for an enterprise prospect — the Competitor Battlecard template is built exactly for this."

The suggestion card uses an emerald border and "✦ Suggested" badge. Two actions: "Use this template →" and "Pick another." The manual template row remains accessible below the suggestion.

**State 3 — Accepted**  
The suggest panel collapses to the slim status bar. Template is selected in the row. If the AI could extract the target name from the description (e.g. "Sauce Labs" from the example above), the variable field is pre-filled with a green "auto-filled" badge. User can still edit it. PDF upload is the only remaining step.

---

## Screen 3 — Template Setup (Power Users Only)

Accessible via "+ Add Template" in the template row, or via the edit icon that appears on hover over an existing template tile. Both entry points are hidden from regular users.

### Fields

**Template Name**  
Free text. Shown as the tile label in the template row.

**Google Slides Template**  
URL or ID input + "Load Slides →" button. Clicking calls GAS `?action=run&mode=template`, which clones the deck and returns the style map. The slide list below auto-populates from this response.

**Target Variable**  
Two fields:
- *Label shown to users* — e.g. "Competitor Name" or "Client Industry"
- *Placeholder hint* — e.g. "e.g. Sauce Labs" or "e.g. Fintech, Healthcare"

There is exactly one variable per template. Its internal name in the prompt is `{target}`.

**Slides — Set Defaults**  
List of all slides from the loaded template. Slide names come from the title text element of each slide in the Google Slides deck (no AI inference needed — the title is already there in the style map). Each slide has an On/Off toggle. These defaults are what end users see when generating, pre-applied silently.

### Save

Persists the template to the template registry (config/env or a lightweight store). The new template tile appears in the template row immediately.

---

## Design System

Follows the project's existing `editorial_enterprise_blend_prd` design:

| Token | Value |
|---|---|
| Primary | `#1E1B4B` (deep indigo) |
| Background (canvas) | `#F9FAFB` |
| Surface (card) | `#FFFFFF` |
| Surface low | `#F3F4F6` |
| Accent (AI actions only) | `#059669` (emerald) |
| Text primary | `#111827` |
| Text secondary | `#6B7280` |
| Text muted | `#9CA3AF` |
| Border | `#E5E7EB` |
| Display font | Newsreader (serif) |
| Body font | Switzer (sans-serif) |
| Border radius (main card) | 0px (sharp) |
| Card shadow | `0 20px 40px -10px rgba(30,27,75,0.06)` |

Emerald `#059669` is reserved exclusively for AI-driven actions (✦ Suggest button, suggestion card border, auto-filled badge). It signals "AI is acting here."

Section separation uses background tonal shifts (`#F9FAFB` alternating rows) rather than divider lines.

---

## What Is Not In Scope

- Multi-variable templates (one `{target}` variable per template, always)
- Per-generation slide toggling by end users (defaults set at template setup, not overridable at generation time)
- User authentication or role management — power user mode is controlled by a single env flag (`POWER_USER_MODE=true`). When set, "+ Add Template" and the template edit icon are visible. No login or role system needed.
- Template deletion or archiving (future iteration)
- Loading/success states (covered separately in existing Stitch screens)

---

## Mockups

Stored in `.superpowers/brainstorm/` (add `.superpowers/` to `.gitignore`):
- `polished-ui.html` — all three screens with full design system applied
- `suggest-dialog.html` — Suggest Template flow, three states
- `template-setup.html` — Template setup screen detail
- `generation-screen-clean.html` — clean end-user generation screen
