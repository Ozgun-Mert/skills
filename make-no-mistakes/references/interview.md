# Interview (Phase 2)

Goal: by the end, every item in the completeness checklist has an answer or an explicit default,
and the user has typed as little as possible.

## Never ask (decide yourself)

Programming language, framework, database, ORM, hosting/cloud, monorepo or not, REST vs GraphQL,
state management, CSS framework, auth library, testing tools, CI, folder structure. If the user
volunteers a preference, record it in `mnm/decisions.md` and follow it.

## AskUserQuestion shapes

### 2a. Feature from research (one question per feature, 4 per call)

```json
{
  "question": "F1 Spaced-repetition flashcards: Anki and Memrise show a daily review queue that resurfaces words right before you'd forget them. Include it?",
  "header": "F1 Flashcards",
  "multiSelect": false,
  "options": [
    {"label": "Yes", "description": "Build it like Anki: daily due queue, again/hard/good/easy buttons, SM-2 scheduling."},
    {"label": "No", "description": "Leave it out."},
    {"label": "Yes, with a tweak", "description": "Build it, changed the way you describe. Type the tweak in the 'Other' box, or pick this and I'll ask."}
  ]
}
```

- `header` ≤ 12 chars: use the feature ID plus a short word.
- Put table-stakes features first, then differentiators, then gap proposals (`G1 …`).
- A free-text "Other" answer counts as "Yes, with a tweak" using that text, unless it clearly says
  no.
- If "Yes, with a tweak" comes with no text, ask one plain question: "What should change about F1?"

### 2b. Open scope question (plain text, only when needed)

Ask when the description names a category but not the user's specific goal. "build me an app for
learning german" is clear enough on its own. "make me an app" or "something for my business" is
not. Ask in one message and wait:

> Besides the features above, what else should it do? A few words per idea is enough (e.g. "teacher
> can assign homework", "works offline").

Turn each idea into a feature row, `U1`, `U2`, …, and confirm unclear ones in 2c with options.

### 2c. Detail rounds

Each question has 2–4 options with the recommended one first, and a description that says the
consequence. Ask only items that are still open. Derive the recommendation from the research and
the description.

## Completeness checklist

| # | Item | Typical options (recommended first, adapt to the product) | Feeds |
|---|---|---|---|
| 1 | Primary users | Individuals (B2C) · Teams/organizations (B2B) · Both | roles, tenancy |
| 2 | Roles | User only · User + admin · User + admin + <domain role, e.g. teacher> | roles, ACL |
| 3 | Sign-in | Email + password · Email magic link · Google sign-in · Email + Google | auth |
| 4 | **Data sharing** (one question per main resource) | Private to owner · Shared with invited people · Visible to everyone in the org/class · Public | **access-control matrix** |
| 5 | Public pages | Landing + pricing + blog/SEO pages · Landing only · App only, no public pages | pages, SEO |
| 6 | Monetization | Free · Free + paid plan (placeholder prices) · Paid only · Decide later (no payments now) | payments piece |
| 7 | Content source | Users create it · We provide starter content (placeholders) · Imported from a file/API | seed data |
| 8 | Admin needs | Simple admin page (users, content, reports) · None for now | admin piece |
| 9 | Notifications | Email for account events only · Email + reminders · In-app only · None | jobs |
| 10 | Languages | UI language(s): one · several (i18n) | i18n piece |
| 11 | Devices | Responsive web (mobile-first) · + installable PWA · + offline | frontend |
| 12 | Integrations | None · <relevant ones from research> | pieces |
| 13 | Compliance / region | GDPR (EU) · KVKK (TR) · Both · None special | legal pages, data |
| 14 | Brand | Name (text answer only if they have one; else "Pick a placeholder name") · colors: pick for me / I have colors | tokens |
| 15 | **UI style** (always) | **Professional**: calm, trustworthy, dense · **Balanced**: friendly but clean · **Fun**: bold colors, playful motion, illustrations | design tokens |
| 16 | Scope | Full version of every Yes feature (Recommended when ≤ ~12 features) · MVP first: table stakes now, rest later | waves |
| 17 | Scale expectation | Small (≤ 1k users) · Growing (≤ 100k) · Large (100k+) | stack sizing |

Item 4 is the most important. Ask it for every resource where privacy isn't obvious. Never assume
"public" for user-created content. If the user picks "Shared with invited people", follow up with
the permission levels (view / edit / manage).

Item 17 is a product question (audience size), not an architecture question. Use it only for
sizing.

## 2d. Confirmation

Show a summary like this:

```
Building: <name> — <one line>
Features: F1 ✓, F2 ✓ (tweak: only for paid users), F3 ✗, U1 ✓ …
Users & roles: …   Sign-in: …
Who sees what: decks → owner only; classes → teacher + enrolled students; …
Style: Balanced · Languages: EN UI, German content · Devices: responsive + PWA
Scope: full · Monetization: free + paid plan (prices as placeholders)
```

Then AskUserQuestion: **Build this (Recommended)** / **Change something**. "Change something" → ask
what (text), update, and show the summary again.

## Recording

Append every answer to `mnm/decisions.md` as `- [phase/item] question → answer`. On a resume, read
it first and skip what's answered.
