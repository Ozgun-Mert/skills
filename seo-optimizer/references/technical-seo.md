# Technical SEO recipes

Contents: 1 Rendering rules · 2 Next.js App Router · 3 Next.js Pages Router · 4 Astro · 5 Nuxt ·
6 SvelteKit / Remix · 7 Vite/CRA SPA · 8 Plain HTML · 9 robots.txt · 10 sitemap.xml · 11 hreflang ·
12 JSON-LD · 13 Slugs & transliteration · 14 Duplicates & canonicals · 15 Blank project scaffold

Follow the framework's own conventions. Don't add a dependency (e.g. `next-sitemap`,
`@nuxtjs/sitemap`, `react-helmet-async`) without asking: a dependency is a change to the project
too. Prefer built-in features.

## 1. Rendering rules (all frameworks)

Googlebot renders JS, but later and less reliably than it reads HTML, and other search engines and
link previews often don't render JS at all. So everything that matters must be in the first HTML
response.

- **Links:** `<a href="/pricing">` or the framework's link component (`<Link href>`, `<NuxtLink to>`).
  Never use `<div|span|button onClick={() => router.push(...)}>` or `window.location = ...` for
  navigation, because crawlers don't click. Buttons that *do* something (open a modal, submit) stay
  buttons.
- **Static content in HTML:** copy, headings, FAQ answers and pricing tables are rendered on the
  server or at build time, not fetched in `useEffect`.
- **Accordions and tabs:** content inside them must already be in the DOM (hidden with CSS or
  `<details>`), not injected when clicked.
- **Next.js:** pages and layouts are Server Components. Move interactivity into small `'use client'`
  leaf components (`<MobileMenuButton/>`, `<PricingToggle/>`) and pass server-rendered content as
  `children`.
- **Images:** set `width`/`height` (or aspect-ratio) to avoid layout shift. The LCP image (usually
  the hero) gets `priority` / `fetchpriority="high"` and no lazy-loading. Images below the fold get
  `loading="lazy"`.
- **Fonts:** `font-display: swap` or `next/font`. Preload at most 1–2 font files.

## 2. Next.js App Router

```tsx
// app/layout.tsx (server component)
import type { Metadata } from 'next'
export const metadata: Metadata = {
  metadataBase: new URL('https://example.com'),        // or '{{PLACEHOLDER: site_url}}' via env
  title: { default: 'Brand: one-line value', template: '%s | Brand' },
  description: '…',
  openGraph: { siteName: 'Brand', locale: 'tr_TR', type: 'website' },
  twitter: { card: 'summary_large_image' },
}
export default function RootLayout({ children }) {
  return <html lang="tr"><body>{children}</body></html>
}
```

```tsx
// app/qr-menu/page.tsx
export const metadata: Metadata = {
  title: 'QR Menü: Restoranlar İçin Dijital Menü',   // template adds " | Brand"
  description: '…',
  alternates: { canonical: '/qr-menu' },
  openGraph: { title: '…', description: '…', url: '/qr-menu', images: ['/og/qr-menu.png'] },
}
```

Dynamic routes use `export async function generateMetadata({ params })` and
`generateStaticParams()`.

```ts
// app/robots.ts
import type { MetadataRoute } from 'next'
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/', disallow: ['/dashboard/', '/api/'] }],
    sitemap: 'https://example.com/sitemap.xml',
  }
}
```

