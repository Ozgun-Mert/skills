# Strict (content-first, editorial, minimal)

Use for segments the user marked **Strict**. Typical segments: blog posts, articles, documentation,
help center, legal pages, government or institutional pages, reports, changelogs, and any page
whose job is to be *read* or *trusted*.

Sources: the GOV.UK Design System, Wikipedia, Stripe and MDN docs, The New York Times and The
Guardian article pages, Medium, and Butterick's *Practical Typography*. See `sources.md`.

Components: shadcn/ui only (typography classes, table, accordion, alert, tabs, breadcrumb), with no React
Bits motion (`component-kits.md` §7).

The idea: **the design disappears and the content is the interface.** No decoration that doesn't
help reading, finding or trusting.

## Rules

**Layout**
- One reading column, 60–75 characters wide (~640–720px at 18px). The GOV.UK pattern is two-thirds width for
  text on desktop and full width on mobile.
- Docs: a three-pane layout (sidebar nav, content, "On this page" table of contents) that collapses to
  a single column with a TOC dropdown on mobile.
- Generous vertical rhythm. Space separates sections; lines and boxes are kept to a minimum.

**Typography**
- Body **18–21px** for long reading (GOV.UK uses 19px), line height 1.5–1.7.
- Serif *or* sans body is fine. Editorial sites favour a serif body with a sans UI; docs favour sans
  body with a mono for code.
- Scale 1.25–1.333, with clear H1 → H2 → H3. Never skip levels; headings are the outline.
- Headings in sentence case. Bold for emphasis, never ALL CAPS paragraphs or underlines that aren't
  links.
- Code: a mono font at 0.9em, a block background, a copy button and horizontal scroll inside the
  block.

**Color**
- Near-black text (#1A1A1A–#222) on white or off-white (#FAFAF7). Contrast is ≥ 7:1 for body
  where possible (AAA).
- One link color, underlined in body text, plus a distinct visited state for docs and reference
  content.
- Color is never the only signal. Callouts (note, warning, danger) also carry an icon and a label.

**Components**
- Callout boxes for notes and warnings, tables with clear headers, figures with captions,
  footnotes or sidenotes, and a "last updated" date.
- Article header: title, a one-sentence summary, author, date, reading time. Only the facts that exist;
  never invent an author.
- Article footer: related links, "Was this helpful?" (docs) and prev/next (docs and series).
- Search in docs is prominent (⌘K/Ctrl+K).
- Anchor links on headings (copy link on hover).

**Forms in strict segments** (the GOV.UK patterns)
- **One thing per page** for long or complex flows. Each page asks one question with a clear heading.
- Labels are questions ("What is your email address?"). Hint text sits under the label, and the
  error summary at the top links to the fields.
- Big full-width inputs on mobile, and a single primary button ("Continue").
- No placeholder-as-label, no multi-column forms, no disabled submit buttons. Validate on
  submit and explain what is wrong.

**Motion and imagery**
- Almost none. Fades of 150–200ms for disclosure. No parallax, no autoplaying video.
- Images only when they inform: diagrams, screenshots, a hero image per article at most.
- Print stylesheet for articles, docs and legal pages.

**Performance and access**
- These pages must be the fastest on the site: server-rendered and text-first, with web fonts
  subset and preloaded or system fonts.
- Perfect semantics: `<article>`, `<nav aria-label>`, `<aside>`, `<time datetime>`, a skip link.
