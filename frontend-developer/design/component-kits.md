# Component kits: shadcn/ui + React Bits

Every frontend this skill builds uses two kits:
- **shadcn/ui** (ui.shadcn.com) for the accessible building blocks: buttons, forms, dialogs, tables,
  sidebars, charts.
- **React Bits** (reactbits.dev) for motion: animated text, WebGL backgrounds, interactive cards,
  galleries, cursors, micro-interactions.

Both copy the source into the project (you own it and can edit it), both style with Tailwind, and both
install with the same `shadcn` CLI.

**How much motion** depends on the segment's style (`DESIGN/styles.md`):

| Style | shadcn/ui | React Bits |
|---|---|---|
| **Fancy** | Base for forms, menus, dialogs | **Lots.** Every section moves. At least 8 React Bits pieces per page (see §4) |
| **Playful** | Base | **Many** micro-interactions and bouncy components (§5) |
| **Normal** | **Everything** | **Light.** Entrances, counters, animated lists; no WebGL (§6) |
| **Strict** | Everything, plus Typography | **None.** At most a subtle FadeContent on the article header |

Verified against the live registries on 2026-10-13: React Bits has 200+ components in five groups (Text
Animations, Animations, Components, Micro Interactions, Backgrounds), and shadcn/ui has 64 components plus
blocks and charts.

## 1. Install

### shadcn/ui
- New project: `npx shadcn@latest init -t next` (templates: `next`, `vite`, `astro`, `react-router`,
  `start`). In an existing React + Tailwind project, use `npx shadcn@latest init` alone.
- Components: `npx shadcn@latest add button card dialog sheet input field select tabs sonner skeleton …`
  Toasts are `sonner`. Three docs entries are **patterns, not installable items**: a data table is `table` +
  `@tanstack/react-table` (follow the docs recipe), a date picker is `popover` + `calendar`, and typography
  is the documented Tailwind classes.
- Blocks: `npx shadcn@latest add dashboard-01 sidebar-07 login-03`. Browse ui.shadcn.com/blocks and pick
  by the segment's needs.
- Charts: `npx shadcn@latest add chart`, then the Recharts examples from ui.shadcn.com/charts.
- Use the package manager whose lockfile is in the repo (`pnpm dlx` / `bunx --bun` / `npx`).

### React Bits
- `npx shadcn@latest add @react-bits/<Name>-TS-TW`, for example `@react-bits/SplitText-TS-TW`. Variants
  are `-TS-TW` (default here), `-TS-CSS`, `-JS-TW` and `-JS-CSS`. Use JS only in a JS-only project.
- If the CLI says the `@react-bits` namespace is unknown, add it to `components.json` and retry:
  ```json
  { "registries": { "@react-bits": "https://reactbits.dev/r/{name}.json" } }
  ```
- Each component's metadata is at `https://reactbits.dev/r/<Name>-TS-TW.json`. Its `dependencies`
  field lists the npm packages it needs (the CLI installs them), and the `files[].content` holds the
  source and props. When you need the props, read the JSON with WebFetch; don't guess them.
- Files land in `components/` (as set in `components.json`), e.g. `components/SplitText.tsx`. Put them
  under `components/motion/` to keep them apart from `components/ui/`.
- **License:** MIT + Commons Clause. You may use them in any product, including commercial ones, but
  you may not resell the components themselves. Mention this in the final report.

### Dependencies they bring (checked)

| Package | Components |
|---|---|
| `gsap` (+ `@gsap/react`) | SplitText, TextType, ScrollFloat, ScrollReveal, AnimatedContent, FadeContent, Masonry, StaggeredMenu, CardNav, PillNav |
| `motion` | BlurText, RotatingText, DecryptedText, CountUp, Counter, TiltedCard, Stack, ScrollVelocity, ElasticSlider, TrueFocus, VariableProximity, SpringCheck, JellyRadio, SquishSwitch, SwipeToast |
| `ogl` | LightRays, SoftAurora |
| `three` | BlobCursor |
| `@use-gesture/react` | DomeGallery |
| `@hugeicons/*` | MagicBento, CardSwap, AnimatedList, Stepper, ProfileCard, PeekRating, PulseHeart, SpringCheck, SwipeToast |
| none (raw WebGL2 or CSS) | Aurora, Silk, LiquidEther, Beams, DarkVeil, Iridescence, Threads, Particles, Galaxy, Plasma, Prism, Grainient, DotGrid, StarBorder, Magnet, ClickSpark, SpecularButton, GlareHover, SpotlightCard, ChromaGrid, CircularGallery, FlyingPosters, InfiniteMenu, LogoLoop, GooeyNav, GlowCursor, LetterGlitch, HoldButton, BounceCards |

