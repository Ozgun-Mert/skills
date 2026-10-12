"""Find the files that most likely describe the PROJECT and the BACKEND contract (FRONTEND.md).

Scans every .md / .txt / .markdown file under --root (skipping node_modules, .git, DESIGN, build
output, …) and scores each one for two roles:
  backend  – how the frontend should call the backend: endpoints, HTTP verbs, request/response
             bodies, base URL, auth, status codes, websockets, GraphQL
  project  – what the project is and does: overview, goals, users, features, pages, user stories
Turkish keywords count too. The agent still reads the top candidates and judges; the score only
orders them.

Usage: python find_docs.py --root . [--top 5] [--min-score 4]
Prints JSON: {"backend": [...], "project": [...], "exact": {...}, "scanned": N}
"""
import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SKIP_DIRS, utf8_stdout  # noqa: E402

EXTS = {".md", ".txt", ".markdown"}
MAX_BYTES = 400_000
NEGATIVE_NAMES = re.compile(r"^(license|licence|changelog|history|code_of_conduct|contributing|"
                            r"security|authors|notice|third.party|requirements|robots)\b", re.I)

BACKEND = [
    (r"\b(GET|POST|PUT|PATCH|DELETE)\s+[`'\"]?/[\w{}:/.-]*", 4.0),
    (r"(?<![\w.])/api/[\w{}:/.-]+", 2.5),
    (r"\bendpoints?\b|\buç ?noktas", 2.0),
    (r"\b(request|response)\s+(body|schema|payload|example|format)\b", 2.5),
    (r"\b(request|response|istek|yanıt|cevap)\b", 0.6),
    (r"\bbase[ _-]?url\b|\bAPI_URL\b|\bVITE_API|\bNEXT_PUBLIC_API", 3.0),
    (r"\b(authorization|bearer|jwt|access[ _]token|refresh[ _]token|api[ _-]?key|cookie)\b", 1.2),
    (r"\b(200|201|204|400|401|403|404|409|422|500)\b\s*(ok|created|bad request|unauthorized|"
     r"forbidden|not found|conflict)?", 0.5),
    (r"\b(openapi|swagger|graphql|websocket|socket\.io|grpc|rest api|webhook)\b", 2.0),
    (r"\bquery (param|string)|\bpath param|\bheaders?\b", 0.8),
    (r"\bcontent-type\b|application/json", 1.5),
    (r"```(json|http)", 1.5),
    (r"\bpagination\b|\bpage_size\b|\blimit\b.*\boffset\b|\bcursor\b", 0.5),
    (r"\bfrontend\b.*\b(call|fetch|request|consume)|\b(fetch|axios)\(", 1.5),
]
PROJECT = [
    (r"^#\s+\S", 0.5),
    (r"\b(overview|about( the| this)? (project|app|product)|introduction|genel bakış|hakkında)\b", 2.5),
    (r"\b(this|the) (project|app|application|platform|product|website|site|tool) "
     r"(is|lets|allows|helps|will|aims)\b", 3.0),
    (r"\bbu (proje|uygulama|platform|site|ürün)\b", 3.0),
    (r"\b(goals?|purpose|mission|vision|problem|solution|amaç|hedef|vizyon|problem|çözüm)\b", 1.2),
    (r"\b(features?|özellik(ler)?|functionality|capabilities)\b", 1.5),
    (r"\b(users?|customers?|audience|personas?|roles?|kullanıcı|müşteri|hedef kitle)\b", 0.8),
    (r"\b(user stor(y|ies)|as an? \w+, I want|use cases?|kullanım senaryo)", 2.5),
    (r"\b(pages?|screens?|sayfa|ekran)\b", 0.6),
    (r"\b(mvp|roadmap|scope|requirements?|gereksinim|kapsam)\b", 1.0),
    (r"\b(pricing|business model|subscription|abonelik|fiyat)\b", 0.6),
]
NAME_BONUS = {
    "backend": [(r"^frontend\.(md|txt)$", 25), (r"(api|endpoints?|backend|contract|integration|"
                r"server|routes)", 6), (r"(readme)", 0.5)],
    "project": [(r"^project\.(md|txt)$", 25), (r"(project|overview|about|brief|spec|prd|"
                r"requirements|idea|product|proje)", 6), (r"^readme\.(md|txt|markdown)$", 3)],
}


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in EXTS:
                yield os.path.join(dirpath, fn)


def score(text, rules):
    total, hits = 0.0, {}
    for pat, w in rules:
        n = len(re.findall(pat, text, re.I | re.M))
        if n:
            # diminishing returns: the 20th endpoint matters less than the 2nd
            total += w * (1 + math.log(n))
            hits[pat[:40]] = n
    return total, hits


def first_heading(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()[:120]
        if s:
            return s[:120]
    return ""


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--min-score", type=float, default=4.0)
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    rows, exact, scanned = [], {}, 0
    for path in walk(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        name = os.path.basename(path).lower()
        if NEGATIVE_NAMES.match(name):
            continue
        try:
            if os.path.getsize(path) > MAX_BYTES:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        scanned += 1
        if name in ("frontend.md", "frontend.txt"):
            exact["frontend"] = rel
        if name in ("project.md", "project.txt"):
            exact["project"] = rel
        row = {"path": rel, "bytes": len(text.encode("utf-8")), "title": first_heading(text)}
        for role, rules in (("backend", BACKEND), ("project", PROJECT)):
            s, hits = score(text, rules)
            for pat, bonus in NAME_BONUS[role]:
                if re.search(pat, name, re.I):
                    s += bonus
                    break
            # README of a dependency deep in the tree is rarely the project brief
            depth = rel.count("/")
            s -= 1.5 * max(0, depth - 1)
            row[role] = round(s, 1)
            row[role + "_signals"] = dict(sorted(hits.items(), key=lambda kv: -kv[1])[:5])
        rows.append(row)

    def pick(role):
        ranked = sorted((r for r in rows if r[role] >= a.min_score), key=lambda r: -r[role])
        return [{"path": r["path"], "score": r[role], "title": r["title"], "bytes": r["bytes"],
                 "signals": r[role + "_signals"]} for r in ranked[:a.top]]

    out = {"root": root, "scanned": scanned, "exact": exact,
           "backend": pick("backend"), "project": pick("project")}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
