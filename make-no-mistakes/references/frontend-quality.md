# Frontend quality: polish and SEO

Paste the relevant parts of this into `frontendprompt.md` and `integrationprompt.md`, adapted to
the chosen framework.

## 1. UI style → design tokens

The interview's style answer chooses the column. Put the resulting tokens in `mnm/spec.md`. The
frontend implements them as CSS variables, which Tailwind v4 reads through `@theme`.

| Token | Professional | Balanced | Fun |
|---|---|---|---|
| Palette | Neutral grays + 1 restrained brand color (blue/teal/indigo), low saturation | Brand color + 1 accent, medium saturation | 2–3 bold saturated colors, playful accent, gradients allowed |
| Type | Inter / system sans; scale 1.2; weights 400/500/600 | Inter or Plus Jakarta Sans; scale 1.25 | Rounded display font (Nunito, Fredoka, Baloo) for headings + readable sans body; scale 1.333 |
| Radius | 6px | 10px | 16–24px, pill buttons |
| Shadow | Subtle, 1 level | 2 levels | Soft colorful shadows or offset "sticker" shadows |
| Density | Compact tables, 8px grid | Comfortable | Spacious, large touch targets |
| Motion | 150ms ease fades only | 200ms transitions, small hover lifts | Springy micro-interactions, celebratory moments (confetti on achievements), all behind `prefers-reduced-motion` |
| Imagery | Product screenshots, simple line icons (Lucide) | Icons + light illustrations | Illustrations/mascot, emoji accents |
| Copy tone | Precise, formal | Friendly, plain | Playful, encouraging |

The brand color comes from the user if given. Otherwise pick one that fits the domain and passes
contrast. Define light and dark themes, and make dark mode follow `prefers-color-scheme`.

## 2. Polish checklist (acceptance rows for frontend pieces)

- A consistent component set (button, input, select, card, dialog, toast, table, empty state,
  skeleton) built once from the tokens and reused everywhere.
- **Every async view has four states:** loading (skeleton), empty (helpful message + CTA), error
  (human message + retry), success.
- Forms:
  - labels, inline validation messages, a disabled + spinner submit while pending
  - server errors mapped to fields
  - no lost input on error
- Mobile-first layout from 360px up. No horizontal scroll at 360/390/768/1280. Touch targets
  ≥ 44px. Working mobile navigation.
- Accessibility (WCAG 2.2 AA):
  - semantic HTML, one `<h1>` per page, logical heading order
  - visible focus rings, full keyboard navigation
  - dialogs trap focus and close on Esc
  - `alt` on content images, `aria-label` on icon buttons
  - contrast ≥ 4.5:1 for body text and ≥ 3:1 for large text
- Feedback: optimistic updates where safe, toasts for background results, confirmation before
  destructive actions.
- Performance: images through the framework's image component (`next/image` or
  `@sveltejs/enhanced-img`) with width/height. Fonts self-hosted with `font-display: swap`. No
  layout shift. Route-level code splitting. Third-party scripts deferred.
- No placeholder lorem ipsum in finished pages. Missing facts use `{{PLACEHOLDER: name}}` (visible,
  trackable).

## 3. SEO checklist (public pages)

**Rendering**
- Public pages are server-rendered or prerendered. Their content is in the raw HTML, not fetched
  client-side.
- Navigation uses real `<a href>` links (`<Link>` in Next.js). Never `onClick` + router push for
  navigation.
- Next.js: pages and layouts are Server Components; `'use client'` only on interactive leaves.
  SvelteKit: `export const prerender = true` on marketing pages; data loads in `+page.server.ts`.

**Per page**
- A unique `<title>` (~50–60 chars) and meta description (~140–160 chars) with the page's primary
  keyword, phrased naturally.
- Exactly one `<h1>` stating the topic. H2/H3 in a logical outline.
- A self-referencing canonical URL (absolute, from a `SITE_URL` env/constant).
- Open Graph + Twitter card tags, with an OG image (static per page type, or generated).
- `<html lang>` set to the content language. `hreflang` alternates when multilingual.
- Lowercase hyphenated URLs. One URL per piece of content. A consistent trailing-slash policy.

**Site-wide**
- `robots.txt`: allows public pages, disallows app/private/utility routes (`/app`, `/api`,
  `/settings`), never blocks CSS/JS, and has a `Sitemap:` line. Next.js: `app/robots.ts`.
  SvelteKit: `src/routes/robots.txt/+server.ts`.
- `sitemap.xml`: indexable public pages only, absolute canonical `loc`, real `lastmod`. Next.js:
  `app/sitemap.ts`. SvelteKit: `src/routes/sitemap.xml/+server.ts`.
- Logged-in app pages: `noindex`.
- JSON-LD, truthful only:
  - `Organization` (or `Person`) and `WebSite` on the home page
  - `SoftwareApplication`/`Product` for the product
  - `BreadcrumbList` on nested pages
  - `FAQPage` only when the page shows the FAQ
  - `BlogPosting` with a real author
  - never invented ratings or reviews
- Internal links: every public page is reachable through real links within 3 clicks of home. Nav,
  footer and breadcrumbs.
- Trust pages when the product has accounts: About, Contact, Privacy, Terms (+ Cookies if tracking,
  + KVKK/GDPR when the interview said so). Legal text is a starting draft with a visible banner:
  "AI-generated draft, have it reviewed by a lawyer". Company facts are placeholders.
- A custom 404 page that returns HTTP 404, never a soft 404.

**Content**
- The landing page has one main promise plus links to feature/use-case pages. Don't keyword-stuff.
- Each public page's search intent comes from the spec's page list. Write for people first.

## 4. Verification commands (integration/QA pieces)

- Build and serve production: `bun run build && bun run preview` (SvelteKit) or
  `bun run build && bun run start` (Next.js).
- Raw-HTML crawl: `python "<SKILL_DIR>/scripts/seo_check.py" http://localhost:<port> --sitemap`.
  Must print `0 critical, 0 high`.
- Playwright: screenshots at 360/390/768/1280 for each public page and each main app page; an
  assertion that there's no horizontal overflow (`document.documentElement.scrollWidth <= innerWidth`).
- Optional: `npx @axe-core/cli` on main pages, 0 serious/critical violations.