- **PillNav** imports `Link` from `react-router-dom`. In Next.js, change it to `next/link` (and in Astro to a
  plain `<a>`) after adding it, and don't install react-router.
- **CardNav** brings `react-icons`. Swap its icons for the project's icon set (Lucide with shadcn).

## 2. Theme both kits from `DESIGN/brand.md`

1. **shadcn variables:** in `globals.css` (`app/globals.css`, `src/index.css`, …), set the `:root` and
   `.dark` values from `brand.md`:

   | shadcn var | brand.md token |
   |---|---|
   | `--background` / `--foreground` | `--bg` / `--text` |
   | `--card`, `--popover` (+ `-foreground`) | `--surface` / `--text` |
   | `--primary` / `--primary-foreground` | `--primary` / text on primary (contrast ≥ 4.5) |
   | `--secondary`, `--muted` / `--muted-foreground` | surface tints / `--text-muted` (≥ 4.5:1) |
   | `--accent` / `--accent-foreground` | `--accent` |
   | `--destructive` | `--danger` |
   | `--border`, `--input` | `--border` |
   | `--ring` | `--focus` |
   | `--radius` | brand radius |
   | `--chart-1…5` | the palette, in order of emphasis |

   Fonts go in `@theme` (`--font-sans`, `--font-display`, `--font-mono`).
2. **React Bits colors come from the tokens, never the demo defaults.** The demos use purple `#5227FF`,
   neon green and white-on-black. Pass the colors through props (`colorStops`, `color`, `glowColor`,
   `spotlightColor`, `color`/`speed` on StarBorder, `colors` on GradientText, etc.), reading the CSS
   variables once with `getComputedStyle(document.documentElement).getPropertyValue('--primary')` or
   from a `tokens.ts` that mirrors `brand.md`. A first-time user who sees a stock purple aurora on an
   orange brand will (rightly) call it a template.
3. Restyle copied components with the project's classes where they hard-code `bg-black`, `text-white` or
   their own fonts.

## 3. Rules for "lots of animation" (all styles)

The non-negotiables in `fancy.md` apply here too. On top of them:

1. **Reduced motion everywhere.** Some components check it themselves (Aurora, Silk, MagicBento,
   ShinyText, GradientText, the WebGL backgrounds, Stack and the motion micro-interactions); many don't
   (SplitText, BlurText, TextType, RotatingText, DecryptedText, ScrollFloat, ScrollReveal, CountUp,
   AnimatedContent, FadeContent, TiltedCard, ScrollVelocity, CurvedLoop, GlitchText, FuzzyText…). Create
   **one** wrapper, `components/motion/Motion.tsx`, with `useReducedMotion()` (from `motion/react`, or
   `matchMedia`). When the user prefers reduced motion it renders the **final state** (plain text,
   visible content, a static gradient instead of a canvas). Use the wrapper or the hook for every
   component that doesn't handle it.
2. **Nothing stays invisible.** Entrance components start at opacity 0. Their trigger
   (IntersectionObserver or ScrollTrigger) must fire on every screen size, including a short page where the
   section never scrolls. Use a small `rootMargin`/`threshold`, and add a no-JS fallback where possible.
   `ui_audit.py` reports leftovers as `stuck-invisible`.
3. **The hero is fast.** The `<h1>` text is in the server HTML (SplitText and BlurText render real text). It
   is fully visible within 600 ms, so keep stagger × characters short or split by words. LCP must not
   wait for WebGL. Mount backgrounds after first paint.
