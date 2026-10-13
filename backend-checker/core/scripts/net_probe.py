"""Where do the backend's dependencies live, and how far apart are they? (performance section 5)

1. Collects endpoints from config: URL-style values (DATABASE_URL, REDIS_URL, MONGO_URI, *_URL…) and
   *_HOST/*_PORT pairs in .env* files (untracked ones too: only scheme/host/port are kept, never
   credentials), docker-compose files and config files; plus region hints from IaC (fly.toml,
   render.yaml, vercel.json, serverless.yml, *.tf, app.yaml) and from managed-service hostnames.
2. Probes (skipped with --offline):
   - DNS for every host; geo-IP for public IPs with ONE batch call to ip-api.com (IPs only);
   - TCP connect time x3 per host:port (no protocol traffic, no login);
   - the project's public URL (--url given to index.py, or the detected one): GET-only timing
     (DNS / connect / TLS / first byte / total) on "/" x3 and one health path x3, max 8 requests.
3. Estimates the round trip between every pair of located endpoints from their distance.
Timings are measured from the user's machine; links between servers are judged by region.

Usage: python net_probe.py --root . [--plan …] [--offline]
Writes docs/.backend-checks/net.json and prints a compact summary.
"""
import argparse
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

URL_VALUE = re.compile(r"""(?i)\b((?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?|mssql|sqlserver|clickhouse|nats|kafka|https?)://[^\s'"`,;]+)""")
HOST_KEY = re.compile(r"""^\s*(?:export\s+)?([A-Z0-9_]*?)_?(HOST|HOSTNAME|SERVER|ADDR|ADDRESS)\s*[=:]\s*['"]?([A-Za-z0-9.\-]+)['"]?\s*$""")
PORT_KEY = re.compile(r"""^\s*(?:export\s+)?([A-Z0-9_]*?)_?PORT\s*[=:]\s*['"]?(\d{2,5})""")
KIND = [("postgres", "postgres"), ("mysql", "mysql"), ("mariadb", "mysql"), ("mongodb", "mongodb"), ("redis", "redis"), ("amqp", "rabbitmq"),
        ("mssql", "mssql"), ("sqlserver", "mssql"), ("clickhouse", "clickhouse"), ("nats", "nats"), ("kafka", "kafka"), ("http", "http")]
DEFAULT_PORT = {"postgres": 5432, "mysql": 3306, "mongodb": 27017, "redis": 6379, "rabbitmq": 5672, "mssql": 1433, "clickhouse": 8123,
                "nats": 4222, "kafka": 9092, "http": 80, "https": 443}
REGION_IN_HOST = re.compile(r"(?i)\b((?:us|eu|ap|sa|ca|me|af|il|mx)-(?:north|south|east|west|central|northeast|southeast|northwest|southwest)-\d)\b|"
                            r"\b(fra|ams|lhr|cdg|iad|sjc|sea|ord|dfw|lax|sin|nrt|syd|gru|bom|hkg|arn|waw|mad|otp|jnb)\d?\b")
IAC = [
    (re.compile(r"(^|/)fly\.toml$"), re.compile(r"""primary_region\s*=\s*["']([\w-]+)""")),
    (re.compile(r"(^|/)render\.ya?ml$"), re.compile(r"""region:\s*["']?([\w-]+)""")),
    (re.compile(r"(^|/)vercel\.json$"), re.compile(r""""regions"\s*:\s*\[\s*"([\w-]+)""")),
    (re.compile(r"(^|/)serverless\.ya?ml$"), re.compile(r"""region:\s*["']?([\w-]+)""")),
    (re.compile(r"\.tf$"), re.compile(r"""\b(?:region|location)\s*=\s*["']([\w-]+)""")),
    (re.compile(r"(^|/)app\.ya?ml$"), re.compile(r"""(?:region|location):\s*["']?([\w-]+)""")),
    (re.compile(r"(^|/)(railway|netlify)\.(json|toml)$"), re.compile(r"""region["']?\s*[:=]\s*["']([\w-]+)""")),
    (re.compile(r"(^|/)\.env[^/]*$"), re.compile(r"""^\s*(?:export\s+)?\w*REGION\w*\s*=\s*["']?([\w-]+)""", re.M)),
]
HEALTH_PATHS = ["/health", "/healthz", "/api/health", "/status"]
EDGE_HEADERS = ("server", "via", "cf-ray", "x-vercel-id", "fly-request-id", "x-amz-cf-pop", "x-served-by", "x-cache", "age",
                "cache-control", "content-encoding", "etag", "x-powered-by", "x-railway-edge", "x-render-origin-server")


