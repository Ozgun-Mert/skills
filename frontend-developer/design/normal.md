# Normal (mainstream, familiar, gets-out-of-the-way)

Use for segments the user marked **Normal**. Typical segments: app panels and dashboards, lists and
catalogs, detail pages, search, cart and checkout, forms, settings, account, admin.

These are **general rules, not a spec**. The skill polishes them for each project in Phase 2: it
researches similar sites and writes `DESIGN/normal-polished.md`. Where the two disagree, the
project file wins.

Sources: the most-visited websites (Similarweb/Semrush 2026: Google, YouTube, Facebook,
Instagram, ChatGPT, X, Reddit, WhatsApp, Bing, TikTok, Wikipedia, Amazon, Yahoo, Temu) and the
design systems behind big products (Material 3, Apple HIG, Shopify Polaris, IBM Carbon,
Atlassian). See `sources.md`.

## Why "normal" works: Jakob's Law

People spend most of their time on *other* sites, so they arrive expecting those sites'
conventions. The most-visited sites have trained billions of people on the same patterns. Reusing
those patterns costs the user nothing to learn. Innovate in the product, not in where the search
box is.

## Conventions users already know (use them)

| Convention | Learned from | Rule |
|---|---|---|
| Logo top-left → home | everyone | Clickable, goes home |
| Primary nav top (desktop) / bottom tab bar or hamburger (mobile) | Instagram, YouTube, X, TikTok | ≤ 5 bottom tabs, icon + label |
| Search box prominent at top, with suggestions | Google, Amazon, YouTube | Autocomplete, recent searches, tolerant of typos |
| Account/avatar top-right | Google, YouTube, Amazon | Menu with profile, settings, sign out |
| Cart icon top-right with count badge | Amazon, Temu | Always visible on commerce sites |
| Feed of cards, infinite scroll or "load more" | Facebook, Reddit, Instagram | Keep scroll position on back |
| Left sidebar for sections in apps | YouTube, ChatGPT, Gmail | Collapsible; current item highlighted |
| Composer / input pinned at bottom | ChatGPT, WhatsApp | Enter to send, Shift+Enter newline |
| Breadcrumbs on deep hierarchies | Amazon, Wikipedia | Not needed on flat sites |
| Footer with legal, help, contact, language | everyone | Plain links, not decorative |
| Blue (or brand) underlined links in text | Wikipedia, Google | Text links look like links |

## Visual language

- **Neutral surfaces + one brand color.** Mostly white or very light gray (dark mode: #121212–#1E1E1E,
  never pure black for app surfaces). Brand color goes on primary actions, active states and links.
  Use semantic colors only for meaning: success green, warning amber, error red, info blue.
- **Type:** one sans family is enough. Use system UI, Inter, Roboto or a similar workhorse, or the
  project's brand font if it is legible at small sizes.
  - Body 16px (never < 14px for UI text, 16px on inputs to prevent iOS zoom), line height 1.4–1.6.
  - Scale 1.2–1.25 (14 / 16 / 20 / 24 / 30 / 36).
  - Weights 400 / 500 / 600; avoid 300 at small sizes.
- **Spacing:** a 4/8px grid (4, 8, 12, 16, 24, 32, 48, 64). Related things sit closer than
  unrelated things (proximity).
- **Radius:** pick one family and keep it: 4–8px (serious, enterprise) or 12–16px (consumer,
  friendly). Buttons, inputs and cards all share it.
- **Elevation:** flat surfaces with 1px borders or very soft shadows. Shadows signal layers
  (menus, dialogs), not decoration.
- **Icons:** one set (Lucide, Material Symbols, Phosphor, Heroicons), one stroke weight, with a label unless the
  meaning is universal (search, close, menu, cart, home, settings).
- **Density:** comfortable by default. Offer a compact table density for power users when the
  product has data tables.
- **Dark mode** follows `prefers-color-scheme` and offers a toggle when the product is used for a
  long time each day.

## Components behave the way people expect

- **Buttons:**
  - one primary per view (filled), secondary (outline/tonal), tertiary (text)
  - min height 40px desktop, 44px touch
  - labels are verbs ("Save changes", "Add to cart"), never "Submit" or "OK" alone
  - Equal-role buttons in a row have equal height and never wrap to two lines. Shorten the label
    or stack the buttons.
- **Inputs:** a label above every field (placeholders are not labels), helper text below, errors
  inline under the field in red with an icon and a fix suggestion. Use the right keyboard
  (`type=email`, `inputmode=numeric`) and `autocomplete` attributes.
- **Tables:** sticky header, right-aligned numbers, sortable columns with an indicator. Row
  actions go in a kebab menu or appear on hover. On mobile, rows become cards.
- **Dialogs:** for confirmations and short focused tasks only. Close with X, Esc and a click
  outside (unless there are unsaved data). Never stack dialogs.
- **Toasts:** brief success or info, auto-dismiss in 4–6 s, with an "Undo" for destructive actions.
  Errors that need action stay on screen, so they are not toasts.
- **Empty states:** explain what will appear here, plus one CTA to create the first item.
- **Loading:** skeletons shaped like the content for page loads; a spinner inside the
  button for actions; optimistic updates for likes and toggles.
- **Pagination vs infinite scroll:** use infinite scroll for feeds and pagination or "load more" for search results
  and anything users compare or come back to. Restore the scroll position on back navigation.

## Interaction and feedback

- Every clickable element has `cursor: pointer`, hover and active states, and a focus ring.
- Respond within 100ms (state change) and show progress for anything over 1 s (Doherty threshold).
- Destructive actions need either a confirm dialog that names the object ("Delete 'Menu A'?") or
  an undo toast. Prefer undo.
- Keep user input on error. Never clear a form because the server rejected one field.
- Remember filters, sort order and tab choices within the session.

## Responsive

- Design mobile-first from 360px. Breakpoints are roughly 640 / 768 / 1024 / 1280.
- Content max width 1200–1440px for apps; 65–75ch for reading text.
- Touch targets ≥ 44×44px with ≥ 8px spacing.
- No horizontal page scroll, ever. Wide tables scroll inside their own container.

## Components

Build Normal segments from **shadcn/ui** (sidebar, data table, field, dialog, sheet, command, sonner,
skeleton, empty, plus blocks such as `dashboard-01` and `login-0x`), themed from the brand tokens. Motion
stays light: short AnimatedContent/FadeContent entrances, CountUp on KPIs, AnimatedList for feeds, Stepper
for multi-step flows. No WebGL backgrounds, cursors or scroll effects. See `component-kits.md` §6.

## Content tone

Use plain, short and specific language in the user's terms (see `ux-principles.md`). Headings tell
the user what they can do or what they'll find. Avoid marketing language inside the app.