4. **One WebGL canvas in view at a time.** Backgrounds, CircularGallery, InfiniteMenu, DomeGallery and
   BlobCursor all use the GPU. Load them lazily:
   - Next.js: `const Aurora = dynamic(() => import('@/components/motion/Aurora'), { ssr: false })`
   - Astro: `client:visible`

   They pause off screen; Aurora does so itself, and the others should be unmounted or paused with an
   IntersectionObserver.
5. **Mobile (< 768px):**
   - Swap WebGL backgrounds for a static CSS gradient made from the same tokens.
   - Turn off cursor effects (TargetCursor, BlobCursor, GlowCursor, SplashCursor, Magnet) and
     hover-only effects (or give them tap equivalents).
   - Pass `disableAnimations` (MagicBento) or the equivalent props.
   - Check with `matchMedia('(pointer: coarse)')` or `(max-width: 767px)`.
6. **One scroll owner.** Use either native scrolling or Lenis, never two smooth-scroll systems. GSAP
   ScrollTrigger works with both; call `ScrollTrigger.refresh()` after fonts and images load.
7. **Next.js:** React Bits components use hooks and browser APIs. Keep `'use client'` at the top of
   each component file and import them from Server Components. Never make a whole page a client
   component just for one animation.
8. **Accessibility:**
   - Animated text keeps an accessible name (`aria-label` on the wrapper when it splits into spans).
   - Decorative canvases get `aria-hidden="true"`.
   - Anything clickable is still a `<button>` or `<a>`.
   - Interactive 3D (DomeGallery, InfiniteMenu) gets a plain list alternative for keyboard users.
9. **Budget per page:** at most ~250 KB of extra JS for motion on a Fancy page, and none on Strict.
   Prefer CSS and zero-dependency components when two do the same job.

## 4. Fancy recipes (lots of motion)

A Fancy page should feel alive from the first frame to the footer. **Minimum:** an animated headline, a
background, a CTA micro-interaction, an entrance on *every* section, and at least 4 more pieces from the
table, so 8 or more in all. Pick by the brand mood, not at random, and never use two components of the same
kind in one viewport (two backgrounds, two cursors).

| Pattern (see `fancy.md`) | React Bits (pick one per slot) | Notes |
|---|---|---|
| Hero headline | **SplitText**, **BlurText**, TextType (typed loop), RotatingText (rotating keyword), ShinyText, GradientText, DecryptedText, TrueFocus, VariableProximity | One per hero; ShinyText/GradientText for a single accent word inside a SplitText line |
| Hero background | **Aurora**, **Silk**, LiquidEther (fluid, reacts to cursor), Beams, LightRays, DarkVeil, Iridescence, Threads, Particles, Galaxy, Plasma, Prism, Grainient, SoftAurora, DotGrid | Map the mood: calm/luxury → Silk, DarkVeil, Grainient · tech → Beams, Threads, Particles, DotGrid · energetic → LiquidEther, Plasma, Prism · dreamy → Aurora, Iridescence, SoftAurora · space/AI → Galaxy, LightRays |
| Primary CTA | **StarBorder**, Magnet, ClickSpark (wrap the page or the CTA), SpecularButton, GlareHover | Keep the shadcn `<Button>` inside for semantics and focus styles |
| Section entrance (every section) | **AnimatedContent**, **FadeContent**, ScrollReveal (paragraph word-by-word), ScrollFloat (section titles), GradualBlur (edge blur) | Stagger children 60–100 ms; distance 40–100 px |
| Features | **MagicBento**, SpotlightCard, TiltedCard, BorderGlow, ChromaGrid, GlassSurface | MagicBento for the bento-grid pattern; SpotlightCard for a 3-up grid |
| Showcase / gallery | CircularGallery, DomeGallery, Masonry, FlyingPosters, InfiniteMenu | Real project images; one per page; keyboard alternative |
| Logos / social proof marquee | **LogoLoop**, ScrollVelocity (big text band), CurvedLoop | Pause on hover; `prefers-reduced-motion` → static row |
| Stats | **CountUp** | Real numbers only, or `{{PLACEHOLDER}}` |
| Testimonials / steps | CardSwap, Stack, ScrollStack | Only real testimonials; never invent them |
| Navigation | PillNav, CardNav, StaggeredMenu (mobile overlay), GooeyNav, Dock (app-like) | Fix the router import (§1) |
| Cursor (desktop only) | TargetCursor, BlobCursor, GlowCursor | Off on touch and with reduced motion; never hide the cursor on inputs |
| 404 / error | FuzzyText, GlitchText, LetterGlitch | Keep a clear "Back home" button |

