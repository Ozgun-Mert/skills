# Research: top-3 SERP analysis

Purpose: learn what Google already rewards for each word, find what those pages *miss*, and use the
gap to plan pages that deserve to rank. Gather inspiration here, never text.

## 1. Locale

Use the target language and country confirmed in Phase 1.

| Market | Search URL |
|---|---|
| Turkey / Turkish | `https://www.google.com.tr/search?q=<q>&hl=tr&gl=tr&num=10&pws=0` |
| US / English | `https://www.google.com/search?q=<q>&hl=en&gl=us&num=10&pws=0` |
| UK / English | `https://www.google.co.uk/search?q=<q>&hl=en&gl=gb&num=10&pws=0` |
| Germany / German | `https://www.google.de/search?q=<q>&hl=de&gl=de&num=10&pws=0` |
| Other | `https://www.google.<cctld>/search?q=<q>&hl=<lang>&gl=<country>&num=10&pws=0` |

URL-encode `q` and keep the Turkish characters (`qr%20men%C3%BC`). `pws=0` turns off
personalization. For a local business, put the place in the query itself (`arabuluculuk nişantaşı`),
since location parameters don't reliably emulate a city.

## 2. Procedure with the built-in browser (first choice)

1. Navigate to the search URL.
2. **Consent screen** (common in EU/TR): pick the most privacy-preserving option ("Reject all" /
   "Tümünü reddet"). If the only choice is to accept, stop and ask the user. Don't accept on your
   own.
3. **Block detection.** Any of these means you are blocked: the URL contains `/sorry/`, or the page
   text contains "unusual traffic", "olağan dışı trafik", "I'm not a robot", "Ben robot değilim" or
   "reCAPTCHA". Don't click it, don't retry in a loop, and don't try another Google domain to get
   around it. Switch to WebSearch for **all remaining words** and note it for the final report:
   "Google blocked automated search. Results come from WebSearch and may differ from real Google
   rankings."
4. Read the results with `get_page_text` (fall back to `read_page`). Skip ads ("Sponsored",
   "Sponsorlu", "Reklam", "Ad"), maps/local packs, video carousels and "People also ask" boxes when
   counting the **top 3 organic** results. Do record the PAA questions and the "Related searches"
   ("İlgili aramalar") list separately.
5. Open each top-3 result (or fetch it with `curl -sL -A "Mozilla/5.0"`) and record its title, H1,
   H2/H3 outline, page type and approximate length. Read for structure and topics. Don't paste
   paragraphs into notes.

Go one word at a time and keep it polite. Don't fire many searches in rapid succession.

## 3. Fallback: WebSearch

Query the word in the target language, adding the country or city if it's local. Take the first 3
results that are real pages (not ads or aggregators of ads) and fetch them as above. WebSearch has no
PAA box, so get question ideas from follow-up searches like `<word> nedir`, `<word> nasıl`,
`<word> fiyat`, `what is <word>`, `<word> vs`.

## 4. Relevance verdict

A result is **relevant** if it serves the same audience with the same kind of offer or information
our project provides. It is **irrelevant** if it only shares a word. For example, for a "qr menü"
SaaS, a QR-code generator for business cards or a news article about a restaurant chain is
irrelevant. Take nothing from irrelevant results except the signal that Google's intent for this
word may differ from ours. If **all three** are irrelevant, tell the user: the word may not fit
the project and is a candidate for dropping or re-scoping.

## 5. Note template: `seo/research/<keyword-slug>.md`

```markdown
# <keyword>: research (<YYYY-MM-DD>, source: Google <locale> | WebSearch fallback)

## Top 3 organic results
| # | URL | Title | Page type | Intent served | Relevant? |
|---|-----|-------|-----------|---------------|-----------|
| 1 | … | … | landing / blog / directory / category / tool | commercial / informational / … | yes / no: why |

### Result 1: outline and observations
- H1: …
- H2s: … (topics only, in your own words)
- Strengths: …
- **Missing / weak:** … ← our opportunity

(repeat for 2 and 3)

## People Also Ask / related searches
- …

## Takeaways for our pages
- Topics we must cover: …
- Gaps we can own (original angle, data, tool, example): …
- Intent Google seems to reward for this word: …

## Sources for facts (if a blog post will cite them)
- <title>: <url>
```

## 6. Copying and copyright

Notes summarize structure and topics in your own words. Never paste competitor paragraphs, lists,
FAQs or headings verbatim into notes or pages. When a fact from a source goes into a blog post, put
it in your own words and link the source.
