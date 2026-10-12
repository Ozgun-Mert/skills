# Project research (Phase 2)

Do this once per project. Everything you learn goes into `DESIGN/`, and later runs read those files
instead of searching again. Re-research only if the user asks, or if `DESIGN/project.md` no longer matches
the product.

## 1. Queries (send them in one message)

Work out from `DESIGN/project.md`:
- `<product>`: a short noun phrase such as "QR menu ordering", "language learning flashcards" or "law firm
  website"
- `<market>`: the country or region and language. Use the copy language, the currency, the domain, or
  ask if unclear.

| # | Query | Purpose |
|---|---|---|
| 1 | `best <product> apps <current year>` | Global leaders |
| 2 | `<product> in local language` + `en iyi` / `beste` / `meilleur` … | Local leaders, e.g. `qr menü sipariş sistemi`, `online yemek siparişi uygulaması` |
| 3 | `<top global competitor> vs <top local competitor>` or `<product> app UX review` | How the leaders differ |
| 4 | `<product> UX best practices` / `<key flow> UX` (e.g. `food ordering checkout UX`) | Flow patterns |
| 5 | `<product> website design inspiration` (dribbble/behance/awwwards/godly/land-book) | Visual direction |
| 6 | Only for regulated domains: `<product> <market> regulations` (e.g. KVKK, allergen labelling) | Required UI elements |

Use the 3–6 most relevant real products: the market leaders, a local leader and a design leader. Skip
listicles that only repeat each other. For each product:
- WebFetch the landing page and one inner page.
- Optionally, run `python "SKILL_DIR/scripts/shoot.py" --url <site> --routes / --widths 390,1280 --viewport-only --out DESIGN/.work/competitors/<name>`
  and look at the screenshots. That shows you what text can't: density, color, type, imagery.

If search is unavailable, use what you know and say so at the top of each file.

## 2. `DESIGN/similar-sites.md`

```markdown
# Similar sites: <product> (<market>), researched <date>

| Site | Market | URL | Why it matters | Layout & nav | Density | Type | Color | Imagery | Standout pattern |
|---|---|---|---|---|---|---|---|---|---|
| Wolt | global | wolt.com | design leader in delivery | top search, horizontal category chips, big image cards | airy | rounded geometric sans | blue on white | big food photos | sticky basket bar at bottom on mobile |
| Yemeksepeti | TR | yemeksepeti.com | TR market leader, the habits users bring | … | dense | … | pink/magenta | … | … |

## What users of this market expect (Jakob's law)
- … (e.g. TR users expect prices as "₺120,00", card installment ("taksit") info at checkout, WhatsApp contact)

## What we will NOT copy
- Their palettes (Wolt blue, Yemeksepeti pink), logos, illustrations, copy.
```

## 3. `DESIGN/ux-patterns.md`

For every flow in the product, write the pattern the leaders converge on (that is the convention) and
any clever variation. Then say where it applies here.

```markdown
## Flow: browse menu → add to cart
- Convention (Wolt, Yemeksepeti, Uber Eats): sticky category chips that scroll-spy the sections; item cards with photo, name, 2-line description, price; tap opens a bottom sheet with options; floating "View basket (2) · ₺240" bar.
- Variation worth taking: Wolt shows the basket total live in the bar (L-Doherty, H1).
- Apply to: /menu/[table] (segment: catalog → Normal).
- Principles: L-Jakob, L-Fitts (bottom bar in the thumb zone), H1.
```

Cover the common flows if the product has them: first visit and onboarding, search and filter, browse
and detail, cart and checkout, sign-up and sign-in, create/edit forms, dashboard overview, tables and
bulk actions, notifications, settings, empty and error states, plus the domain-specific flows.

## 4. `DESIGN/normal-polished.md`

Copy the structure of `SKILL_DIR/design/normal.md` and make each rule concrete for this domain and
market: navigation pattern, density, component specifics (e.g. "price always bottom-right of a card,
bold"), formats (currency, dates, phone), tone. Drop rules that don't apply. This file, not the
baseline, is what Normal segments follow.

## 5. `DESIGN/brand.md`: our own identity

Choose them for the *topic and audience*, and make them **differ from the 3 main competitors**:

1. **Mood words** (3): e.g. "warm, appetizing, quick".
2. **Fonts.** 1 display + 1 text (+ 1 mono only if needed), free to use (Google Fonts / Fontshare).
   - Give a reason for each one.
   - Check that it supports the language's characters (Turkish needs ğ ş ı İ ç ö ü; test "Iğdır'da şişli
     çöp").
   - Explain how it differs from the competitors' fonts.
   - Self-host the fonts or use the framework's font loader, with `font-display: swap`.
3. **Palette** as tokens:
   - `--bg`, `--surface`, `--text`, `--text-muted`, `--border`
   - `--primary` (+ hover/active), `--accent`
   - `--success`, `--warning`, `--danger`, `--focus`

   Give light and dark values. Write the contrast ratio for each text/background pair and pass WCAG AA
   (4.5:1 for text, 3:1 for UI). Explain why these colors fit the topic (e.g. warm tomato and cream for
   food; avoid the competitors' pink and blue).
4. **Scale and shape:** type scale (ratio + sizes), spacing scale, radius, shadows, motion durations and
   easing. If any segment is Fancy or Playful, also give that segment's token overrides (bigger display
   sizes, springier motion).
5. **Imagery and iconography:** photo style, illustration style, icon set.

Compute contrast exactly rather than guessing. For example:
`python -c "f=lambda h:[(lambda c:c/12.92 if c<=.03928 else((c+.055)/1.055)**2.4)(int(h[i:i+2],16)/255) for i in(1,3,5)];L=lambda h:.2126*f(h)[0]+.7152*f(h)[1]+.0722*f(h)[2];a,b=L('#1F2937'),L('#FFFFFF');print(round((max(a,b)+.05)/(min(a,b)+.05),2))"`

## 6. `DESIGN/README.md`

```markdown
# DESIGN: <project>  (generated by /develop-frontend, gitignored)
- project.md: what the product is, data sources (contract / mock / none)
- similar-sites.md, ux-patterns.md, normal-polished.md, brand.md: research (<date>)
- styles.md: style per segment (Phase 3)
- plan.md: page plan + task table (Phase 4)
- Baseline files used: SKILL_DIR/design/{fancy,normal,strict,playful,ux-principles}.md
- .work/: state, routes, review rounds, screenshots
```
