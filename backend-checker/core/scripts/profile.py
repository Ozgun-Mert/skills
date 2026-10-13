"""Project profile for the performance check: scale, purpose, and whether hand-written algorithms are intended.

The architecture advice (section 4) depends on scale and domain, and the "use the built-in sort"
advice (section 2) is wrong for a course project that must implement algorithms by hand. The profile
is inferred from the code; anything that stays unclear is asked once and saved.

  python profile.py show --root .                # inferred values + open questions (JSON)
  python profile.py set --root . --answers '{"scale": "small", "handwritten_algorithms_intentional": false}'

Stored in docs/.backend-checks/profile.json. Keys:
  scale: "hobby" | "small" | "medium" | "large"   (expected users/traffic)
  purpose: free text, e.g. "restaurant ordering SaaS", "university algorithms assignment"
  handwritten_algorithms_intentional: true | false
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

LEARNING = re.compile(r"(?i)\b(homework|assignment|coursework|course project|university|ödev|odev|lab \d|exercise|kata|leetcode|"
                      r"learning project|tutorial|for learning|practice project|algorithms? (course|class))\b")
SCALE_WORDS = [("large", re.compile(r"(?i)\b(millions? of (users|requests)|high[- ]traffic|enterprise|kubernetes|k8s|autoscal\w*|sharding|multi[- ]region)\b")),
               ("medium", re.compile(r"(?i)\b(thousands of (users|requests)|saas|production|customers|b2b|subscription)\b")),
               ("hobby", re.compile(r"(?i)\b(hobby|toy|side project|personal project|demo|prototype|poc|proof of concept)\b"))]
DOMAIN_WORDS = re.compile(r"(?i)\b(restaurant|menu|e-?commerce|shop|store|payment|crypto|trading|stock|ai|machine learning|ml|llm|chat|"
                          r"game|iot|analytics|blog|cms|booking|reservation|delivery|education|health|fintech|social|streaming|video)\b")
QUESTIONS = {
    "scale": {"question": "How many users/requests do you expect for this backend in the next year?",
              "options": {"hobby": "Just me / a demo", "small": "Up to a few hundred users", "medium": "Thousands of users",
                          "large": "Tens of thousands or more, or heavy traffic"}},
    "handwritten_algorithms_intentional": {
        "question": "Are the hand-written algorithms (e.g. your own sort) intentional, like a course or learning project?",
        "options": {"false": "No: suggest the built-in versions", "true": "Yes: keep them hand-written, only suggest better algorithms"}},
}


def infer(root, index):
    texts = []
    for name in ("README.md", "readme.md", "README.rst", "README.txt"):
        t, _ = C.read_text(os.path.join(root, name))
        if t:
            texts.append(t[:20000])
    blob = "\n".join(texts) + " " + " ".join(d.get("name", "") for d in index.get("dependencies", []) if d.get("direct"))
    totals = index.get("totals", {})
    routes = sum(len(v) for v in index.get("hotspots", {}).get("routes", {}).values())
    inferred = {"lines_of_code": totals.get("lines"), "source_files": totals.get("source_files"), "route_lines": routes,
                "direct_dependencies": sum(1 for d in index.get("dependencies", []) if d.get("direct")),
                "domain_keywords": sorted({m.group(0).lower() for m in DOMAIN_WORDS.finditer(blob)})[:12],
                "learning_hints": sorted({m.group(0).lower() for m in LEARNING.finditer(blob)})[:6]}
    scale = None
    for label, rx in SCALE_WORDS:
        if rx.search(blob):
            scale = label
            break
    inferred["scale_guess"] = scale
    inferred["handwritten_guess"] = True if inferred["learning_hints"] else None
    return inferred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["show", "set"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--answers", help="JSON object with profile keys")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    path = C.state_path(root, "profile.json")
    prof = C.load_json(path, {}) or {}
    if a.command == "set":
        try:
            ans = json.loads(a.answers or "{}")
        except ValueError as e:
            print(json.dumps({"ok": False, "error": f"--answers is not valid JSON: {e}"}))
            return 1
        for k, v in ans.items():
            if isinstance(v, str) and v.lower() in ("true", "false"):
                v = v.lower() == "true"
            prof[k] = v
        prof["answered_at"] = C.now_iso()
        C.save_json(path, prof)
        print(json.dumps({"ok": True, "profile": prof}, ensure_ascii=False))
        return 0
    index = C.load_json(C.state_path(root, "index.json"), {}) or {}
    inferred = infer(root, index)
    open_q = []
    if "scale" not in prof and not inferred["scale_guess"]:
        open_q.append({"key": "scale", **QUESTIONS["scale"]})
    cands = (C.load_json(C.state_path(root, "perf-candidates.json"), {}) or {}).get("candidates", {})
    has_handwritten = bool(cands.get("handwritten_sort") or cands.get("recursion_no_memo"))
    inferred["handwritten_algorithm_candidates"] = len(cands.get("handwritten_sort", [])) + len(cands.get("recursion_no_memo", []))
    # Only worth a question when the answer changes advice: hand-written algorithms exist, or the README hints at a course.
    if "handwritten_algorithms_intentional" not in prof and (has_handwritten or inferred["learning_hints"]):
        open_q.append({"key": "handwritten_algorithms_intentional", **QUESTIONS["handwritten_algorithms_intentional"]})
    effective = {
        "scale": prof.get("scale") or inferred["scale_guess"] or "unknown",
        "purpose": prof.get("purpose") or (", ".join(inferred["domain_keywords"][:4]) or "unknown"),
        "handwritten_algorithms_intentional": prof.get("handwritten_algorithms_intentional",
                                                       inferred["handwritten_guess"] if inferred["handwritten_guess"] is not None else False),
        "source": "answered" if prof else "inferred",
    }
    print(json.dumps({"profile": effective, "inferred": inferred, "saved": prof, "open_questions": open_q}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
