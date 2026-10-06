"""Find repeated code blocks (a tiny jscpd) to seed code-quality section 1.

Lines are normalized twice: "exact" (whitespace, string and number literals collapsed) and
"structural" (identifiers collapsed too, so the same logic with different names still matches).
Blocks of >= --min-lines meaningful lines that appear in 2+ places become clusters.

Usage: python dupes.py --root . [--plan docs/.backend-checks/plan-code-quality.json] [--min-lines 4]
Writes docs/.backend-checks/dupes.json. With --plan in incremental mode, only clusters that touch a
file being analyzed are kept.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

KEYWORDS = set("""if else for while return const let var function async await try catch finally throw new class
def elif in not and or is None True False null undefined true false import from export default switch case break
continue raise with as yield lambda pass self this super func go defer package struct interface type public private
protected static void int string bool float double long char""".split())
STR = re.compile(r"""(?:f|r|b)?("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)""")
NUM = re.compile(r"\b\d+(\.\d+)?\b")
IDENT = re.compile(r"\b[A-Za-z_$][\w$]*\b")
TRIVIAL = re.compile(r"^([{}()\[\];,]|end|else:?|try:?|pass|\}\s*else\s*\{|\}\)?;?|\]\)?;?|return;?|break;?|\)\s*\{?)$")
COMMENT = re.compile(r"^\s*(//|#|\*|/\*|\*/|<!--|--)")
IMPORT = re.compile(r"^\s*(import\b|from\s+\S+\s+import\b|const\s+\{?[\w\s,]*\}?\s*=\s*require\(|using\s|package\s|require\b)")


def normalize(line):
    s = line.strip()
    if not s or COMMENT.match(s) or IMPORT.match(s):
        return None, None
    s = re.sub(r"\s+//.*$|\s+#.*$", "", s)
    exact = NUM.sub("N", STR.sub("S", s))
    exact = re.sub(r"\s+", " ", exact)
    if TRIVIAL.match(exact) or len(exact) < 4:
        return None, None
    struct = IDENT.sub(lambda m: m.group(0) if m.group(0) in KEYWORDS else "I", exact)
    return exact, struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan")
    ap.add_argument("--min-lines", type=int, default=4)
    ap.add_argument("--max-clusters", type=int, default=40)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    index = C.load_json(C.state_path(root, "index.json"))
    plan = C.load_json(a.plan) if a.plan else None
    focus = {f["path"] for f in plan["files_to_analyze"]} if plan and plan.get("mode") == "incremental" else None
    K = a.min_lines

    seqs = {}
    for p, m in index["files"].items():
        if m.get("test") or m["lang"] in ("config", "sql", "prisma", "graphql"):
            continue
        text, _ = C.read_text(os.path.join(root, p))
        if not text:
            continue
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            e, s = normalize(line)
            if s:
                rows.append((i, e, s, line.strip()))
        if len(rows) >= K:
            seqs[p] = rows

    hashes = {p: [hash(tuple(r[2] for r in rows[i:i + K])) for i in range(len(rows) - K + 1)] for p, rows in seqs.items()}
    where = {}
    for p, hs in hashes.items():
        for i, h in enumerate(hs):
            where.setdefault(h, []).append((p, i))

    covered = set()
    clusters = []
    for p in sorted(hashes):
        hs = hashes[p]
        for i, h in enumerate(hs):
            if (p, i) in covered:
                continue
            occ, last = [], {}
            for (q, j) in where[h]:
                if q in last and j - last[q] < K:  # overlapping window in the same file
                    continue
                occ.append((q, j))
                last[q] = j
            if len(occ) < 2:
                continue
            L = K
            while True:
                nxt = [(q, j + L - K + 1) for q, j in occ]
                if any(n >= len(hashes[q]) for q, n in nxt):
                    break
                if len({hashes[q][n] for q, n in nxt}) != 1:
                    break
                if any(nxt[k][0] == occ[k + 1][0] and nxt[k][1] + K - 1 >= occ[k + 1][1] for k in range(len(occ) - 1)):
                    break
                L += 1
            for q, j in occ:
                for t in range(j, j + L - K + 1):
                    covered.add((q, t))
            locs = []
            for q, j in occ:
                rows = seqs[q]
                locs.append({"file": q, "start": rows[j][0], "end": rows[j + L - 1][0]})
            first = [r[1] for r in seqs[occ[0][0]][occ[0][1]:occ[0][1] + L]]
            exact = all([r[1] for r in seqs[q][j:j + L]] == first for q, j in occ)
            preview = [r[3][:100] for r in seqs[occ[0][0]][occ[0][1]:occ[0][1] + min(L, 4)]]
            clusters.append({"lines": L, "count": len(occ), "kind": "exact" if exact else "similar (names differ)",
                             "locations": locs, "preview": preview})

    clusters.sort(key=lambda c: -(c["lines"] * c["count"]))
    if focus is not None:
        clusters = [c for c in clusters if any(l["file"] in focus for l in c["locations"])]
    clusters = clusters[:a.max_clusters]
    C.save_json(C.state_path(root, "dupes.json"), {"min_lines": K, "clusters": clusters})
    print(json.dumps({"dupes_json": f"{C.STATE_DIR}/dupes.json".replace("\\", "/"), "clusters": len(clusters),
                      "top": [f"{c['lines']} lines x{c['count']} ({c['kind']}): " + ", ".join(f"{l['file']}:{l['start']}-{l['end']}" for l in c["locations"][:4])
                              for c in clusters[:8]]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
