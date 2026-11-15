# 03: Design System

**Look and feel:** modern fintech ops console. Light, airy, quiet. Think Linear / Stripe Dashboard. Brand colors are taken from the pitch deck (deep indigo + a single orange accent) so the demo and the deck feel like one product.

Implement these as **named tokens** (CSS variables / a `theme.py` constants file). Never hard-code a hex in a component.

## 1. Color tokens
### Neutrals
| Token | Hex | Use |
|---|---|---|
| `--canvas` | `#F6F7F9` | App background |
| `--surface` | `#FFFFFF` | Cards, panels, tables |
| `--surface-sunken` | `#F0F2F5` | Inputs, table header, code blocks |
| `--border` | `#E4E7EC` | Hairlines, card borders |
| `--border-strong` | `#CDD2DA` | Hover borders, focused dividers |
| `--ink` | `#0F1222` | Primary text |
| `--ink-muted` | `#555B6E` | Secondary text |
| `--ink-subtle` | `#8A90A2` | Captions, placeholders (not for essential info) |

### Brand
| Token | Hex | Use |
|---|---|---|
| `--brand` | `#4A3C8C` | Primary buttons, selected nav, links, focus ring |
| `--brand-strong` | `#3A2E73` | Button hover/pressed |
| `--brand-tint` | `#F1EEFB` | Selected row, active nav background |
| `--sidebar` | `#12142B` | Sidebar background (deep ink-indigo) |
| `--sidebar-text` | `#C9CCE0` | Sidebar text; active item is `#FFFFFF` on `rgba(255,255,255,.08)` |

### Semantic (always paired: foreground + tint background)
| Meaning | Fg | Tint bg | Used for |
|---|---|---|---|
| **Attention** (human needed) | `#C25E0E` | `#FFF3E6` | Needs approval, over cap, `needs_approval` decisions. **The one accent.** |
| **Success** | `#17744C` | `#E8F6EF` | Resolved, executed, passed checks |
| **Danger** | `#B8312D` | `#FDEDEC` | Blocked, error, rejected, missing policy_ref |
| **Info** | `#2859C5` | `#EAF0FE` | AI working, read-only calls |
| **Neutral** | `#555B6E` | `#EEF0F4` | Waiting, platform actions, disabled |
| **Escalated** | `#4A3C8C` | `#F1EEFB` | Escalated (hand-off, no decision button) |

**Rule:** color never carries meaning alone. Every colored element also has a text label or an icon.
**Contrast:** body text ≥ 4.5:1 on its background; all fg/tint pairs above meet this.

## 2. Status language (single source of truth)
Use these mappings everywhere (queue, case header, audit, overview).

### Case status → chip
| `status` | Label | Style |
|---|---|---|
| `awaiting_approval` | Needs approval | Attention |
| `escalated` | Escalated | Escalated |
| `open` | AI working | Info |
| `need_info` | Waiting on customer | Neutral |
| `resolved` | Resolved | Success |
| `rejected` | Rejected | Danger |

### Gateway decision → chip (audit)
| `decision` | Label | Style |
|---|---|---|
| `executed` | Executed | Success |
| `needs_approval` | Needs approval | Attention |
| `blocked` | Blocked | Danger |
| `error` | Error | Danger |
| anything else | show raw value | Neutral |

### Tier → friendly label and chip
| `tier` | Label | Style | Plain meaning (tooltip) |
|---|---|---|---|
| `read_only` | Read | Neutral | Looks up data, changes nothing |
| `reversible` | Reversible | Info | Can be undone |
| `money_moving` | Money | Attention | Moves money, capped, needs policy |
| `sensitive` | Sensitive | Attention | Changes account identity, needs step-up |
| `protective` | Protective | Escalated | Protects the customer (e.g. freeze), acts first |
| `platform` | Platform | Neutral | Internal workflow (escalate, follow-up) |

## 3. Typography
- **Font:** `Inter` (fallback: `-apple-system, Segoe UI, Roboto, sans-serif`). **Mono:** `JetBrains Mono` / `ui-monospace` for IDs, refs, JSON.
- **Numbers:** `font-variant-numeric: tabular-nums` for all amounts and counts.

| Style | Size / weight / line | Use |
|---|---|---|
| Display | 32 / 700 / 1.15 | Hero metric only |
| H1 | 22 / 650 / 1.3 | Page title |
| H2 | 16 / 650 / 1.4 | Card titles, section titles |
| Body | 14 / 400 / 1.55 | Default |
| Body-strong | 14 / 600 / 1.55 | Labels with emphasis |
| Caption | 12 / 500 / 1.4 | Metadata, chips, table headers (uppercase +0.04em tracking for table headers only) |
| Mono | 13 / 500 | `CASE-0007`, `T1002`, `RFND-T1001`, policy refs |

