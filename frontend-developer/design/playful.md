# Playful (friendly, colorful, rewarding)

Use for segments the user marked **Playful**. Typical segments: consumer apps for learning,
habits, kids, food, games and social; onboarding flows; achievements; empty states; any segment
whose goal is to make people *want to come back*.

Sources: Duolingo, Headspace, Notion (marketing pages), Mailchimp (Freddie-era brand), Airbnb
illustrations, Figma and Discord marketing pages, and Material 3 Expressive. See `sources.md`.

## Rules

**Color**
- Two or three saturated brand colors plus warm neutrals. Use flat color blocks for sections and
  colored cards. Gradients are allowed but must be subtle.
- Each color has a job: primary action, reward/success, highlight. Don't color randomly. Text on
  color still needs ≥ 4.5:1 contrast. Saturated yellow and lime need dark text.

**Typography**
- Rounded or soft geometric display font for headings (Nunito, Fredoka, Baloo 2, Quicksand,
  DynaPuff, Gluten, Lexend for readability). Use a highly readable sans for body.
- Bigger, bolder headings (scale 1.333). Short sentences.

**Shape and depth**
- Large radius (16–24px), pill buttons and chunky borders (2–3px).
- "Sticker" offset shadows (a solid shadow 4px down and 4px right) or soft colored shadows.
- Buttons have a visible pressed state, moving down 2–4px on press like a physical key (Duolingo).

**Illustration and character**
- A consistent illustration style (one artist feel): blobs, mascots, hand-drawn icons and emoji
  accents. Illustrations explain empty states, errors and onboarding steps.
- A mascot or character can react to user actions (success, failure, waiting).

**Motion and feedback**
- Springy easing (slight overshoot), 200–400ms.
- Celebrate wins: confetti or a burst on completion, streak counters and progress rings
  (goal-gradient effect). Reward is proportional: small actions get small feedback.
- Skeletons can be colorful; loaders can be tiny animations.
- Everything respects `prefers-reduced-motion`. Celebrations become a static badge.

**Copy tone**
- Warm, encouraging and human ("Nice! 3 days in a row"). Errors are kind and still
  specific ("That code didn't work. Check the 6 digits we emailed you.").
- Never childish in serious moments (payment, privacy, account deletion). Those use the
  **normal** rules with the playful palette.

**Watch out**
- Playful isn't messy: it uses the same grid, spacing scale and alignment discipline as normal.
- Don't put playful decoration on dense data screens. It competes with the data.
- Don't make every element animated. Pick moments.
