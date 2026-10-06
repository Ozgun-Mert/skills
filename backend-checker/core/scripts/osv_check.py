"""Known vulnerabilities and end-of-life status for every dependency and the runtime (section 1a).

- One batch query to OSV.dev for all dependency@version pairs (1000 per request), then vulnerability
  details for each new id. Results are cached per package@version in osv-cache.json and refreshed
  after 7 days, so re-runs cost nothing.
- Runtime end-of-life from endoflife.date.
- Picks the closest non-vulnerable version for each package (same major when possible).
Only package names and versions leave the machine. Never source code.

Usage: python osv_check.py --root . [--plan docs/.backend-checks/plan-security.json] [--offline]
Writes docs/.backend-checks/deps.json and prints a compact summary.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/{}"
EOL = "https://endoflife.date/api/{}.json"
MAX_AGE = dt.timedelta(days=7)
UA = {"User-Agent": "backend-checker/1.0", "Content-Type": "application/json"}


def http_json(url, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=UA, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def vkey(v):
    v = str(v or "").lstrip("vV=")
    main, _, pre = re.split(r"[+]", v)[0].partition("-")
    nums = [int(x) for x in re.findall(r"\d+", main)[:4]]
    while len(nums) < 4:
        nums.append(0)
    return (nums, 0 if pre else 1, pre)


def lt(a, b):
    return vkey(a) < vkey(b)


def fixed_for(vuln, eco, name, current):
    """Smallest 'fixed' version above `current` in the range that contains it (None = no fix known)."""
    best = None
    affected_any = False
    for aff in vuln.get("affected", []):
        pkg = aff.get("package", {})
        if pkg.get("ecosystem", "").split(":")[0] != eco or pkg.get("name", "").lower() != name.lower():
            continue
        for rng in aff.get("ranges", []):
            if rng.get("type") not in ("SEMVER", "ECOSYSTEM"):
                continue
            intro, events = "0", rng.get("events", [])
            for ev in events:
                if "introduced" in ev:
                    intro = ev["introduced"]
                elif "fixed" in ev:
                    fx = ev["fixed"]
                    if not lt(current, intro) and lt(current, fx):
                        affected_any = True
                        if best is None or lt(fx, best):
                            best = fx
                elif "last_affected" in ev:
                    if not lt(current, intro) and not lt(ev["last_affected"], current):
                        affected_any = True
    return best, affected_any


def severity(v):
    ds = v.get("database_specific") or {}
    sev = ds.get("severity")
    if sev:
        return {"MODERATE": "Medium", "CRITICAL": "Critical", "HIGH": "High", "LOW": "Low", "MEDIUM": "Medium"}.get(str(sev).upper(), str(sev).title())
    for s in v.get("severity", []):
        m = re.search(r"CVSS:[0-9.]+/.*", s.get("score", ""))
        if m:
            return "see CVSS " + s["score"][:60]
    return None


def registry_info(v):
    """(recommended version exists?, latest published version) from the package registry; None when unknown."""
    eco, name, rec = v["ecosystem"], v["name"], v["recommended_version"]
    try:
        if eco == "npm":
            latest = http_json(f"https://registry.npmjs.org/{name.replace('/', '%2F')}/latest", timeout=15).get("version")
            exists = None
            if rec:
                try:
                    exists = bool(http_json(f"https://registry.npmjs.org/{name.replace('/', '%2F')}/{rec}", timeout=15).get("version"))
                except urllib.error.HTTPError:
                    exists = False
            return exists, latest
        if eco == "PyPI":
            j = http_json(f"https://pypi.org/pypi/{name}/json", timeout=20)
            return (rec in j.get("releases", {})) if rec else None, j.get("info", {}).get("version")
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return None, None


def check_runtime(runtime, errors):
    out = []
    today = dt.date.today()
    for r in runtime:
        prod, ver = r["product"], str(r["version"] or "")
        try:
            cycles = http_json(EOL.format(prod))
        except (urllib.error.URLError, OSError, ValueError) as e:
            errors.append(f"endoflife.date {prod}: {e}")
            out.append({**r, "eol": None, "error": "lookup failed"})
            continue
        parts = ver.split(".")
        cands = [".".join(parts[:2]), parts[0]] if prod not in ("nodejs", "eclipse-temurin", "amazon-corretto") else [parts[0]]
        cyc = next((c for c in cycles if str(c.get("cycle")) in cands), None)
        if not cyc:
            out.append({**r, "eol": None, "note": "cycle not found"})
            continue
        eol = cyc.get("eol")
        is_eol = eol is True or (isinstance(eol, str) and dt.date.fromisoformat(eol) <= today)
        supported = [str(c["cycle"]) for c in cycles
                     if not (c.get("eol") is True or (isinstance(c.get("eol"), str) and dt.date.fromisoformat(c["eol"]) <= today))]
        lts = [str(c["cycle"]) for c in cycles if c.get("lts") and str(c["cycle"]) in supported]
        out.append({**r, "cycle": cyc.get("cycle"), "eol": eol, "is_eol": is_eol, "latest_in_cycle": cyc.get("latest"),
                    "supported_cycles": supported[:6], "supported_lts": lts[:3]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    index = C.load_json(C.state_path(root, "index.json"))
    if not index:
        print(json.dumps({"error": "run index.py first"}))
        return 2
    cache_p = C.state_path(root, "osv-cache.json")
    cache = C.load_json(cache_p, {"pkgs": {}, "vulns": {}})
    now = dt.datetime.now().astimezone()
    deps = [d for d in index.get("dependencies", []) if d.get("name") and d.get("version") and d.get("ecosystem")]
    errors, network_ok = [], not a.offline

    def fresh(entry):
        try:
            return now - dt.datetime.fromisoformat(entry["checked_at"]) < MAX_AGE
        except (KeyError, ValueError):
            return False

    todo = [d for d in deps if not fresh(cache["pkgs"].get(f"{d['ecosystem']}|{d['name']}|{d['version']}", {}))]
    if todo and network_ok:
        for i in range(0, len(todo), 1000):
            chunk = todo[i:i + 1000]
            q = {"queries": [{"package": {"ecosystem": d["ecosystem"], "name": d["name"]}, "version": str(d["version"]).lstrip("v") if d["ecosystem"] != "Go" else d["version"]} for d in chunk]}
            try:
                res = http_json(OSV_BATCH, q, timeout=60)
            except (urllib.error.URLError, OSError, ValueError) as e:
                errors.append(f"OSV batch: {e}")
                network_ok = False
                break
            for d, r in zip(chunk, res.get("results", [])):
                ids = [v["id"] for v in r.get("vulns", []) or []]
                cache["pkgs"][f"{d['ecosystem']}|{d['name']}|{d['version']}"] = {"vulns": ids, "checked_at": now.isoformat(timespec="seconds")}
    need = sorted({vid for d in deps for vid in cache["pkgs"].get(f"{d['ecosystem']}|{d['name']}|{d['version']}", {}).get("vulns", [])
                   if vid not in cache["vulns"]})
    if need and network_ok:
        def get(vid):
            try:
                return vid, http_json(OSV_VULN.format(vid))
            except (urllib.error.URLError, OSError, ValueError) as e:
                return vid, {"error": str(e)}
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            for vid, v in ex.map(get, need):
                if "error" in v:
                    errors.append(f"OSV {vid}: {v['error']}")
                    continue
                cache["vulns"][vid] = {"summary": (v.get("summary") or v.get("details", "")[:160]).strip(), "aliases": v.get("aliases", [])[:4],
                                       "severity": severity(v), "affected": v.get("affected", []), "published": v.get("published", "")[:10]}
    C.save_json(cache_p, cache)

    vulnerable = []
    for d in deps:
        ent = cache["pkgs"].get(f"{d['ecosystem']}|{d['name']}|{d['version']}")
        if not ent or not ent.get("vulns"):
            continue
        vl, fixes, no_fix = [], [], False
        for vid in ent["vulns"]:
            v = cache["vulns"].get(vid)
            if not v:
                vl.append({"id": vid})
                continue
            fx, _ = fixed_for(v, d["ecosystem"], d["name"], d["version"])
            if fx:
                fixes.append(fx)
            else:
                no_fix = True
            cve = next((x for x in v["aliases"] if x.startswith("CVE-")), None)
            vl.append({"id": vid, "cve": cve, "severity": v["severity"], "summary": v["summary"][:140], "fixed_in": fx})
        rec = max(fixes, key=vkey) if fixes else None
        same_major = bool(rec) and vkey(rec)[0][0] == vkey(d["version"])[0][0]
        vulnerable.append({"ecosystem": d["ecosystem"], "name": d["name"], "version": d["version"], "direct": d.get("direct"),
                           "dev": d.get("dev", False), "manifest": d.get("manifest"), "approx_version": d.get("approx", False),
                           "recommended_version": rec, "same_major": same_major, "some_vulns_unfixed": no_fix, "vulns": vl})
    vulnerable.sort(key=lambda x: (not x["direct"], x["name"]))
    if network_ok:
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            for v, (exists, latest) in zip(vulnerable, ex.map(registry_info, vulnerable)):
                v["recommended_exists"] = exists
                v["latest_version"] = latest

    runtime = check_runtime(index.get("runtime", []), errors) if network_ok else index.get("runtime", [])
    out = {"checked_at": now.isoformat(timespec="seconds"), "network_ok": network_ok and not any(e.startswith("OSV batch") for e in errors),
           "dependencies_checked": len(deps), "vulnerable": vulnerable, "runtime": runtime, "errors": errors[:20]}
    C.save_json(C.state_path(root, "deps.json"), out)
    print(json.dumps({
        "deps_json": f"{C.STATE_DIR}/deps.json".replace("\\", "/"), "network_ok": out["network_ok"], "checked": len(deps),
        "vulnerable_direct": [f"{v['name']}@{v['version']} -> {v['recommended_version'] or 'no fix'}"
                              f"{' (not published!)' if v.get('recommended_exists') is False else ''} latest {v.get('latest_version') or '?'}"
                              for v in vulnerable if v["direct"]][:40],
        "vulnerable_transitive": len([v for v in vulnerable if not v["direct"]]),
        "runtime": [f"{r['product']} {r['version']}: {'EOL' if r.get('is_eol') else 'supported' if r.get('is_eol') is False else 'unknown'}" for r in runtime],
        "errors": errors[:5],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