Example Fancy landing page, 10 pieces:
1. ClickSpark wrapping `<main>`
2. PillNav
3. Silk background
4. SplitText `<h1>` with a ShinyText keyword
5. StarBorder CTA
6. LogoLoop of partners
7. MagicBento features
8. ScrollReveal manifesto paragraph
9. CountUp stats
10. CardSwap testimonials

AnimatedContent on each section; FuzzyText 404.

## 5. Playful recipes (many micro-interactions)

| Pattern | Components |
|---|---|
| Form controls | SpringCheck (checkbox), JellyRadio, SquishSwitch, ElasticSlider, PeekRating (ratings) |
| Feedback | SwipeToast (toasts), PulseHeart (like/favourite), ClickSpark (celebration on success), HoldButton (confirm by holding) |
| Lists and cards | BounceCards, Stack (swipeable cards), AnimatedList (feeds/notifications) |
| Text | RotatingText, TextType, GradientText for one highlight |
| Stats and progress | CountUp, Counter, Stepper (onboarding) |
| Background (marketing pages only) | DotGrid, Particles or Grainient, in brand colors and low intensity |

They sit on top of the shadcn primitives: keep the label, error and focus behaviour of `Field`.

## 6. Normal recipes (shadcn first, light motion)

| Need | shadcn/ui |
|---|---|
| App shell | `sidebar` (+ a `sidebar-0x` block), `breadcrumb`, `navigation-menu`, `dropdown-menu`, `avatar` |
| Dashboard | `dashboard-01` block, `card`, `chart`, `table` + TanStack Table (the data-table recipe), `tabs`, `badge`, `progress` |
| Forms | `field`, `input`, `input-group`, `textarea`, `select`/`native-select`, `combobox`, `checkbox`, `radio-group`, `switch`, `popover` + `calendar` (date picker), `input-otp`, `slider` |
| Overlays | `dialog`, `alert-dialog` (destructive confirm), `sheet` (mobile filters, item details), `drawer`, `popover`, `hover-card`, `tooltip` |
| Feedback | `sonner` (toasts), `alert`, `skeleton`, `spinner`, `empty`, `progress` |
| Search | `command` (⌘K palette), `input-group` with a search icon |
| Auth | `login-0x` / `signup-0x` blocks |

Light React Bits only:
- AnimatedContent or FadeContent for page and section entrances (short: 0.4–0.6 s, distance ≤ 30 px)
- CountUp on KPI cards
- AnimatedList for activity feeds
- Stepper for multi-step flows
- ClickSpark at most on one success moment

No WebGL backgrounds, cursors or scroll-jacking.

## 7. Strict

Use the shadcn typography classes from the docs (or `@tailwindcss/typography` `prose`, themed with the tokens), `table`,
`accordion` (FAQ), `breadcrumb`, `separator`, `scroll-area` (code), `alert` (callouts) and `tabs` (code
samples). No React Bits, except an optional FadeContent (≤ 0.3 s) on the article header.

## 8. Non-React projects (existing code only; never migrate)

| Stack | Components | Motion |
|---|---|---|
| Vue / Nuxt | shadcn-vue (shadcn-vue.com) | Vue Bits (vue-bits.dev), the official Vue port of React Bits, with the same recipes |
| Svelte / SvelteKit | shadcn-svelte (shadcn-svelte.com) | Rebuild the recipe effects with GSAP, `motion` or Svelte transitions; for WebGL backgrounds, port the shader from the React Bits registry JSON (`files[].content`) into a Svelte component |
| Plain HTML | none | GSAP + ScrollTrigger and CSS, following the same recipe slots |