def kind_of(scheme):
    s = scheme.lower()
    for k, v in KIND:
        if s.startswith(k):
            return "https" if s == "https" else v
    return s


def is_local(host):
    if host in ("localhost", "0.0.0.0") or host.endswith((".local", ".internal", ".localhost")) or "." not in host:
        return True  # bare names are docker-compose services / k8s services
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def candidate_files(root):
    out = []
    for d, dirs, files in os.walk(root):
        rel_d = C.rel(d, root)
        depth = 0 if rel_d == "." else rel_d.count("/") + 1
        dirs[:] = [x for x in dirs if x not in C.EXCLUDE_DIRS and (not x.startswith(".") or x in (".github",)) and depth < 3]
        for f in files:
            p = f if rel_d == "." else f"{rel_d}/{f}"
            if f.startswith(".env") or re.search(r"(?i)(docker-compose[^/]*|compose)\.ya?ml$|\.tf$|fly\.toml$|render\.ya?ml$|vercel\.json$|"
                                                 r"serverless\.ya?ml$|app\.ya?ml$|railway\.(json|toml)$|netlify\.toml$|"
                                                 r"(settings|config|database|db)\.(py|js|ts|json|ya?ml|toml)$|application[\w-]*\.(ya?ml|properties)$", f):
                out.append(p)
    return out[:200]


def collect(root):
    endpoints, hints = {}, []
    for p in candidate_files(root):
        text, _ = C.read_text(os.path.join(root, p), limit=500_000)
        if not text:
            continue
        hosts, ports = {}, {}
        for i, line in enumerate(text.splitlines(), 1):
            if len(line) > 2000 or line.strip().startswith(("#", "//")):
                continue
            key = re.match(r"^\s*(?:export\s+)?-?\s*([A-Za-z0-9_]+)\s*[=:]", line)
            for m in URL_VALUE.finditer(line):
                try:
                    u = urllib.parse.urlsplit(m.group(1))
                    host, port = u.hostname, u.port
                except ValueError:
                    continue
                if not host or "${" in m.group(1) or host in ("example.com", "user", "host"):
                    continue
                kind = kind_of(u.scheme)
                if kind in ("http", "https") and not (key and re.search(r"(?i)(api|service|search|elastic|backend|cache|queue|url)", key.group(1))):
                    continue
                port = port or DEFAULT_PORT.get(kind, 0)
                k = (host, port)
                endpoints.setdefault(k, {"name": key.group(1) if key else kind, "kind": kind, "host": host, "port": port,
                                         "sources": [], "local": is_local(host)})
                endpoints[k]["sources"].append(f"{p}:{i}")
            hm = HOST_KEY.match(line)
            if hm and not URL_VALUE.search(line):
                hosts[hm.group(1)] = (hm.group(3), i)
            pm = PORT_KEY.match(line)
            if pm:
                ports[pm.group(1)] = int(pm.group(2))
        for prefix, (host, i) in hosts.items():
            if host in ("0.0.0.0",) or re.match(r"^\d+$", host):
                continue
            guess = "redis" if "REDIS" in prefix else "postgres" if re.search(r"PG|POSTGRES|DB|DATABASE", prefix) else \
                    "mysql" if "MYSQL" in prefix else "mongodb" if "MONGO" in prefix else "smtp" if "SMTP" in prefix or "MAIL" in prefix else "service"
            port = ports.get(prefix) or DEFAULT_PORT.get(guess, 0)
            if not port:
                continue
            k = (host, port)
            endpoints.setdefault(k, {"name": f"{prefix}_HOST" if prefix else "HOST", "kind": guess, "host": host, "port": port,
                                     "sources": [], "local": is_local(host)})
            endpoints[k]["sources"].append(f"{p}:{i}")
        for fx, rx in IAC:
            if fx.search(p):
                for m in rx.finditer(text):
                    hints.append({"source": p, "region": m.group(1)})
    for e in endpoints.values():
        m = REGION_IN_HOST.search(e["host"])
        if m:
            e["region_from_hostname"] = (m.group(1) or m.group(2)).lower()
        e["sources"] = e["sources"][:4]
    seen, uniq = set(), []
    for h in hints:
        if (h["source"], h["region"]) not in seen:
            seen.add((h["source"], h["region"]))
            uniq.append(h)
    return list(endpoints.values()), uniq[:30]


