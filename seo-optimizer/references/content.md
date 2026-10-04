# People-first content

Google's ranking systems reward pages written to help a person, not to match a string. In practice:
answer the searcher's real question quickly, add something the current top results don't have, and
make it trustworthy (who wrote it, where the facts come from, real examples).

## 1. Brief template (one per approved page; show the user the briefs in one message)

```markdown
### <path>: <page type>
- Primary keyword / secondaries: …
- Reader & question: who lands here and what they need answered in the first screen
- Gap we fill (from research): what the top-3 results miss that we add
- Outline:
  - H1: … (states the topic plainly; includes the primary keyword if it reads naturally)
  - H2: …
    - H3: …
  - H2: …
- Internal links out: → /…, → /…   |   Links in (from): /…, /…
- CTA: …
- Product claims this page will make (need confirmation): 1. … 2. …
- Original material wanted: screenshots of X, real number Y, a customer example …
- Placeholders: {{PLACEHOLDER: …}}
```

## 2. Fact check before writing

Collect every capability claim across all briefs into one numbered list and ask the user to confirm
it in a single message:

```
Before I write the copy, please confirm what the product really does (yes / no / partly + note):
1. Menus can be updated instantly without reprinting the QR code
2. Supports multiple languages per menu
3. Integrates with POS systems: which ones?
…
```

Anything not confirmed is left out of the copy. If it would help SEO, list it in the Phase 8 feature
suggestions instead.

## 3. Original data: ask, never invent

Ask for: real usage numbers, number of customers or venues, years in business, credentials or
licences (e.g. a mediator's registry number), case studies, testimonials with permission, product
screenshots, team or office photos, prices and plan names. If the user has none, write without
them. Specific, honest copy beats fake social proof.

Never invent: statistics, percentages, testimonials, reviews, star ratings, client logos, awards,
press mentions, author names or bios, dates of founding, certifications.

## 4. Placeholders

Format: `{{PLACEHOLDER: snake_case_name}}`. Use it exactly like this, so a single grep finds every
one (`grep -rn "{{PLACEHOLDER:" .`). Use the placeholder in visible copy, attributes and JSON-LD
alike. A placeholder that ships by accident is visible and gets fixed, while an invented value ships
silently. Record every placeholder in `seo/seo-plan.json` → `placeholders[]` with its file and what's
needed. List them all in the final report.

Common ones: `site_url`, `brand_name`, `phone`, `email`, `address_street`, `address_city`,
`price_<plan>_monthly`, `plan_<n>_name`, `founding_year`, `author_name`, `author_bio`,
`company_legal_name`, `tax_office_and_number`, `kep_address`, `data_controller_contact`.

## 5. Writing rules

- **Answer first.** The first paragraph under the H1 answers the page's main question in 1–3
  sentences.
- **Headings are questions or topics a person would scan for.** Use keywords where they fit
  naturally. Never stack synonyms ("QR Menü, Karekod Menü, Dijital Menü Çözümleri") into a heading.
- **Short paragraphs** (2–4 sentences), lists where they help, one idea per section.
- **Be specific to this product**: its real workflow, real screens, real limits. Generic text that
  could sit on any competitor's site adds nothing.
- **Blog posts:** a real author (or `{{PLACEHOLDER: author_name}}`), published and updated dates,
  sources linked for every external fact, a closing section linking to the relevant product page.
  Research facts from reliable sources (official bodies, standards, primary data) and keep the source
  links in `seo/research/<slug>.md`.
- **FAQ:** real questions taken from PAA and the user's customer questions, with answers of 2–5
  sentences. Each answer links to the page with more detail. Don't repeat the same FAQ block on many
  pages, because that creates duplicate content.
- **Titles:** ~50–60 characters, unique, primary keyword near the front, brand at the end
  (`QR Menü Nedir? Restoranlar İçin Rehber | Brand`).
- **Meta descriptions:** ~140–160 characters, unique, describing what the page offers plus a soft
  CTA. They don't affect ranking directly, but they do affect clicks.
- **Alt text:** describe what the image shows and why it's there ("Telefon ekranında açılmış QR
  menü, kategori listesi görünüyor"). Don't stuff keywords. Use `alt=""` for decorative images.
- **Turkish:** use correct characters (ç ğ ı İ ö ş ü) in copy, titles and alt text. Transliterate
  only in URLs.

## 6. Duplicate-content hygiene

Don't reuse paragraphs across pages. Boilerplate (footer, nav) is fine. Repeated body sections are
not. If two planned pages end up saying the same thing, merge them and tell the user.