```ts
// app/sitemap.ts: lastmod = when that page's content last changed, not new Date() for all
import type { MetadataRoute } from 'next'
const base = 'https://example.com'
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${base}/`, lastModified: '2026-10-04', changeFrequency: 'monthly', priority: 1 },
    { url: `${base}/qr-menu`, lastModified: '2026-10-04', priority: 0.9 },
    // blog posts: map over the posts' frontmatter dates
  ]
}
```

Also: `app/not-found.tsx` (returns a real 404), `app/opengraph-image.*` if there is no OG image. Use
`next/link` and `next/image` (with `alt`). JSON-LD goes in a server component:
`<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />`.
Delete any public `robots.txt` or `sitemap.xml` that duplicates `app/robots.ts` or `app/sitemap.ts`,
because both would conflict (ask first).

## 3. Next.js Pages Router

`next/head` per page for title, meta, canonical and OG. Pre-render with `getStaticProps`. Use
`public/robots.txt` and either a static `public/sitemap.xml` or `pages/sitemap.xml.ts` that writes
XML in `getServerSideProps`. Custom `pages/404.tsx`. Set `lang` in `pages/_document.tsx`
(`<Html lang="tr">`) or via `i18n` in `next.config` (ask before editing config).

## 4. Astro

Static by default, which is great for SEO. Use a shared `<BaseHead>` component with title, description,
canonical (`new URL(Astro.url.pathname, Astro.site)`) and OG. Set `site` in `astro.config.*` (ask).
`@astrojs/sitemap` is the standard (ask before adding), or write `src/pages/sitemap.xml.ts`. Put
`public/robots.txt`. Islands (`client:*`) only for interactive bits.

## 5. Nuxt

`useSeoMeta({ title, description, ogTitle, … })` and `useHead({ link: [{ rel: 'canonical', href }] })`
per page. Set `app.head.htmlAttrs.lang` in `nuxt.config` (ask). Use `ssr: true` (default) or
`nuxi generate`. Sitemap via `@nuxtjs/sitemap` (ask) or a server route. Robots in `public/robots.txt`.
Use `<NuxtLink to>`.

## 6. SvelteKit / Remix

**SvelteKit:** `<svelte:head>` per page, `export const prerender = true` for static pages,
`src/routes/sitemap.xml/+server.ts`, `static/robots.txt`, `<html lang>` in `src/app.html`.
**Remix / React Router v7:** `export const meta` per route, a `sitemap[.]xml.tsx` resource route,
`public/robots.txt`.

## 7. Vite / CRA single-page app (client-only)

The first HTML is an empty `<div id="root">`. Every route shares one title. Crawlers may index a
blank shell. **Explain this to the user and propose options. Don't migrate on your own:**
1. **Prerender at build** (`vite-plugin-prerender`, `vite-ssg` for Vue, `react-snap` for CRA):
   the smallest change that gives real HTML per route.
2. **Move marketing pages to SSG** (Astro or Next.js) and keep the app as a SPA under `/app`.
3. **Full SSR framework migration**: the largest effort, the best result.

Whatever the user chooses, you can still do these after approval: convert `onClick` navigation to
`<Link to>` / `<a href>`, per-route titles and meta (`react-helmet-async` only if approved, or
`document.title` as a weak stopgap), `public/robots.txt`, `public/sitemap.xml`, alt text, and SPA
fallback awareness (unknown routes return 200 with the shell, which is a soft 404: report it).

## 8. Plain HTML

Edit `<head>` per file: `<title>`, `<meta name="description">`, `<link rel="canonical">`, OG tags,
`<html lang>`, `<meta name="viewport" content="width=device-width, initial-scale=1">`. Put
`robots.txt` and `sitemap.xml` at the web root. Use folder-style clean URLs (`/hakkimda/index.html`
→ `/hakkimda/`) only if the host serves them. Don't rename existing URLs without asking, because
renamed URLs need redirects (server config).

## 9. robots.txt

```
User-agent: *
Allow: /
Disallow: /dashboard/
Disallow: /api/
Disallow: /*?*sort=

Sitemap: https://example.com/sitemap.xml
```

Disallow only private or utility areas (account, admin, cart, internal search, faceted parameters).
Never block `/_next/`, `/assets/`, `*.css` or `*.js`, because Google needs them to render. robots.txt
controls crawling, not indexing: to keep a page out of results, use `<meta name="robots"
content="noindex">` and *don't* also block it in robots.txt (Google can't see a noindex it isn't
allowed to crawl).

## 10. sitemap.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc><lastmod>2026-10-04</lastmod></url>
  <url><loc>https://example.com/qr-menu</loc><lastmod>2026-10-04</lastmod></url>
</urlset>
```

- Include only canonical, indexable, 200-status URLs, with absolute `https://` URLs on the
  production host, matching the canonical exactly (trailing slash included).
- `lastmod` uses W3C date format (`YYYY-MM-DD` or full ISO) and reflects real content changes. Google
  ignores lastmod if it's always "now".
- Put the most important pages first (home, main keyword pages, pricing). `priority` and
  `changefreq` are ignored by Google, so they're optional.
- More than 50,000 URLs → use a sitemap index.
- If the site URL is unknown, generate from a single `SITE_URL` constant or env var and mark it as a
  placeholder.

## 11. hreflang (only when more than one language is confirmed)

Each language version links to all versions including itself, plus `x-default`:

```html
<link rel="alternate" hreflang="tr" href="https://example.com/qr-menu" />
<link rel="alternate" hreflang="en" href="https://example.com/en/qr-menu" />
<link rel="alternate" hreflang="x-default" href="https://example.com/qr-menu" />
```

In Next.js, use `alternates: { canonical, languages: { tr: '/qr-menu', en: '/en/qr-menu', 'x-default': '/qr-menu' } }`.
In the sitemap, add `xmlns:xhtml` and `<xhtml:link rel="alternate" hreflang=… href=…/>` per URL.
Each language version is canonical to itself, never to the other language.

## 12. JSON-LD (truthful only)

| Page | Types |
|---|---|
| Home | `Organization` (or `Person`) + `WebSite` |
| Product / keyword page | `SoftwareApplication` (SaaS: `applicationCategory`, `operatingSystem`, `offers` only with real prices) or `Product` / `Service` |
| Local business pages | `LocalBusiness` subtype (`LegalService`, `Restaurant` …) with `name`, `address`, `telephone`, `openingHours`, `geo` only if known |
| Blog post | `BlogPosting` (`headline`, `datePublished`, `dateModified`, `author` = real Person, `image`) |
| FAQ section | `FAQPage`, matching the visible Q&A exactly |
| Any nested page | `BreadcrumbList` |
| Personal site | `Person` with `sameAs` [social URLs], `jobTitle` |

Never add `aggregateRating` or `review` without real, on-page reviews. Unknown values become
placeholders. Validate with Google's Rich Results Test (give the user the link:
https://search.google.com/test/rich-results).

## 13. Slugs and transliteration

Lowercase, ASCII, hyphens, no stop-word soup, ≤ ~5 words.
Turkish map: `ç→c ğ→g ı→i İ→i ö→o ş→s ü→u` (also `â→a î→i û→u`).
Examples: `karekod menü` → `karekod-menu` · `QR Menü Nedir?` → `qr-menu-nedir` ·
`Nişantaşı Arabuluculuk` → `nisantasi-arabuluculuk`.
Other languages: strip diacritics (`ä→a` or the `ae` convention the site already uses). Never change
an existing URL without asking, because it needs a 301 redirect, which is server or config work.

## 14. Duplicates and canonicals

- Every indexable page has a self-referencing canonical with an absolute URL.
- Pick one trailing-slash style and match it in links, canonicals and the sitemap (Next.js
  `trailingSlash` is config, so ask).
- Parameter variants (`?ref=`, `?utm_`) canonicalize to the clean URL.
- Paginated blog lists canonicalize to themselves (page 2 → page 2), not to page 1.
- Thin utility pages (thank-you, search results, tag pages with one post) → `noindex,follow`.
- www vs non-www, http → https, old URLs → new: **report** these to the user. They're redirects in
  server or hosting config, not frontend work.

## 15. Blank project scaffold (mode C, after the user approves Next.js)

Propose: `npx create-next-app@latest . --ts --app --eslint --src-dir=false --import-alias "@/*"`
(ask about Tailwind; it's the user's styling choice). Then create:
- `app/layout.tsx` with metadata, `lang` and a shared header/footer
- the approved pages
- `app/robots.ts`, `app/sitemap.ts`, `app/not-found.tsx`
- a `lib/site.ts` holding `SITE_URL`, brand, NAP and socials in one place (placeholders where unknown)

Plus the `.gitignore` entry `/seo/`. Use `output: 'export'` only if the user wants static hosting.