def resolve(host):
    try:
        t = time.perf_counter()
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        ms = round((time.perf_counter() - t) * 1000, 1)
        ips = []
        for info in infos:
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
        return ips[:3], ms
    except OSError as e:
        return [], str(e)[:80]


def tcp_times(ip, port, n=3):
    out = []
    for _ in range(n):
        try:
            t = time.perf_counter()
            with socket.create_connection((ip, port), timeout=3):
                out.append(round((time.perf_counter() - t) * 1000, 1))
        except OSError as e:
            return {"error": type(e).__name__, "ok": out}
    return {"min_ms": min(out), "avg_ms": round(sum(out) / len(out), 1)}


def geo(ips):
    public = [ip for ip in ips if not is_local(ip)]
    res = {}
    if public:
        body = json.dumps([{"query": ip, "fields": "status,country,countryCode,regionName,city,lat,lon,isp,org,query"} for ip in public[:100]]).encode()
        req = urllib.request.Request("http://ip-api.com/batch", data=body, headers={"Content-Type": "application/json", "User-Agent": "backend-checker"})
        with urllib.request.urlopen(req, timeout=15) as r:
            for row in json.loads(r.read().decode()):
                if row.get("status") == "success":
                    res[row["query"]] = {k: row.get(k) for k in ("country", "countryCode", "regionName", "city", "lat", "lon", "isp", "org")}
    return res


def my_location():
    with urllib.request.urlopen(urllib.request.Request("http://ip-api.com/json/?fields=status,country,city,lat,lon,isp",
                                                       headers={"User-Agent": "backend-checker"}), timeout=10) as r:
        j = json.loads(r.read().decode())
    return {k: j.get(k) for k in ("country", "city", "lat", "lon", "isp")} if j.get("status") == "success" else None


def http_timing(url, path):
    """One GET with phase timings. Returns dict (ms) or {'error': …}."""
    u = urllib.parse.urlsplit(url)
    host, https = u.hostname, u.scheme == "https"
    port = u.port or (443 if https else 80)
    full_path = (u.path.rstrip("/") + path) or "/"
    t0 = time.perf_counter()
    try:
        ip = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)[0][4][0]
        t1 = time.perf_counter()
        sock = socket.create_connection((ip, port), timeout=10)
        t2 = time.perf_counter()
        if https:
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        t3 = time.perf_counter()
        sock.sendall(f"GET {full_path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: backend-checker/1.0 (latency probe)\r\n"
                     f"Accept: */*\r\nAccept-Encoding: gzip, br\r\nConnection: close\r\n\r\n".encode())
        first = sock.recv(65536)
        t4 = time.perf_counter()
        size = len(first)
        while size < 1_000_000:
            chunk = sock.recv(65536)
            if not chunk:
                break
            size += len(chunk)
        t5 = time.perf_counter()
        sock.close()
    except (OSError, ssl.SSLError, IndexError) as e:
        return {"path": path, "error": f"{type(e).__name__}: {str(e)[:80]}"}
    head = first.split(b"\r\n\r\n", 1)[0].decode("latin-1", "replace").split("\r\n")
    status = int(head[0].split()[1]) if len(head[0].split()) > 1 and head[0].split()[1].isdigit() else None
    headers = {}
    for h in head[1:]:
        if ":" in h:
            k, v = h.split(":", 1)
            if k.strip().lower() in EDGE_HEADERS:
                headers[k.strip().lower()] = v.strip()[:120]
    ms = lambda a, b: round((b - a) * 1000, 1)  # noqa: E731
    return {"path": path, "status": status, "ip": ip, "dns_ms": ms(t0, t1), "connect_ms": ms(t1, t2), "tls_ms": ms(t2, t3) if https else 0,
            "ttfb_ms": ms(t3, t4), "total_ms": ms(t0, t5), "bytes": size, "headers": headers}


def probe_domain(url):
    runs, used = [], 0
    for _ in range(3):
        runs.append(http_timing(url, "/"))
        used += 1
    for hp in HEALTH_PATHS:
        if used >= 8:
            break
        r = http_timing(url, hp)
        used += 1
        if r.get("status") and r["status"] < 400:
            runs.append(r)
            for _ in range(2):
                if used < 8:
                    runs.append(http_timing(url, hp))
                    used += 1
            break
    ok = [r for r in runs if "error" not in r]
    summary = {}
    for path in sorted({r["path"] for r in ok}):
        rs = [r for r in ok if r["path"] == path]
        summary[path] = {k: round(sum(r[k] for r in rs) / len(rs), 1) for k in ("dns_ms", "connect_ms", "tls_ms", "ttfb_ms", "total_ms")}
        summary[path]["status"] = rs[-1]["status"]
    return {"url": url, "requests": used, "runs": runs, "avg_by_path": summary,
            "edge_headers": next((r["headers"] for r in ok), {}), "ip": next((r["ip"] for r in ok), None)}


