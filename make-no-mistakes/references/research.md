# Research (Phase 1)

Do the research once, here, and copy what each worker needs into its prompt. Workers don't search
again unless their prompt names a specific open question.

## Queries (send in one message)

Replace `<idea>` with the product noun phrase and `<audience>` if known. New project, 3–5 of:

| # | Query pattern | Purpose |
|---|---|---|
| 1 | `best <idea> apps <current year>` | Competitor list |
| 2 | `<top competitor> features` / `<idea> app features comparison` | Feature catalog |
| 3 | `<idea> app reviews complaints` / `reddit <idea> app what I wish` | Gaps competitors leave |
| 4 | `<domain> best practices` (e.g. `spaced repetition algorithm best practice`) | Domain logic |
| 5 | `<idea> regulations` only if the domain is regulated (health, finance, kids, education data) | Compliance |

Existing project: the same, aimed at the feature (`<feature> UX best practices`,
`<feature> <framework> <version> implementation`, `<feature> security pitfalls`).

Use WebFetch on at most 3 pages that look like real feature lists or official docs. Skip SEO spam
and listicles that only repeat each other.

## What to extract

- **Features** that appear in ≥ 2 competitors (table stakes) and distinctive features that appear
  in 1 (differentiators). Record *how* each competitor does it, in one line, so the "Yes" option
  can say exactly what will be built.
- **Complaints / gaps:** what users dislike (paywalls, ads, no offline, slow sync, no export).
  Turn these into differentiator proposals.
- **Best practices** per area (domain logic, UX, security, SEO, performance), each as one
  actionable line with the source.

## `mnm/research.md` format

```markdown
# Research: <idea>  (<date>)

## Competitors
| Name | URL | Positioning | Pricing model |

## Feature catalog
| ID | Feature | Who has it | How they do it (1 line) | Type | Source |
|----|---------|-----------|--------------------------|------|--------|
| F1 | Spaced-repetition flashcards | Anki, Memrise | SM-2-style review queue, daily due count | table stakes | <url> |
| F2 | Speaking practice with feedback | Babbel | Speech recognition scores pronunciation per word | differentiator | <url> |

## Gaps competitors leave
- G1: … → proposal: …

## Best practices
### Domain
### Backend
### Frontend / UX
### Security
### SEO
```

Keep it short: 8–20 features. Merge near-duplicates. Leave out features that clearly don't fit the
user's description (e.g. kids' mode for a B2B tool) instead of asking about them.

## Rules

- Never copy competitor text, branding or proprietary content into the product. Take ideas only.
- Cite a source URL for every feature and practice; "general knowledge" is allowed for well-known
  practices (e.g. argon2id for passwords).
- If search fails or is unavailable, use your own knowledge and say so in the file header.
