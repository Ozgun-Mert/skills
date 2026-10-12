# Style interview (Phase 3)

The user decides how each **segment** of the frontend should look. One site can mix styles, for example a
fancy landing page, normal panels and a strict blog. Each style maps to a design file:

| Style | File the segment follows | In one line |
|---|---|---|
| Fancy | `SKILL_DIR/design/fancy.md` + `DESIGN/brand.md` (fancy overrides) | Award-level: big type, scroll storytelling, motion, bold two-color palette |
| Normal | `DESIGN/normal-polished.md` (from `SKILL_DIR/design/normal.md`) | Familiar and efficient, like the big sites people already use |
| Strict | `SKILL_DIR/design/strict.md` | Content-first, minimal, fast, very readable |
| Playful | `SKILL_DIR/design/playful.md` | Friendly, colorful, rounded, celebratory |

Every segment, whatever its style, also follows `SKILL_DIR/design/ux-principles.md` and
`DESIGN/ux-patterns.md`. All segments share the tokens in `DESIGN/brand.md` (fonts and palette), so the
site still feels like one product. Style changes the *treatment*, not the identity.

## Segments

Offer only the segments this project actually has. Group small ones: if auth is only two pages, put it in
with forms.

| Segment | Typical routes | Default recommendation |
|---|---|---|
| Landing / marketing | `/`, `/features`, `/pricing`, `/about` | Fancy for consumer, brand, luxury, portfolio; Normal for B2B tools; Playful for kids, learning, games |
| Auth | `/login`, `/signup`, `/reset` | Normal |
| Panels / dashboard | `/app`, `/dashboard`, `/admin` | Normal |
| Lists / catalog | `/menu`, `/products`, `/search` | Normal (Playful for fun consumer apps) |
| Detail | `/product/[id]`, `/item/[id]` | Normal (Fancy for luxury and showcase products) |
| Forms / checkout | `/checkout`, `/new`, multi-step flows | Normal; Strict for government, finance, legal |
| Blog / content | `/blog`, `/blog/[slug]` | Strict |
| Docs / help | `/docs`, `/help`, `/faq` | Strict |
| Settings / account | `/settings`, `/profile` | Normal |
| Onboarding / achievements | `/welcome`, streaks, badges | Playful |

Adjust a recommendation with the research. If every competitor is dense and utilitarian, a Fancy
landing page can be the differentiator. If the audience is older or the domain is serious (health,
legal, finance), lean towards Normal or Strict.

## Question format

Ask at most 4 segments per AskUserQuestion call. For example:

```
question: "Landing page (/, /pricing, /about): which style?"
header: "Landing"
options:
  - label: "Fancy (Recommended)"
    description: "Big headline, scroll-driven story, smooth motion, bold two-color look. Best first impression; a bit heavier."
  - label: "Normal"
    description: "Clean and familiar, like Wolt/Airbnb's homepage. Fast, clear, safe."
  - label: "Strict"
    description: "Minimal, text-first, very fast. Suits serious or content-heavy brands."
  - label: "Playful"
    description: "Rounded, colorful, illustrated, cheerful micro-animations."
```

Put the recommended option first. Write each description for *this* segment and project. Mention a
competitor the user knows when that helps them picture it.

After the segment questions, you may ask one optional mood question with 2–4 directions from
`brand.md`, for example "Warm & appetizing (Recommended)" / "Fresh & minimal" / "Bold & energetic". If the
user types something else ("like Apple but greener"), fold it into `brand.md` and say what changed.

## `DESIGN/styles.md`

```markdown
# Styles per segment (chosen <date>)
| Segment | Routes | Style | Follow | Notes from user |
|---|---|---|---|---|
| Landing | /, /pricing | Fancy | design/fancy.md + brand.md#fancy | "not too dark" |
| Panels | /admin/** | Normal | DESIGN/normal-polished.md | |
| Blog | /blog/** | Strict | design/strict.md | |
Mood: warm & appetizing
```

A forms or checkout flow *inside* a Fancy or Playful segment always uses Normal behaviour, styled with
that segment's tokens (`fancy.md` non-negotiable #7).
