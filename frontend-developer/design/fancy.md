# Fancy (premium / award-level)

Use for segments the user marked **Fancy**. Typical segments: landing and hero, brand story,
product showcase, portfolio, launch or campaign pages, luxury and real estate, agency sites.
Researched from Awwwards Sites of the Year, Sites of the Month and Sites of the Day (2017 to Oct 2026).
`sources.md` lists the sites. These are patterns to reuse, not sites to copy. Pick the 3–5 that fit
the project, never all of them.

**What the winners have in common:** one bold idea, executed with craft. They have a restrained
palette, big confident type and motion that tells a story. Their weakest Awwwards scores are almost
always **Accessibility** (6.6–7.2) and **Semantics/SEO**. We keep the wow factor and fix those
two weaknesses (see "Non-negotiables").

## 1. Color: two colors, one of them loud

Nearly every winner lists a **2-color palette**: one near-black or near-white base plus one
saturated signature color.

| Site | Base | Signature |
|---|---|---|
| Lando Norris (SOTY 2025) | #111112 | #D2FF00 acid lime |
| Heron AI | #282828 | #F15534 orange-red |
| Why Zero | #FFFFFF | #01C654 green |
| Floema | #241F21 | #E9E778 pale yellow |
| Dropbox Brand | #1A1918 | #0061FE blue |
| Lama Lama | #1A1C1C | #F9F4EB warm off-white |
| Odyssée (clinic, luxury) | #F6F4F2 | #1E305E navy |
| Montfort (finance) | #F4F6F8 | #29648E steel blue |
| Igloo Inc | #383E4E | #B6BAC5 |

