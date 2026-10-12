# UX principles (apply to every segment and every style)

Style decides how the site *looks*. These decide whether people can *use* it. When a style rule
conflicts with a principle here, the principle wins. The front persona cites these IDs (e.g. `H1`,
`L-Fitts`) when it explains a fix.

Sources: NN/g's 10 usability heuristics, Laws of UX (lawsofux.com), Don Norman's affordances and
signifiers, NN/g's guide to clickable elements, WCAG 2.2, and Baymard checkout research (2025
benchmark). See `sources.md`.

## A. Nielsen's 10 usability heuristics

| ID | Heuristic | What it means in a frontend |
|---|---|---|
| H1 | Visibility of system status | Every action gets feedback in < 100ms: pressed state, spinner in the button, toast, updated count. Show where the user is (active nav, step 2 of 4). |
| H2 | Match the real world | The user's words, not ours: "Table 5", not "Session #a8f2". Things are ordered the way users think (menu categories in meal order). |
| H3 | User control and freedom | Back works. Cancel, close, undo. Modals close with Esc and X. Users can leave a flow without losing data. |
| H4 | Consistency and standards | The same thing looks and behaves the same everywhere. Follow platform conventions (Jakob's law). |
| H5 | Error prevention | Constraints, good defaults, disable impossible options, confirm destructive actions, and format inputs as people type. |
| H6 | Recognition over recall | Show options instead of making users remember them. Keep the cart summary visible and show recent searches. |
| H7 | Flexibility and efficiency | Shortcuts for experts (keyboard, bulk actions, saved filters) that novices never need to see. |
| H8 | Aesthetic and minimalist design | Every element competes for attention. Remove what doesn't serve the page's main task. |
| H9 | Help users recover from errors | Plain-language message, the exact problem, how to fix it, shown next to the problem. Never "Invalid input" or "Error 500". |
| H10 | Help and documentation | Contextual help (tooltips, hint text, empty-state guidance) instead of manuals. |

## B. Laws of UX (the ones that change frontend decisions)

| ID | Law | Rule of thumb |
|---|---|---|
| L-Jakob | Users expect your site to work like the sites they already use | Put things where the big sites put them (see `normal.md`) |
| L-Fitts | Time to hit a target depends on its distance and size | Primary actions big and close to where the thumb or cursor already is; mobile CTAs in the thumb zone (bottom) |
| L-Hick | Decision time grows with the number of choices | One primary action per view; ≤ 7 nav items; progressive disclosure for advanced options |
| L-Miller | ~7±2 items in working memory | Chunk long lists into groups and long forms into sections |
| L-Doherty | Productivity peaks when responses take < 400ms | Optimistic UI, skeletons, prefetch on hover |
| L-AesUse | Attractive designs are *perceived* as easier to use | Polish matters, but it can hide real usability problems, so test tasks, not just looks |
| L-VonRestorff | The item that stands out is remembered | Only the primary CTA gets the accent color |
| L-Proximity / L-CommonRegion / L-Similarity | Grouping comes from closeness, shared containers and shared styling | Spacing and cards create structure; items that look alike must behave alike |
| L-SerialPos | First and last items are remembered best | Key nav items go first and last; important info goes at the start and end of a list |
| L-GoalGradient | Motivation rises near a goal | Progress bars on multi-step flows, "1 step left" |
| L-PeakEnd | Experiences are judged by their peak and their end | Make the success state (order placed, signup done) a satisfying moment |
| L-Tesler | Complexity can only move, not vanish | The system absorbs it: autofill, smart defaults, address lookup |
| L-Postel | Be liberal in what you accept | Accept "0532 123 45 67", "+90 532…" and "5321234567"; trim spaces; case-insensitive codes |
| L-Zeigarnik | Unfinished tasks are remembered | Save drafts and carts; show "continue where you left off" |
| L-ChoiceOverload | Too many options overwhelm people | Curate defaults, show the "most popular" choice, filter instead of scroll |
| L-CognitiveLoad | Mental effort to use the interface | Fewer words, fewer fields, fewer decisions per screen |

## C. Signifiers: users must *see* what is clickable (Norman, NN/g)

- **S1** Buttons look like buttons: rectangle, rounded corners, fill or border. Never style
  non-clickable things (headings, tags, badges) like buttons.
- **S2** Links in text are colored *and* underlined (or clearly distinct). Non-link text never
  uses the link color.
- **S3** Every clickable element has `cursor: pointer`, a hover state (desktop), a pressed state and
  a visible `:focus-visible` ring.
- **S4** A whole card is clickable when it looks like one unit, and the hover state covers the whole card.
- **S5** Unless an icon is universal (search, close, menu, home, cart, settings), it gets a text label.
- **S6** Disabled controls look disabled *and* explain why (tooltip or helper text), or they stay enabled
  and show the error on click.
- **S7** Don't strip every depth cue (flat design). Keep at least one: border, fill or shadow.

## D. Visual integrity: things the user persona flags as "looks broken"

- **V1 Symmetry of equals:** sibling elements with the same role (buttons in a row, cards in a
  grid, nav items) share the same height, padding, alignment and line count. One button wrapping
  to 2 lines while its sibling has 1 is a defect. Fix it with shorter labels, `min-width`,
  `white-space: nowrap` plus a responsive stack, or equal-height grid rows.
- **V2 Alignment:** everything snaps to the grid. Left edges line up across sections. Icons are
  vertically centered with their text.
- **V3 Consistent spacing:** use the spacing scale only, with no magic 13px gaps. Equal things get
  equal gaps.
- **V4 No overflow:** no horizontal page scroll at 360–1440px; long words and URLs break
  (`overflow-wrap: anywhere`); text is never clipped by its container.
- **V5 No overlap:** sticky headers don't cover anchors (`scroll-margin-top`), toasts don't cover
  CTAs, and the cookie banner doesn't cover the checkout button.
- **V6 Images:** fixed aspect ratios (no layout shift) and `object-fit: cover`. No stretched or
  broken images; placeholders are tasteful.
- **V7 States exist:** hover, focus, active, disabled, loading, empty, error and success for every
  component and async view.
- **V8 Consistent casing and punctuation** in buttons and headings. Truncated text gets an ellipsis and
  a tooltip.

## E. Accessibility (WCAG 2.2 AA, the minimum)

- Contrast: 4.5:1 for normal text, 3:1 for large text (≥ 24px, or ≥ 18.66px bold) and 3:1 for UI component
  boundaries and focus indicators.
- Target size: at least 24×24 CSS px (2.5.8 AA). **Our standard is 44×44** for touch.
- Focus is visible and never hidden behind sticky headers, cookie banners or chat widgets (2.4.11
  Focus Not Obscured).
- Every drag interaction has a click or tap alternative (2.5.7 Dragging Movements).
- Full keyboard operation in a logical tab order. Dialogs trap focus and return it to the trigger on close.
- Semantic HTML first (button, a, nav, main, label), ARIA only to fill gaps. `alt` on informative
  images, `alt=""` on decorative ones.
- Don't ask for the same information twice in one flow (3.3.7 Redundant Entry). Authentication without
  cognitive tests where possible (3.3.8): allow paste and password managers.
- `prefers-reduced-motion` respected; nothing flashes more than 3 times a second.
- `lang` attribute; a zoom of 200% still works; the layout reflows at 320px.

## F. Forms and checkout (Baymard 2025)

- **F1** Fewer fields beats fewer steps. Most checkouts need about 8 fields; the average is 11.3. Cut
  everything optional.
- **F2** Guest checkout is the most visible option. Account creation is offered *after*
  purchase.
- **F3** Mark **both** required and optional fields (marking only one led 32% of test users to miss
  a field).
- **F4** Hide rarely used fields ("Company", "Address line 2") behind a link.
- **F5** Error messages are specific and adaptive ("Card number is incomplete", not "Invalid").
- **F6** Explain why sensitive fields are needed (phone: "Only for delivery questions").
- **F7** Card number auto-spaces; expiry format matches the card (MM/YY).
- **F8** Show delivery or arrival *dates or times*, not "2 business days".
- **F9** Quantity steppers (− 1 +), not bare number fields.
- **F10** Simple password rules (min length), show/hide toggle, paste allowed.
- **F11** Inline validation on blur, not on every keystroke. Never clear valid fields.

## G. Content and wordiness

- **W1** People scan, they don't read. Front-load headings and keep paragraphs to 1–3 sentences on
  UI pages.
- **W2** One message per screen. If a section needs a paragraph to explain the UI, the UI is unclear.
- **W3** Button labels say what happens ("Pay ₺240"). Headings say what the page is for.
- **W4** Numbers, prices and dates use the user's locale formatting (`Intl`).
- **W5** Microcopy explains consequences ("You can change this later").