def endpoint_status(e, offline):
    if e["local"]:
        return "(local)"
    if offline:
        return "(not probed: offline)" + (f" region {e['region_from_hostname']}" if e.get("region_from_hostname") else "")
    if not e.get("ips"):
        return f"(DNS failed: {e.get('dns_ms')})" + (f" region {e['region_from_hostname']}" if e.get("region_from_hostname") else "")
    g = e.get("geo", {})
    tcp = e.get("tcp", {})
    return f"{g.get('city', '?')},{g.get('countryCode', '?')} tcp " + (f"{tcp['avg_ms']}ms" if "avg_ms" in tcp else tcp.get("error", "?"))


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(h)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    index = C.load_json(C.state_path(root, "index.json"), {})
    url = index.get("project_url") or index.get("detected_url")
    endpoints, hints = collect(root)
    notes, errors = [], []
    out = {"checked_at": C.now_iso(), "offline": a.offline, "measured_from": None, "url": url,
           "url_source": "argument" if index.get("project_url") else ("detected" if url else None),
           "endpoints": endpoints, "region_hints": hints, "domain": None, "pairs": [], "notes": notes, "errors": errors}
    if not endpoints and not hints and not url:
        notes.append("No hosts, regions or public URL found in config. Section 5 has nothing to measure.")
    if not a.offline:
        for e in endpoints:
            if e["local"]:
                e["note"] = "local / docker-compose / private host: runs next to the app or on a private network"
                continue
            ips, dns = resolve(e["host"])
            e["ips"], e["dns_ms"] = ips, dns
            if ips:
                e["tcp"] = tcp_times(ips[0], e["port"])
        if url:
            try:
                out["domain"] = probe_domain(url)
            except Exception as ex:  # noqa: BLE001
                errors.append(f"domain probe: {ex}")
        ips = [e["ips"][0] for e in endpoints if e.get("ips")] + ([out["domain"]["ip"]] if out.get("domain") and out["domain"].get("ip") else [])
        try:
            g = geo(ips)
            for e in endpoints:
                if e.get("ips") and e["ips"][0] in g:
                    e["geo"] = g[e["ips"][0]]
            if out.get("domain") and out["domain"].get("ip") in g:
                out["domain"]["geo"] = g[out["domain"]["ip"]]
            out["measured_from"] = my_location()
        except Exception as ex:  # noqa: BLE001
            errors.append(f"geo-IP lookup: {ex}")
        located = [(e["name"], e["geo"]) for e in endpoints if e.get("geo")]
        if out.get("domain") and out["domain"].get("geo"):
            located.append(("public URL (" + url + ")", out["domain"]["geo"]))
        for i in range(len(located)):
            for j in range(i + 1, len(located)):
                d = km(located[i][1], located[j][1])
                out["pairs"].append({"a": located[i][0], "b": located[j][0], "distance_km": d,
                                     "est_rtt_ms": round(d / 100 + 1, 1)})  # light in fibre ≈ 200 km/ms one way
        if out.get("domain") and out["domain"].get("edge_headers", {}).get("cf-ray") or \
                (out.get("domain") and any(k in out["domain"].get("edge_headers", {}) for k in ("x-vercel-id", "x-amz-cf-pop"))):
            notes.append("The public URL is behind a CDN/edge network: its geo-IP is the edge, not the origin server.")
    C.save_json(C.state_path(root, "net.json"), out)
    print(json.dumps({
        "net_json": f"{C.STATE_DIR}/net.json".replace("\\", "/"), "offline": a.offline, "url": url,
        "endpoints": [f"{e['name']} {e['kind']} {e['host']}:{e['port']} " + endpoint_status(e, a.offline) for e in endpoints][:20],
        "region_hints": [f"{h['region']} ({h['source']})" for h in hints][:10],
        "domain": {p: v for p, v in (out["domain"] or {}).get("avg_by_path", {}).items()} if out.get("domain") else None,
        "pairs": [f"{p['a']} <-> {p['b']}: {p['distance_km']} km, ~{p['est_rtt_ms']} ms RTT" for p in out["pairs"]][:10],
        "notes": notes, "errors": errors[:5],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