Amounts: always `₹` + Indian digit grouping (`₹5,000`, `₹1,20,000`). Never show raw floats (`5000.0`).

## 4. Spacing, radius, elevation
- **4px base grid.** Scale: 4, 8, 12, 16, 24, 32, 48.
- Card padding: 16–20. Gap between cards: 16. Page gutters: 32.
- **Radius:** inputs/buttons 8, cards 12, chips pill (999).
- **Elevation:** flat. Cards = 1px `--border`, **no heavy shadows**. Only the dialog and drawer get a soft shadow `0 8px 30px rgba(15,18,34,.12)`.

## 5. Core components
Each component below must be a single reusable function (`components.py`) so every screen looks identical.

### 5.1 `chip(label, style, icon=None)`
Pill, 12px caption text, 4×10 padding, tint bg + fg text, optional 12px leading icon or dot. Never wrap to two lines.

### 5.2 `button`
| Variant | Style | Use |
|---|---|---|
| Primary | `--brand` bg, white text | Approve & execute |
| Secondary | white bg, `--border-strong` border, ink text | Reject, cancel |
| Danger-quiet | white bg, Danger fg, Danger-tint on hover | Confirm reject |
| Ghost | no border, brand text | Inline actions ("Copy ID") |

Height 40 (primary actions) / 32 (inline). Disabled = Neutral tint with muted text, plus a tooltip explaining *why* it is disabled.

### 5.3 `stat_tile(label, value, hint=None, accent=None)`
Card with caption label (top), 28px value, optional hint line. `accent="attention"` adds a 3px left border in orange and tints the value. Used in the status strip and Overview.

### 5.4 `case_row(case)` (queue list item)
Height ≈ 76. Layout:
```
● Rahul Sharma                        2d ago
  Flight Booking · ₹5,000 reversal    [Needs approval]
  CASE-0007
```
- Row 1: customer name (600) + relative age (muted, right-aligned).
- Row 2: one-line "what" (muted) + status chip (right).
- Row 3: case id (mono, subtle).
- Selected: `--brand-tint` bg + 3px `--brand` left bar. Hover: `--surface-sunken`.
- Attention rows get a small orange dot before the name. This is the only "urgency" signal.

### 5.5 `decision_card(case)`: the hero component
Elevated by position, not shadow: a white card with a **3px orange top border** when it needs approval. Contents in file 04.

### 5.6 `fact_grid(items)`
Two- or three-column label/value pairs. Labels = caption muted; values = body-strong; ids and refs in mono with a click-to-copy.

### 5.7 `check_item(state, text)`
One line with an icon: ✓ Success (passed), ⚠ Attention (limit exceeded), ✕ Danger (failed), ○ Neutral (not applicable). Text is plain language.

### 5.8 `timeline_item(actor, action, result, time)`
Vertical rail with a dot. Dot color = decision style. Primary text = plain-language sentence. Secondary = tool name (mono) + tier chip. See file 04 for wording rules.

### 5.9 `policy_callout(ref, source, section, text?)`
A left-bordered (3px `--brand`) quote-style block with a book icon: "**Policy applied**  `paytm_upi_failed_txn.md` › Refunds". If rule text is available, show it in muted body below. If a `policy_ref` is missing on a money action, show the Danger variant: "No policy cited".

### 5.10 `empty_state(icon, title, body)`
Centered, 48px muted icon, H2 title, muted body. Never a blank area.

### 5.11 `toast`
Bottom-right, 4s, one line + icon. Success/Danger styles only.

### 5.12 `dialog` (confirmation)
480px wide, centered, scrim `rgba(15,18,34,.4)`. Title, summary fact grid, two buttons (secondary left, primary right).

## 6. Iconography
One line-icon set only (Lucide). 16px inline, 20px nav. Suggested: `inbox` (Queue), `shield-check` (Audit), `layout-dashboard` (Overview), `wrench` (Tools), `check-circle`, `alert-triangle`, `x-circle`, `book-open` (policy), `clock`, `snowflake` (freeze). **In Streamlit** you may use Material symbols (`:material/inbox:`) or emoji-free text-only labels; stay consistent, never mix sets.

## 7. Motion
Minimal and purposeful. 150ms ease-out for hover and selection. New cases arriving: a one-time 600ms orange-tint fade on the row. No page transitions, no bouncing, no spinners longer than a skeleton.

## 8. Do / Don't
- **Do** use whitespace instead of lines and boxes to separate things.
- **Do** keep one primary button per view.
- **Don't** use more than one accent color (orange) per screen for "attention".
- **Don't** show raw enum values or snake_case in primary UI.
- **Don't** use emoji as UI chrome (they read as unprofessional in a finance product).
