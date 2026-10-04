# State file: `seo/seo-plan.json` + `seo/seo-plan.md`

The state lets later runs continue instead of starting over: no duplicate pages, no keyword
cannibalization, no repeated questions. It lives in `/seo/` (or the folder recorded in
`state_dir`), which is gitignored because it holds working notes, not site code.

Write the JSON first, then render the Markdown from it. Update both at the end of every phase that
changes something, not only at the very end, so an interrupted run still leaves a usable state.

## seo-plan.json

```json
{
  "schema_version": 1,
  "state_dir": "seo",
  "updated_at": "2026-10-04T14:20:00Z",
  "runs": [
    { "date": "2026-10-04", "arguments": "['qr menü', 'karekod menü']", "mode": "A",
      "serp_source": "google-browser | websearch-fallback", "summary": "Planned 6 pages, built 5" }
  ],
  "project": {
    "name": "Brand", "type": "product | personal | local-business",
    "stack": "nextjs-app", "rendering": "ssg | ssr | csr | static-html",
    "site_url": "https://example.com | {{PLACEHOLDER: site_url}}",
    "languages": ["tr"], "country": "TR", "region": "İstanbul / Nişantaşı | null",
    "backend_paths": ["app/api/**", "prisma/**"],
    "ask_before_touching": ["middleware.ts", "next.config.mjs"]
  },
  "facts": {
    "confirmed_capabilities": ["Menus update instantly without reprinting QR"],
    "denied_capabilities": ["Online ordering"],
    "answers": { "show_prices": "no", "has_blog": "yes" }
  },
  "words": [
    { "word": "qr menü", "source": "user | agent-approved", "status": "approved | rejected" }
  ],
  "keywords": [
    { "keyword": "qr menü nedir", "parent": "qr menü", "intent": "informational",
      "page": "/blog/qr-menu-nedir", "role": "primary | secondary" }
  ],
  "pages": [
    { "path": "/blog/qr-menu-nedir", "file": "app/blog/qr-menu-nedir/page.tsx",
      "type": "blog", "primary_keyword": "qr menü nedir",
      "secondary_keywords": ["qr menü nasıl çalışır"], "intent": "informational",
      "status": "planned | approved | built | changed | rejected",
      "legal": false, "legal_decision": "yes | yes-with-banner | no | null", "banner": false,
      "last_changed": "2026-10-04" }
  ],
  "rejected": [
    { "path": "/fiyatlar", "keyword": "qr menü fiyatları", "reason": "User does not show prices publicly", "date": "2026-10-04" }
  ],
  "placeholders": [
    { "name": "phone", "files": ["app/iletisim/page.tsx", "app/layout.tsx"], "needed": "Public phone number in +90 format", "status": "open | filled" }
  ],
  "issues_for_user": [
    { "type": "redirect | status | https | www | backend | config", "url": "http://example.com/",
      "detail": "http does not redirect to https", "found": "2026-10-04", "status": "open | resolved" }
  ],
  "pending_checks": [
    { "check": "core-web-vitals", "reason": "site not deployed", "how": "re-run /optimize-seo verification after deploy" }
  ],
  "suggestions": [
    { "idea": "Public indexable menu page per restaurant", "why": "Long-tail '<restaurant> menü' searches", "status": "suggested | accepted | declined" }
  ],
  "research": [ { "keyword": "qr menü", "file": "seo/research/qr-menu.md", "date": "2026-10-04" } ]
}
```

## seo-plan.md (readable by people)

```markdown
# SEO plan: <Brand>
_Last updated: <date> · Site: <url> · Languages: <tr> · Market: <TR / İstanbul>_

## Words
| Word | Source | Status |

## Page map
| Path | Type | Primary keyword | Secondary | Intent | Status |

## Rejected (won't be proposed again)
| Path / keyword | Reason | Date |

## Open placeholders
| Placeholder | Where | What's needed |

## Issues for you (backend / server / hosting)
| Issue | URL | Detail |

## Pending checks
- …

## Suggestions
- …

## Run history
- <date>: mode <A/B/C>, <summary>
```