Rules:
- Use **warm off-whites** (#F6F4F2, #F9F4EB) and **soft blacks** (#111112, #1A1918), never pure
  #000 on #FFF. Pure values look cheap and glare.
- Use the signature color sparingly: CTAs, one hero word, hover states, the cursor, section
  dividers. If it covers more than ~10% of the screen it stops being special.
- Luxury, health and finance use dark navy or steel blue on off-white with no neon. Sports,
  tech, startups and youth use neon (lime, orange-red, electric blue) on near-black.
- Images supply the rest of the color: full-bleed photography and video, often graded toward the
  palette.

## 2. Typography: the type *is* the layout

Fonts seen on the winners, read from their font files:
- Swiss/neo-grotesk sans: Suisse Int'l (Terminal Industries, Lama Lama), GT Standard (twks), ABC Diatype and Die Grotesk (Butter), Zimula (Floema)
- custom display faces: Brier (Lando Norris), Dropbox Sharp Grotesk
- a **mono accent** for labels and metadata: Geist Mono, Sometype Mono

Patterns:
- **Oversized display headlines**: 10–20vw on hero, `clamp()`-based, tight leading (0.85–1.0),
  negative tracking (−0.02 to −0.05em). A single word or short phrase can fill the viewport.
- **Grotesk + mono** is the dominant pairing: the mono goes in small uppercase labels, indices
  ("01 / 05"), metadata and buttons. **Serif display + grotesk body** is the luxury and editorial variant.
- Variable fonts, animated through weight or width on scroll and hover.
- **Kinetic type**: lines or characters reveal on scroll (SplitText-style masks rising from a
  clip), marquee bands of huge text, and text that reacts to the cursor.
- Body copy stays boring and readable: 16–18px, 1.5 line height, 60–75ch measure.

Premium fonts cost money. Use free alternatives with the same feel, and choose a **different** one
from the competitors (see `brand.md` in the project):

| Feel | Paid original | Free alternatives (Google Fonts / Fontshare) |
|---|---|---|
| Swiss neo-grotesk | Suisse Int'l, GT America, Diatype | Inter Tight, Geist, Switzer, General Sans, Hanken Grotesk |
| Characterful grotesk | GT Walsheim, Druk | Satoshi, Cabinet Grotesk, Clash Grotesk, Bricolage Grotesque |
| Condensed / poster | Druk Wide, Brier | Anton, Big Shoulders Display, Oswald, Clash Display, Unbounded |
| Luxury serif display | GT Super, Canela, Ogg | Instrument Serif, Fraunces, Playfair Display, Gambetta, Erode |
| Mono accent | GT America Mono, Suisse Mono | Geist Mono, JetBrains Mono, IBM Plex Mono, Space Mono |

## 3. Layout and composition

- **Scroll-driven storytelling**: a single long page in chapters, each with one idea, revealed by
  scrolling. Common elements are pinned sections, horizontal-scroll strips inside vertical scroll, and
  scroll-scrubbed video or image sequences.
- **Asymmetric 12-column grid** with generous negative space. Content sits off-center and big
  elements bleed off the edges, but the grid underneath stays strict, so it reads as intentional.
- **Full-bleed media**: hero video or image, edge-to-edge galleries, scroll-zoom on images
  (e.g. Floema's "scroll video zooming").
- **Bento grids** for features: modular cards of different sizes on one grid. This is the Apple
  pattern, now common on SaaS sites.
- **Sticky mini-UI**: a small fixed nav or logo, a section index ("02 — Services") and a scroll
  progress line.
- **Marquees**: infinite horizontal bands of text or logos between sections.
- Custom 404, preloader and footer are treated as design moments. Awwwards juries reward them.

## 4. Motion

The stack seen on the winners: GSAP + ScrollTrigger + SplitText, Lenis smooth scroll, Barba
page transitions, Three.js/OGL WebGL. Webflow, Nuxt, Next and Astro all appear.

- **Smooth inertial scroll** (Lenis). Keep native scrollbars and keyboard scrolling working.
- **Reveal on enter**: text lines mask-up, images clip-path/scale from 1.1→1, stagger 40–80ms.
  Easing `cubic-bezier(.16,1,.3,1)` / expo-out, 600–1200ms for large moves, 150–250ms for UI.
- **Page transitions**: curtain wipes, shared-element morphs or the View Transitions API.
- **Preloader**: a logo or counter animation that **covers real asset loading** and lasts under 2 s.
  Skip it on repeat visits.
- **Hover**: magnetic buttons, image reveal on link hover, underline draw, cursor-follow labels.
- **Custom cursor**: a dot or ring that grows on interactive elements and shows contextual labels
  ("View", "Drag"). Never hide the system cursor on form fields or text, and keep
  `cursor:pointer` semantics.
- **3D/WebGL**: one hero object or scene that reacts to the mouse and scroll (Igloo, Lando
  Norris, Montfort). Give it a static fallback image, and lazy-init it after first paint.
- **Microinteractions and sound** (rare): opt-in sound toggle; hold-to-proceed interactions only as
  extras.

## 5. Imagery

- Art-directed photography and video in a consistent grade. Grain or noise overlays, duotone.
- 3D renders (Blender, Spline) for tech products, and macro product shots.
- Icons are rare. When they appear they are custom and thin-stroke.

## Non-negotiables (the "fancy but usable" contract)

Award sites lose points on these. We don't.
1. `prefers-reduced-motion: reduce` turns off smooth scroll, parallax, scrubbing, marquees and
   WebGL motion. Content stays reachable and readable.
2. Content is real HTML: one `<h1>`, semantic sections and text that isn't baked into canvas. SEO
   and screen readers depend on it.
3. Contrast ≥ 4.5:1 on body text over images (use scrims). Visible focus rings that match the brand.
4. A preloader must never block content for more than 2 s. LCP < 2.5 s on 4G mid-range mobile. Lazy-load
   WebGL and video, and use `poster` images.
5. **Mobile is designed, not shrunk**: big type scales down with `clamp()`, horizontal sections
   become vertical, hover effects get tap equivalents, and the custom cursor is disabled on touch.
6. Navigation is always one tap away. A fancy menu overlay is fine, but a hidden nav with no label is not.
7. Fancy is for *showing*. Forms, checkout, settings and dashboards inside a fancy site use the
   **normal** rules, styled with the fancy tokens (palette and type).
