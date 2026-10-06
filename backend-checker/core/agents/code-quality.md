# Code quality agent → `docs/CODE_QUALITY.md`

Follow `agent-contract.md` (inputs, JSON output, validation, return line). This brief is your checklist.
Check id: `code-quality`. Use the section ids below exactly.

## Purpose and limits

Make the backend **easier to read and easier to extend**. You don't judge business logic or security:
the security agent covers those, so skip them even when you notice them. You **write no code**. Every
`fix` is a short plan, given as a list of steps:
- **what** to extract;
- **what to name it** and its inputs/outputs in words;
- **where** it lives (file/folder);
- **which call sites** move to it;
- **in what order** to do it so the app keeps working between steps.

Each finding has `impact` (High/Medium/Low: how much easier reading or changing gets) and `effort`
(S: under an hour, M: up to a day, L: more). One finding per problem: put the other occurrences in
`locations`. Use `group` to tie findings that belong to one refactor (e.g. `payment-providers`).

## Work order

1. Read your plan, then load the code (contract, "Inputs" step 2).
2. Read the script candidates:
   - `docs/.backend-checks/dupes.json`: duplicate clusters;
   - `docs/.backend-checks/quality-candidates.json`: long functions/files, nesting, magic values,
     unused exports/deps, commented-out code, weak types.

   They're hints with false positives and gaps. Confirm each against the code, and also report what
   the scripts can't see (similar logic written differently).
3. Go through the sections below, write `findings-code-quality.new.json`, validate, return the summary line.

In incremental mode, sections 1, 5, 7, 8 and 10 may be in `rerun_sections` (whole scope). Otherwise
limit yourself to `files_to_analyze`.

## Sections

### 1. Repetitive code
- **What counts:** the same or similar logic in more than one place that could be one function with
  different inputs, e.g.:
  - the same role check in many handlers;
  - the same response mapping;
  - copy-pasted provider branches;
  - repeated pagination or validation;
  - the same query with a different filter.
- **What to report:** every location.
- **The plan describes the new function:** name, parameters (what varies between the copies becomes
  a parameter), return value, the module it goes in, which call sites switch to it, and in what order.
  Prefer existing helpers or middleware layers when the code already has them.

### 2. Interfaces / typed input contracts
- **What counts:** function inputs not described by a named, reusable type. Untyped `dict`/`any`/
  `object` payloads, long positional parameter lists, ad-hoc object shapes repeated across functions.
- **Why it matters:** with a named contract, a higher-level function can extend it (e.g.
  `CreateOrderInput` → `CreatePaidOrderInput extends CreateOrderInput`) instead of re-listing fields.
- **What the contract should be per language:**
  - TS: `interface`/`type`;
  - Python: dataclass, Pydantic model, `TypedDict` or `Protocol`;
  - Go: interfaces/structs;
  - Java/C#: interface/DTO record.
- **Plain JS:** suggest JSDoc `@typedef` and `@param` types. Mention a TypeScript migration only as an
  optional roadmap item (one finding, effort L).
- **Plan:** the contract's name, its fields, where it lives (shared types path if one was given), and
  which functions take it.

### 3. Extensibility (adding a new variant)
- **What to look for:** places where adding one new variant means editing many places. Find
  `switch`/`if-elif` chains on a type/kind/method/provider/channel/role (`type_switch` hotspots), e.g.:
  - payment methods/providers;
  - notification channels;
  - storage, auth or shipping providers;
  - export formats, user roles, file types.
- **Example:** adding a new payment method shouldn't require rewriting the payment system.
- **The plan proposes a strategy/registry/adapter:**
  1. the common contract (e.g. `PaymentProvider { charge(input), refund(input) }`);
  2. one module per variant;
  3. a registry/map keyed by the variant name, so a new variant is one new file plus one registry line;
  4. how callers pick the variant;
  5. migration steps, one variant at a time.
- Also flag the same variant list written out in several places (enum values duplicated as strings).

### 4. Long functions, long files, deep nesting
- **Thresholds (rough):** function over 50 lines, file over 400 lines, nesting deeper than 3.
- **What to report:** each one, with how to split it: which steps become named helpers, and what
  moves to which file. For nesting, suggest guard clauses/early returns and extracting the inner block.
- **Route handlers** that do validation + business logic + DB + response formatting in one body
  count here. Propose a validation step, a service function and a mapper, without redesigning the
  whole architecture.

### 5. Dead code
Each with "safe to delete?" reasoning:
- unused exports, functions and files;
- unused dependencies (from `quality-candidates.json`; verify there's no dynamic import or CLI use);
- commented-out code blocks;
- unreachable branches;
- feature flags that are always on.

### 6. Magic numbers and strings
- **What counts:** unexplained literals with business meaning, e.g.:
  - tax rates, fees, limits, timeouts, page sizes;
  - status names, role names, provider names;
  - especially the same literal repeated across files.
- **Plan:** constant/enum name, where it lives (constants module or config/env for
  deployment-specific values), and the call sites to update.
- **Skip:** obvious values (0, 1, HTTP status codes in their natural place).

### 7. Error-handling consistency
- **What counts:** mixed styles, e.g.:
  - throwing vs returning `{error}` vs `res.status()` scattered around;
  - `HTTPException` in some places and dicts in others;
  - swallowed errors;
  - `print` instead of a logger;
  - no central handler.
- **Plan:** a small set of error classes (`NotFoundError`, `ValidationError`, `ConflictError`…), one
  central error handler/middleware that maps them to responses, and the order to migrate call sites.

### 8. API response & naming consistency
- **Response shapes:** different per endpoint (`{data, page}` vs a bare array vs `{result}`).
- **Mixed casing in JSON** (`inStock` vs `in_stock`).
- **Mixed naming:** files (`userRoutes.js` vs `order-routes.js`), functions and route paths.
- **Plan:** propose the convention that matches the majority, plus where to enforce it (a shared
  response helper or serializer).

### 9. Hardcoded dependencies / testability
- **What counts:** modules that create their own DB clients, SDK clients, SMTP connections, clocks
  (`Date.now()`/`datetime.now()` inside logic) or env reads deep inside logic, so tests can't swap
  them.
- **Plan:** pass them as parameters, constructor or factory arguments, or use the framework's DI
  (`Depends`, Nest providers); create them once in a composition root.

### 10. Weak and duplicated types
- **Weak types:** `any`/untyped values, missing return types on exported functions, `dict`/`Any`
  everywhere.
- **Duplicated types:** types defined separately in backend, frontend and shared code that should
  live once in the shared path. Only when a shared/frontend path was given: use the `types`
  extra_hotspots.
- **Plan:** where the single source of truth goes and how both sides import it.

## Finish with the roadmap fields
You don't write the roadmap: the renderer orders all findings by impact ÷ effort and groups them by
`group`. Your part is setting `impact`, `effort` and `group` carefully.
