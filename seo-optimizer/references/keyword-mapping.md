# Keyword mapping: sub-keywords → intent → page

The aim is one clear page per search intent. A searcher who asks "what is a QR menu?" wants an
explanation. A searcher who types "QR menu price" wants numbers. Serving both on one page satisfies
neither, and two pages chasing the same query split the ranking signals (cannibalization).

## 1. Generate sub-keywords

For each approved word, build candidates from:
1. People Also Ask and related searches from the research notes (strongest signal, because they are
   real queries).
2. Intent modifiers (table below).
3. What the product actually does: features, use cases and audiences found while reading the project.
4. The location, for local businesses (district, city, "yakınımda" / "near me").

Drop candidates the product can't honestly answer (e.g. "online sipariş" for a menu-only product).
Flag them to the user instead of silently dropping them: they may be feature ideas (Phase 8
suggestions).

## 2. Intent taxonomy

| Intent | What the searcher wants | Turkish modifiers | English modifiers | Typical home |
|---|---|---|---|---|
| Informational | To learn or understand | nedir, nasıl, neden, ne işe yarar, örnekleri, rehber | what is, how to, why, guide, examples | `/blog/<slug>`, FAQ entry |
| Commercial investigation | To compare solutions | en iyi, programı, yazılımı, uygulaması, karşılaştırma, alternatifleri, vs | best, software, app, tool, vs, alternatives, review | landing page, keyword page (`/qr-menu`), comparison page |
| Transactional / pricing | To buy, sign up or see prices | fiyat, fiyatları, ücret, ücretsiz, satın al, demo, kayıt | price, pricing, cost, free, buy, demo, sign up | `/pricing`, signup/demo CTA |
| Local | To find a provider nearby | <ilçe/şehir>, yakınımda, adres, iletişim | <city>, near me | `/about`, `/contact`, a location page **only** if it has unique content |
| Navigational / brand | To find this specific site | <brand>, <brand> giriş, <person name> | <brand>, <brand> login | home, `/about`, `/contact` |

When a word mixes intents ("qr menü fiyatları nasıl belirlenir"), choose the dominant one by
looking at what the top-3 results actually are. Google has already decided the intent.

## 3. Assignment rules

- **One primary keyword per page; one page per primary keyword.** Close variants (`qr menü`,
  `qr menu`, `karekod menü`) normally belong to the *same* page as secondaries. Give a variant
  its own page only if its top-3 results are clearly different pages with a different intent.
- **Prefer existing pages.** Improving an existing URL keeps its history and links. Propose a new
  page only when no existing page fits the intent.
- **No doorway pages.** Don't create `/qr-menu-istanbul`, `/qr-menu-ankara` … with swapped city
  names. A location page is fine only when it has genuinely unique content (a real office, local
  customers, local regulations).
- **Landing-page budget.** The home or landing page serves the main commercial intent: hero (H1 plus
  a one-sentence value proposition and CTA), 3–5 benefit or feature blocks, proof (only if real),
  a short FAQ teaser or link, and links to the keyword, pricing and blog pages. On a phone it should
  end within roughly 6–8 screen heights. Everything else moves to dedicated pages.
- **Respect the user's no.** If the user doesn't want public prices, pricing intent goes to a
  "request a quote / demo" section or is dropped. Don't sneak a pricing page back in.
- **Every page links into the graph.** Plan at least one link *into* each new page from an existing
  page (nav, footer, related posts, body text), or it will be orphaned.

## 4. Slugs

Lowercase ASCII, hyphen-separated, short, matching the primary keyword in the target language:
`/qr-menu`, `/blog/qr-menu-nedir`, `/fiyatlar` or `/pricing` (follow the site's existing URL
language; if there's none, use the content language). Transliteration table:
`references/technical-seo.md`.

## 5. Page plan table (show this to the user)

```
I am going to add / change these pages. Reply per row: yes / no / yes but change …

| # | Path | New/Existing | Page type | Primary keyword | Secondary keywords | Intent | Missing info → placeholder |
|---|------|--------------|-----------|-----------------|--------------------|--------|----------------------------|
| 1 | / | Existing | Landing | qr menü | dijital menü, karekod menü | commercial | — |
| 2 | /blog/qr-menu-nedir | New | Blog post | qr menü nedir | qr menü nasıl çalışır | informational | — |
| 3 | /fiyatlar | New | Pricing | qr menü fiyatları | qr menü ücretleri | pricing | prices → {{PLACEHOLDER: price_basic_monthly}}, {{PLACEHOLDER: price_pro_monthly}} |
| 4 | /iletisim | Existing | Contact | <brand> iletişim | — | navigational | phone → {{PLACEHOLDER: phone}} |
```

Under the table, add one or two lines on **why** for any non-obvious row (e.g. "Row 2: all top-3
results for 'qr menü nedir' are explanatory blog posts, so a sales page wouldn't rank for it").
Also list sub-keywords you dropped and why, so the user can overrule you.

## 6. Recording

Save the approved map in `seo/seo-plan.json` (`pages[]` and `keywords[]`) and the rejected rows in
`rejected[]`. Later runs read these to avoid re-proposing rejected pages and to prevent
cannibalization.
