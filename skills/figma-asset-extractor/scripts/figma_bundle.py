#!/usr/bin/env python3
"""figma_bundle.py — turns a Figma file into a design bundle an AI can use directly for implementation.

  figma_bundle.py probe  --url <figma URL>                 check token/access + list pages (screen counts)
  figma_bundle.py fetch  --url <figma URL> --out <bundle> [--pages 8:880,13:5459] [--resume]
                                                           download raw JSON, images, renders, and icon SVGs to disk via REST
  figma_bundle.py fetch-urls --list <urls.json> --out <bundle>  (MCP fallback) download and save a list of temporary URLs
  figma_bundle.py build  --out <bundle>                      raw/ → tokens·components·screens·manifest·README
  figma_bundle.py check  --out <bundle>                      completeness check (0 pass · 1 defects · 2 cannot decide)
  figma_bundle.py --self-test                              self-verify build and check against a fixture

The token is read only from the FIGMA_TOKEN environment variable or ~/.config/figma/token (a read-only personal access token). It is never written to output or logs.
Uses only the python3 standard library — consumer projects are not asked to pip install anything.

Exit codes: 0 success · 1 defect (check) or request failure · 2 cannot decide (no token · no input · offline)
"""
import argparse, colorsys, hashlib, json, os, re, shutil, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict

API = "https://api.figma.com/v1"
RENDER_BATCH = 10      # requesting 40 images at once for a large screen (393×852 @2x, many images) made Figma drop the connection with no response (measured) — on failure, split in half
TOKEN_COVERAGE = 0.95  # tokens are the values up to 95% cumulative usage. The remaining tail is one-off values — flagged to be snapped to the nearest token
# A file drawn without a token system ends up with 133 colors and 178 fonts at 95% cumulative coverage (Orangetopia, measured) — that is drift, not tokens.
# So each kind gets a cap. The values come from the usual scale of real design systems (a palette of about 20 colors, a type scale of about 10 steps).
TOKEN_CAP = {"color": 24, "text-color": 12, "stroke": 8, "font": 16, "radius": 8, "spacing": 12, "shadow": 6, "gradient": 6}
COLOR_MERGE = 10       # an RGB distance of 10 or less merges into the same color — hand drift the eye cannot tell apart, like #F27321/#F26C1D
CANDIDATE_MIN = 3      # the same non-component structure appearing 3 or more times is a candidate (2 is often a coincidence)
ICON_MAX = 48          # only icon-like instances at or below this size (px) are extracted as SVG — anything larger is treated as an illustration
GENERIC = re.compile(r"^(Component|Frame|Group|Rectangle|Instance|Property \d)\b|^\d+$", re.I)
AUTO_NAME = re.compile(r"^(Group|Rectangle|Frame|Ellipse|Vector|Line|Union|Subtract|Intersect|Polygon|Star|image|ChatGPT Image|Screenshot)\b", re.I)


def die(msg, code=1):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(code)


# ── input ─────────────────────────────────────────────────────────────
def parse_url(url):
    m = re.search(r"figma\.com/(design|file|board|slides|make)/([0-9A-Za-z]{22,128})(?:/branch/([0-9A-Za-z]+))?", url or "")
    if not m:
        die("Not a Figma URL — it must look like https://www.figma.com/design/<fileKey>/...", 2)
    if m.group(1) != "design" and m.group(1) != "file":
        die(f"{m.group(1)} files are not supported — only Design files have screens and components", 2)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    node = (q.get("node-id") or [None])[0]
    return (m.group(3) or m.group(2)), (node.replace("-", ":") if node else None)


TOKEN_FILE = os.path.expanduser("~/.config/figma/token")   # outside the project — a place that cannot be committed


def token():
    """FIGMA_TOKEN env var → ~/.config/figma/token, in that order. Claude Code's Bash does not carry shell state over,
    so an `export` made during a conversation does not survive to the next command — hence one file in the user's home as the second source."""
    t = os.environ.get("FIGMA_TOKEN", "").strip()
    if not t and os.path.exists(TOKEN_FILE):
        t = open(TOKEN_FILE).read().strip()
    if not t:
        print("no-token — no Figma token. Take the fallback (MCP) path, or have the user place a token themselves:\n"
              "  Figma → Settings → Security → Personal access tokens → File content: Read-only\n"
              f"  In a terminal: mkdir -p ~/.config/figma && (read -rs T && printf %s \"$T\" > {TOKEN_FILE}) && chmod 600 {TOKEN_FILE}\n"
              "  (never write the token in chat, project files, or command-line arguments)", file=sys.stderr)
        sys.exit(2)
    return t


def api(path, tok, params=None, tries=4, soft=False):
    url = f"{API}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    for i in range(tries):
        req = urllib.request.Request(url, headers={"X-Figma-Token": tok})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                wait = int(e.headers.get("Retry-After", "0") or 0) or 2 ** (i + 2)
                print(f"  … rate limit (429) — retrying in {wait}s", file=sys.stderr)
                time.sleep(min(wait, 120))
                continue
            if soft and e.code >= 500:
                return None
            body = e.read().decode("utf-8", "replace")[:300]
            hint = {403: "check the token permission (File content: Read) or the file sharing permission",
                    404: "the file key is wrong or this token's account cannot see the file"}.get(e.code, "")
            die(f"Figma API {e.code} {path} — {hint} {body}")
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            # when a render is heavy the server drops the connection with no response (RemoteDisconnected) — treat it as a transient error and retry
            if i < tries - 1:
                print(f"  … connection error ({type(e).__name__}) — retrying in {2 ** (i + 2)}s", file=sys.stderr)
                time.sleep(2 ** (i + 2)); continue
            if soft:
                return None
            die(f"network error — if offline, cannot decide: {getattr(e, 'reason', e)}", 2)


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for i in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            return True
        except Exception as e:  # temporary URL expired or transient error — retry, then report the failure as a list
            if i == 2:
                print(f"  ! download failed {os.path.basename(dest)}: {e}", file=sys.stderr)
    return False


def sniff_ext(path):
    with open(path, "rb") as f:
        h = f.read(12)
    if h.startswith(b"\x89PNG"): return "png"
    if h[:3] == b"\xff\xd8\xff": return "jpg"
    if h[:4] == b"GIF8": return "gif"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP": return "webp"
    if h.lstrip().startswith(b"<"): return "svg"
    return "bin"


# ── tree utilities ──────────────────────────────────────────────────
def walk(n, fn, depth=0, parent=None):
    if n.get("visible") is False:
        return
    fn(n, depth, parent)
    for c in n.get("children", []) or []:
        walk(c, fn, depth + 1, n)


def screens_of(canvas):
    """A FRAME directly under a page (or SECTION) is a screen — any other top-level node is a note or reference material on the board."""
    out = []
    for n in canvas.get("children", []):
        if n.get("visible") is False:
            continue
        if n["type"] == "SECTION":
            out += [(c, n.get("name")) for c in n.get("children", []) if c["type"] == "FRAME" and c.get("visible") is not False]
        elif n["type"] == "FRAME":
            out.append((n, None))
    return out


def hexc(c, opacity=1.0):
    a = c.get("a", 1) * (opacity if opacity is not None else 1)
    h = "#" + "".join(f"{round(c[k] * 255):02X}" for k in "rgb")
    return h if a >= 0.995 else f"{h}/{round(a * 100)}"


def slug(s, fallback="x"):
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", (s or "").strip()).strip("-").lower()
    return s[:60] or fallback


def font_key(st):
    """A type token's identity is font family, weight, and size. Adding line height and letter spacing splits a hand-drawn file into hundreds of combinations (measured: 360)."""
    return f"{st.get('fontFamily')}|{st.get('fontWeight')}|{round(st.get('fontSize', 0), 1)}"


def font_detail(st):
    lh = st.get("lineHeightPx")
    lh = "auto" if st.get("lineHeightUnit") == "INTRINSIC_%" or lh is None else round(lh, 1)
    return f"lh {lh} ls {round(st.get('letterSpacing', 0), 2)}"


def sig(n, d=0):
    """Structural signature — only type, auto-layout direction, and child structure. Text and color are left out (to group the same button that differs only in its label)."""
    kids = [c for c in n.get("children", []) or [] if c.get("visible") is not False]
    if d > 3 or not kids or n["type"] == "INSTANCE":
        return n["type"][0] + (":" + n.get("componentId", "") if n["type"] == "INSTANCE" else "")
    lm = n.get("layoutMode")
    return n["type"][0] + (lm[0] if lm and lm != "NONE" else "") + "(" + ",".join(sig(c, d + 1) for c in kids) + ")"


VECTORS = ("VECTOR", "BOOLEAN_OPERATION", "STAR", "POLYGON", "LINE", "ELLIPSE", "REGULAR_POLYGON")


def vector_only(n):
    kids = [c for c in n.get("children", []) or [] if c.get("visible") is not False]
    return bool(kids) and all(c["type"] in VECTORS or (c["type"] in ("FRAME", "GROUP") and vector_only(c)) for c in kids)


def icon_key(n):
    bb = n.get("absoluteBoundingBox") or {}
    return f"vec:{n.get('name')}:{round(bb.get('width', 0))}x{round(bb.get('height', 0))}"


def h8(s):
    return hashlib.sha1(s.encode()).hexdigest()[:8]


# ── probe ───────────────────────────────────────────────────────────────
def cmd_probe(a):
    key, node = parse_url(a.url)
    tok = token()
    f = api(f"/files/{key}", tok, {"depth": 2})
    print(f"ready — file: {f.get('name')} · version {f.get('version')} · modified {f.get('lastModified')}")
    if node:
        print(f"node-id in the URL: {node}")
    for p in f["document"]["children"]:
        frames = sum(1 for c in p.get("children", []) if c["type"] in ("FRAME", "SECTION"))
        comps = sum(1 for c in p.get("children", []) if c["type"] in ("COMPONENT", "COMPONENT_SET"))
        print(f"  {p['id']:>12}  {p['name']}  — top-level frames/sections {frames} · components {comps}")


# ── fetch (REST) ────────────────────────────────────────────────────────
def cmd_fetch(a):
    key, _ = parse_url(a.url)
    tok = token()
    out = a.out
    raw = os.path.join(out, "raw")
    os.makedirs(raw, exist_ok=True)
    params = {}
    if a.pages:
        params["ids"] = a.pages
    fj = os.path.join(raw, "file.json")
    if a.resume and os.path.exists(fj):
        print("· reusing file JSON (--resume)")
        f = json.load(open(fj))
    else:
        print("· downloading file JSON…")
        f = api(f"/files/{key}", tok, params)
    f["_source"] = {"fileKey": key, "url": a.url, "pages": a.pages.split(",") if a.pages else None,
                    "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "via": "rest"}
    if a.pages:  # passing ids leaves the other pages in the document as empty shells — keep only the selected pages
        keep = set(f["_source"]["pages"])
        f["document"]["children"] = [p for p in f["document"]["children"] if p["id"] in keep]
    with open(fj, "w") as fp:
        json.dump(f, fp, ensure_ascii=False)

    used_imgs, renders, icons = set(), {}, {}
    comp_meta = f.get("components", {})
    for page in f["document"]["children"]:
        def visit(n, d, parent):
            for p in (n.get("fills") or []) + (n.get("background") or []):
                if p.get("type") == "IMAGE" and p.get("imageRef"):
                    used_imgs.add(p["imageRef"])
            if n["type"] in ("COMPONENT", "COMPONENT_SET"):
                renders[n["id"]] = "components"
            if n["type"] == "INSTANCE":
                cm = comp_meta.get(n.get("componentId"), {})
                nm = cm.get("name", "")
                bb = n.get("absoluteBoundingBox") or {}
                if (":" in nm or "icon" in nm.lower()) and bb.get("width", 99) <= ICON_MAX and bb.get("height", 99) <= ICON_MAX:
                    icons.setdefault(cm.get("key") or n["componentId"], n["id"])
            elif n["type"] in ("FRAME", "GROUP") and vector_only(n) and not AUTO_NAME.match(n.get("name", "")):
                bb = n.get("absoluteBoundingBox") or {}
                if bb.get("width", 99) <= ICON_MAX and bb.get("height", 99) <= ICON_MAX:
                    icons.setdefault(icon_key(n), n["id"])   # a vector icon that is not a component — download once when name and size match (measured: 2,327 places · 78 icons)
        walk(page, visit)
        for s, _ in screens_of(page):
            renders[s["id"]] = "screens"

    print(f"· downloading {len(used_imgs)} image fills…")
    fills = api(f"/files/{key}/images", tok).get("meta", {}).get("images", {})
    miss = []
    idir = os.path.join(out, "assets", "images")
    have = {x.rsplit(".", 1)[0] for x in os.listdir(idir)} if os.path.isdir(idir) else set()
    for ref in sorted(used_imgs - have):   # skip what is already downloaded — resume with the same command after an interruption
        url = fills.get(ref)
        tmp = os.path.join(out, "assets", "images", ref)
        if not url or not download(url, tmp):
            miss.append(ref); continue
        os.replace(tmp, f"{tmp}.{sniff_ext(tmp)}")

    def render(ids, fmt, scale, folder):
        d = os.path.join(out, "assets", folder)
        have = {x.rsplit(".", 1)[0] for x in os.listdir(d)} if os.path.isdir(d) else set()
        todo = [i for i in ids if i.replace(":", "-") not in have]
        bad = []
        def go(chunk):
            r = api(f"/images/{key}", tok, {"ids": ",".join(chunk), "format": fmt, "scale": scale}, soft=True)
            if r is None:   # server dropped the connection or returned 5xx — split in half and retry; if even a single one fails, put it in the failure list
                if len(chunk) == 1: bad.append(chunk[0]); return
                h = len(chunk) // 2; go(chunk[:h]); go(chunk[h:]); return
            for nid, url in (r.get("images") or {}).items():
                if not url or not download(url, os.path.join(d, nid.replace(":", "-") + "." + fmt)):
                    bad.append(nid)
            print(f"  {folder}: +{len(chunk)}", file=sys.stderr)
        for i in range(0, len(todo), RENDER_BATCH):
            go(todo[i:i + RENDER_BATCH])
        return bad

    print(f"· downloading {len(renders)} screen/component renders…")
    bad = render([i for i, k in renders.items() if k == "screens"], "png", 2, "screens")
    bad += render([i for i, k in renders.items() if k == "components"], "png", 2, "components")
    print(f"· downloading {len(icons)} icon SVGs…")
    bad += render(icons.values(), "svg", 1, "icons")
    with open(os.path.join(raw, "fetch-report.json"), "w") as fp:
        json.dump({"missingImages": miss, "failedRenders": bad, "icons": icons}, fp, ensure_ascii=False, indent=1)
    print(f"✓ download complete → {out}  (image failures {len(miss)} · render failures {len(bad)})")
    return 1 if (miss or bad) else 0


# ── fetch-urls (MCP fallback) ─────────────────────────────────────────
def cmd_fetch_urls(a):
    """Download the list of temporary URLs that MCP's download_assets and get_screenshot returned.
    List format: [{"kind": "screens|components|icons|images", "node": "8:1296", "url": "..."}]
    kind=images is the original image so its name is unknown — the SHA-1 of its content is the Figma imageHash, so name it by that."""
    items = json.load(open(a.list))
    bad = 0
    for it in items:
        kind = it["kind"]
        if kind == "images":
            tmp = os.path.join(a.out, "assets", "images", "_tmp_" + h8(it["url"]))
            if not download(it["url"], tmp): bad += 1; continue
            digest = hashlib.sha1(open(tmp, "rb").read()).hexdigest()
            os.replace(tmp, os.path.join(a.out, "assets", "images", f"{digest}.{sniff_ext(tmp)}"))
        else:
            ext = "svg" if kind == "icons" else "png"
            if not download(it["url"], os.path.join(a.out, "assets", kind, it["node"].replace(":", "-") + "." + ext)): bad += 1
    print(f"✓ {len(items) - bad}/{len(items)} saved")
    return 1 if bad else 0


# ── build ───────────────────────────────────────────────────────────────
def load_raw(out):
    """Merge raw/file.json (REST) or raw/mcp-*.json (fallback) into one REST-shaped document."""
    raw = os.path.join(out, "raw")
    if os.path.exists(os.path.join(raw, "file.json")):
        return json.load(open(os.path.join(raw, "file.json")))
    parts = sorted(p for p in os.listdir(raw) if p.startswith("mcp-") and p.endswith(".json")) if os.path.isdir(raw) else []
    if not parts:
        die(f"{raw}/has neither file.json nor mcp-*.json — run fetch first", 2)
    doc = {"name": None, "document": {"children": []}, "components": {}, "componentSets": {}, "_source": {"via": "mcp"}}
    for p in parts:
        d = json.load(open(os.path.join(raw, p)))
        doc["name"] = doc["name"] or d.get("name")
        for pg in d["document"]["children"]:   # pieces of the same page fetched in offset chunks are merged into one page
            same = next((x for x in doc["document"]["children"] if x["id"] == pg["id"]), None)
            if same: same["children"] += [c for c in pg["children"] if c["id"] not in {x["id"] for x in same["children"]}]
            else: doc["document"]["children"].append(pg)
        doc["components"].update(d.get("components", {}))
        doc["componentSets"].update(d.get("componentSets", {}))
        doc["_source"].update({k: v for k, v in d.get("_source", {}).items() if k != "via"})
    return doc


class Ranked:
    """Usage count per value + one evidence node. The top values (cumulative TOKEN_COVERAGE) are tokens, the rest are the tail."""
    def __init__(self):
        self.n, self.at = Counter(), {}
    def add(self, k, nid):
        if k is None: return
        self.n[k] += 1; self.at.setdefault(k, nid)
    def merge_colors(self):
        """Merge close colors into the most-used representative. A different opacity means a different color."""
        reps = []
        for k, c in self.n.most_common():
            base, _, alpha = k.partition("/")
            if not re.fullmatch(r"#[0-9A-F]{6}", base): reps.append(k); continue
            tgt = next((r for r in reps if r.partition("/")[2] == alpha and re.fullmatch(r"#[0-9A-F]{6}", r.partition("/")[0])
                        and rgb_dist(base, r.partition("/")[0]) <= COLOR_MERGE), None)
            if tgt is None: reps.append(k); continue
            self.n[tgt] += c; del self.n[k]
            self.merged = getattr(self, "merged", {}); self.merged[k] = tgt
    def split(self, cap=None):
        tot, acc, head, tail = sum(self.n.values()) or 1, 0, [], []
        for k, c in self.n.most_common():
            (head if acc / tot < TOKEN_COVERAGE and (cap is None or len(head) < cap) else tail).append(k)
            acc += c
        return head, tail


def rgb_dist(a, b):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5


def cmd_build(a):
    out = a.out
    doc = load_raw(out)
    al = json.load(open(os.path.join(out, "aliases.json"))) if os.path.exists(os.path.join(out, "aliases.json")) else {}
    A = lambda sect: al.get(sect, {})
    comps_meta, sets_meta = doc.get("components", {}), doc.get("componentSets", {})
    report = json.load(open(os.path.join(out, "raw", "fetch-report.json"))) if os.path.exists(os.path.join(out, "raw", "fetch-report.json")) else {}

    R = {k: Ranked() for k in ("color", "text-color", "stroke", "font", "radius", "spacing", "shadow", "gradient")}
    local_defs = {}          # definition node id → node
    usage = defaultdict(list)  # definition key (key or id) → [(screen id, instance id, variant name)]
    images = defaultdict(lambda: {"nodes": [], "names": Counter(), "w": 0, "h": 0})
    sigs = defaultdict(list)   # candidate signature → [(screen id, node id, w, h, name)]
    screens, flows = [], []
    parent_of = {}

    def def_key(comp_id):
        m = comps_meta.get(comp_id, {})
        if m.get("componentSetId"):
            sm = sets_meta.get(m["componentSetId"], {})
            return sm.get("key") or m["componentSetId"], sm.get("name"), m.get("name")
        return m.get("key") or comp_id, m.get("name"), None

    def style_stats(n):
        nid = n["id"]
        for p in n.get("fills") or []:
            if p.get("visible") is False: continue
            if p["type"] == "SOLID": R["text-color" if n["type"] == "TEXT" else "color"].add(hexc(p["color"], p.get("opacity", 1)), nid)
            elif p["type"] == "IMAGE" and p.get("imageRef"):
                im = images[p["imageRef"]]; bb = n.get("absoluteBoundingBox") or {}
                if len(im["nodes"]) < 8: im["nodes"].append(nid)
                im["names"][n.get("name", "")] += 1
                im["w"] = max(im["w"], round(bb.get("width", 0))); im["h"] = max(im["h"], round(bb.get("height", 0)))
            elif p["type"].startswith("GRADIENT"):
                R["gradient"].add(p["type"].split("_")[1].lower() + "(" + ", ".join(f"{hexc(s['color'])} {round(s['position'] * 100)}%" for s in p.get("gradientStops", [])) + ")", nid)
        for p in n.get("strokes") or []:
            if p.get("visible") is not False and p["type"] == "SOLID": R["stroke"].add(hexc(p["color"], p.get("opacity", 1)), nid)
        if n.get("cornerRadius"): R["radius"].add(str(round(n["cornerRadius"], 1)), nid)
        elif n.get("rectangleCornerRadii") and any(n["rectangleCornerRadii"]): R["radius"].add(" ".join(str(round(x, 1)) for x in n["rectangleCornerRadii"]), nid)
        if n.get("layoutMode") and n["layoutMode"] != "NONE":
            if n.get("itemSpacing"): R["spacing"].add(str(round(n["itemSpacing"], 1)), nid)   # 0 means "no spacing", not a token
            for k in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft"):
                if n.get(k): R["spacing"].add(str(round(n[k], 1)), nid)
        for e in n.get("effects") or []:
            if e.get("visible") is False: continue
            if e["type"] in ("DROP_SHADOW", "INNER_SHADOW"):
                o = e.get("offset", {})
                R["shadow"].add(f"{'inset ' if e['type'] == 'INNER_SHADOW' else ''}{round(o.get('x', 0), 1)} {round(o.get('y', 0), 1)} {round(e.get('radius', 0), 1)} {round(e.get('spread', 0), 1)} {hexc(e['color'])}", nid)
            else:
                R["shadow"].add(f"{e['type'].lower()} {round(e.get('radius', 0), 1)}", nid)
        if n["type"] == "TEXT" and n.get("style"): R["font"].add(font_key(n["style"]), nid)

    # 1) Sweep definitions and screens in one pass
    pages = []
    for page in doc["document"]["children"]:
        pslug = A("pages").get(page["id"]) or slug(page["name"], page["id"].replace(":", "-"))
        pages.append({"id": page["id"], "name": page["name"], "slug": pslug, "screens": []})

        def defs(n, d, parent):
            if n["type"] == "COMPONENT_SET" or (n["type"] == "COMPONENT" and (parent or {}).get("type") != "COMPONENT_SET"):
                local_defs[n["id"]] = (n, page)
        walk(page, defs)

        for s, section in screens_of(page):
            sc = {"id": s["id"], "name": s["name"], "page": page["id"], "section": section,
                  "w": round(s["absoluteBoundingBox"]["width"]), "h": round(s["absoluteBoundingBox"]["height"]), "sig": h8(sig(s))}

            def visit(n, d, parent, sc=sc):
                if parent: parent_of[n["id"]] = parent["id"]
                style_stats(n)
                if n.get("transitionNodeID"):
                    flows.append({"screen": sc["id"], "from": n["id"], "to": n["transitionNodeID"]})
                for it in n.get("interactions") or []:
                    for act in it.get("actions") or []:
                        if act and act.get("destinationId"):
                            flows.append({"screen": sc["id"], "from": n["id"], "to": act["destinationId"], "trigger": (it.get("trigger") or {}).get("type")})
                if n["type"] == "INSTANCE":
                    k, nm, var = def_key(n.get("componentId"))
                    usage[k].append((sc["id"], n["id"], var))
                elif d > 0 and n["type"] in ("FRAME", "GROUP") and len([c for c in n.get("children", []) if c.get("visible") is not False]) >= 2:
                    bb = n.get("absoluteBoundingBox") or {}
                    sg = sig(n)
                    if sg.count("(") + sg.count(",") >= 2 and bb.get("width", 0) >= 24 and bb.get("height", 0) >= 16:
                        sigs[h8(sg)].append((sc["id"], n["id"], round(bb.get("width", 0)), round(bb.get("height", 0)), n.get("name", "")))
            walk(s, lambda n, d, p: visit(n, d, p))
            screens.append(sc); pages[-1]["screens"].append(sc["id"])

    for n, page in local_defs.values():
        walk(n, lambda x, d, p: style_stats(x))

    # 2) Components: local definitions + remote definitions used by screens (merged with the local ones by key)
    by_key = {}
    for nid, (n, page) in local_defs.items():
        meta = (sets_meta if n["type"] == "COMPONENT_SET" else comps_meta).get(nid, {})
        k = meta.get("key") or nid
        variants = n.get("children", []) if n["type"] == "COMPONENT_SET" else [n]
        by_key[k] = {"key": k, "id": nid, "figmaName": n["name"], "type": n["type"], "page": page["id"], "local": True,
                     "description": meta.get("description") or n.get("description") or "",
                     "props": {pk.split("#")[0]: {"type": pv.get("type"), "default": pv.get("defaultValue"), "options": pv.get("variantOptions")}
                               for pk, pv in (n.get("componentPropertyDefinitions") or {}).items()},
                     "variants": [{"id": v["id"], "name": v["name"]} for v in variants],
                     "w": round(n["absoluteBoundingBox"]["width"]), "h": round(n["absoluteBoundingBox"]["height"]), "node": n}
    for k, uses in usage.items():
        if k in by_key: continue
        cid = next((cid for cid, m in comps_meta.items() if (m.get("key") == k) or (sets_meta.get(m.get("componentSetId"), {}).get("key") == k) or cid == k), None)
        m = comps_meta.get(cid, {})
        nm = sets_meta.get(m.get("componentSetId"), {}).get("name") if m.get("componentSetId") else m.get("name")
        by_key[k] = {"key": k, "id": cid, "figmaName": nm or k, "type": "REMOTE", "page": None, "local": False,
                     "description": m.get("description", ""), "props": {}, "variants": [{"name": v} for v in sorted({v for _, _, v in uses if v})],
                     "w": None, "h": None, "node": None}
    # The same definition copied onto every page (same name and size) is one — merge into the one with the most uses. Remote Iconify copies with the same name are also one
    def fold(group):
        group.sort(key=lambda k: (-len(usage.get(k, [])), not by_key[k]["local"]))
        keep = group[0]
        for k in group[1:]:
            usage[keep] = usage.get(keep, []) + usage.pop(k, []); by_key[keep].setdefault("mergedKeys", []).append(k); del by_key[k]
    same = defaultdict(list)
    for k, c in by_key.items():
        # Name and size alone are not enough — “Walk” 1k and “Walk” 3k are different components with the same name and size. Variant names and structure must also match to be a copy
        if c["local"]: same[("L", c["figmaName"], c["w"], c["h"], tuple(v["name"] for v in c["variants"]), sig(c["node"]))].append(k)
        elif re.fullmatch(r"[a-z0-9-]+:[a-z0-9-]+", c["figmaName"] or ""): same[("I", c["figmaName"])].append(k)
    for g in same.values():
        if len(g) > 1: fold(g)
    # A remote definition with the same name as a local one, where there is only one such local, is the same component (a copy published to a library) — merge into the local one
    local_by_name = defaultdict(list)
    for k, c in by_key.items():
        if c["local"]: local_by_name[c["figmaName"]].append(k)
    for k in [k for k, c in by_key.items() if not c["local"]]:
        tgt = local_by_name.get(by_key[k]["figmaName"])
        if tgt and len(tgt) == 1:
            usage[tgt[0]] += usage.pop(k, []); by_key[tgt[0]].setdefault("mergedKeys", []).append(k); del by_key[k]
    names_seen = Counter(c["figmaName"] for c in by_key.values())
    ca = A("components")
    for c in by_key.values():
        a_ = ca.get(c["id"]) or ca.get(c["key"]) or {}
        c["name"] = a_.get("name") or c["figmaName"]
        c["purpose"] = a_.get("purpose", "")
        c["needsAlias"] = (not a_.get("name")) and (bool(GENERIC.search(c["figmaName"])) or names_seen[c["figmaName"]] > 1)
        c["slug"] = slug(c["name"], c["key"][:8]) + ("" if a_.get("name") or names_seen[c["figmaName"]] == 1 else "-" + h8(c["key"])[:4])
        c["uses"] = usage.get(c["key"], [])
        c["icon"] = c["key"] in (report.get("icons") or {}) or (":" in c["figmaName"] and (c["w"] or 0) <= ICON_MAX)
        c["iconify"] = c["figmaName"] if re.fullmatch(r"[a-z0-9-]+:[a-z0-9-]+", c["figmaName"] or "") else None

    # 3) Candidates: the same structure CANDIDATE_MIN or more times, and not one that is already just a single instance inside
    cand_alias = A("candidates")
    candidates = []
    screen_group = {s["id"]: (s["page"], s["sig"], s["w"]) for s in screens}
    for sg, occ in sigs.items():
        # If five copies of a screen differing only in state each contain the same chunk, that counts once, not five times — count by screen-structure group
        if len({screen_group[o[0]] for o in occ}) < CANDIDATE_MIN and len(occ) < CANDIDATE_MIN * 3: continue
        names = Counter(o[4] for o in occ if o[4] and not AUTO_NAME.match(o[4]))
        al_ = cand_alias.get(sg, {})
        candidates.append({"sig": sg, "count": len(occ), "screens": len({o[0] for o in occ}), "example": occ[0][1],
                           "size": f"{occ[0][2]}x{occ[0][3]}", "hint": names.most_common(1)[0][0] if names else "",
                           "name": al_.get("name"), "reject": al_.get("reject"), "purpose": al_.get("purpose", ""),
                           "nodes": [o[1] for o in occ[:12]]})
    candidates.sort(key=lambda c: -c["count"])
    # Of candidates that contain each other, keep only the outer one — do not have the same node set named twice
    seen_nodes = set()
    kept = []
    for c in sorted(candidates, key=lambda c: -int(c["size"].split("x")[0]) * int(c["size"].split("x")[1])):
        if set(c["nodes"]) <= seen_nodes: continue
        kept.append(c); seen_nodes.update(c["nodes"])
    candidates = sorted(kept, key=lambda c: -c["count"])
    # A candidate at least 80% inside another candidate is that candidate's sub-structure — it is built together with the outer one, so no separate decision is asked
    occ_nodes = {nid: cd["sig"] for cd in candidates for nid in [o[1] for o in sigs[cd["sig"]]]}
    for cd in candidates:
        occ = [o[1] for o in sigs[cd["sig"]]]
        def inside(nid):
            p_ = parent_of.get(nid)
            while p_:
                if p_ in occ_nodes and occ_nodes[p_] != cd["sig"]: return occ_nodes[p_]
                p_ = parent_of.get(p_)
            return None
        outer = [inside(x) for x in occ]
        if sum(1 for x in outer if x) >= 0.8 * len(occ):
            cd["nestedIn"] = Counter(x for x in outer if x).most_common(1)[0][0]

    # 4) Tokens
    ta = A("tokens")
    tokens = {}
    for kind, r in R.items():
        if kind in ("color", "text-color", "stroke"): r.merge_colors()
        head, tail = r.split(TOKEN_CAP.get(kind))
        names = ta.get(kind, {})
        tokens[kind] = {"tokens": [{"value": v, "name": names.get(v), "uses": r.n[v], "example": r.at[v],
                                    "merged": sorted(k for k, t in getattr(r, "merged", {}).items() if t == v) or None} for v in head],
                        "offToken": [{"value": v, "uses": r.n[v], "example": r.at[v]} for v in tail]}
        if kind == "font":
            def fparts(v):
                f = v.split("|"); return f[0], int(f[1]) if f[1].isdigit() else 400, float(f[2] or 0)
            for t in tokens[kind]["offToken"]:
                fa, w, sz = fparts(t["value"])
                near = min(tokens[kind]["tokens"], key=lambda x: (fparts(x["value"])[0] != fa, abs(fparts(x["value"])[2] - sz), abs(fparts(x["value"])[1] - w)), default=None)
                if near: t["nearest"] = near["name"] or near["value"]
        if kind in ("radius", "spacing"):
            num = lambda v: float(v.split()[0])
            for t in tokens[kind]["offToken"]:
                near = min(tokens[kind]["tokens"], key=lambda x: abs(num(x["value"]) - num(t["value"])), default=None)
                if near: t["nearest"] = near["name"] or near["value"]
        if kind in ("color", "text-color", "stroke"):
            named = [t for t in tokens[kind]["tokens"]]
            for t in tokens[kind]["offToken"]:
                base = t["value"].split("/")[0]
                near = min(named, key=lambda x: rgb_dist(base, x["value"].split("/")[0]), default=None)
                if near: t["nearest"] = near["name"] or near["value"]
    icon_names = sorted({c["iconify"] for c in by_key.values() if c["iconify"]})

    # 5) Asset list — attach a path only for what actually exists on disk (check counts missing ones as defects)
    def exists(folder, stem):
        d = os.path.join(out, "assets", folder)
        if not os.path.isdir(d): return None
        for f in os.listdir(d):
            if f.rsplit(".", 1)[0] == stem: return f"assets/{folder}/{f}"
        return None
    ia = A("images")
    img_list = []
    for ref, im in images.items():
        hint = next((n for n, _ in im["names"].most_common() if n and not AUTO_NAME.match(n)), "")
        img_list.append({"hash": ref, "name": ia.get(ref) or hint or None, "file": exists("images", ref), "w": im["w"], "h": im["h"],
                         "uses": sum(im["names"].values()), "nodes": im["nodes"]})
    img_list.sort(key=lambda x: -x["uses"])
    img_by_hash = {i["hash"]: i for i in img_list}

    # 6) Write
    tname = {}
    for kind in tokens:
        for t in tokens[kind]["tokens"]:
            tname[(kind, t["value"])] = t["name"] or t["value"]
            for mv in t.get("merged") or []: tname[(kind, mv)] = (t["name"] or t["value"]) + f" (≈{mv})"
        for t in tokens[kind]["offToken"]:
            if t.get("nearest"): tname[(kind, t["value"])] = f"{t['nearest']} (off-token {t['value']})"
    for d in ("components", "screens"):
        shutil.rmtree(os.path.join(out, d), ignore_errors=True)
    os.makedirs(os.path.join(out, "components"), exist_ok=True)

    def describe(n):
        bits = []
        bb = n.get("absoluteBoundingBox") or {}
        if bb: bits.append(f"{round(bb.get('width', 0))}×{round(bb.get('height', 0))}")
        lm = n.get("layoutMode")
        if lm and lm != "NONE":
            pad = [round(n.get(k, 0)) for k in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft")]
            bits.append(f"auto-layout {lm.lower()} gap {round(n.get('itemSpacing', 0))} pad {' '.join(map(str, pad))} · {n.get('primaryAxisAlignItems', 'MIN').lower()}/{n.get('counterAxisAlignItems', 'MIN').lower()}")
        for p in n.get("fills") or []:
            if p.get("visible") is False: continue
            if p["type"] == "SOLID":
                v = hexc(p["color"], p.get("opacity", 1)); kind = "text-color" if n["type"] == "TEXT" else "color"
                bits.append(f"{'color' if n['type'] == 'TEXT' else 'bg'} {tname.get((kind, v), v + ' (off-token)')}")
            elif p["type"] == "IMAGE":
                im = img_by_hash.get(p.get("imageRef"), {})
                bits.append(f"image {im.get('file') or 'img:' + str(p.get('imageRef'))[:10]} ({p.get('scaleMode', 'FILL').lower()})")
            elif p["type"].startswith("GRADIENT"):
                bits.append("gradient " + ", ".join(hexc(s["color"]) for s in p.get("gradientStops", [])))
        for p in n.get("strokes") or []:
            if p.get("visible") is not False and p["type"] == "SOLID":
                v = hexc(p["color"], p.get("opacity", 1)); bits.append(f"border {n.get('strokeWeight', 1)} {tname.get(('stroke', v), v)}")
        if n.get("cornerRadius"): bits.append(f"radius {tname.get(('radius', str(round(n['cornerRadius'], 1))), n['cornerRadius'])}")
        elif n.get("rectangleCornerRadii") and any(n["rectangleCornerRadii"]): bits.append("radius " + " ".join(str(round(x)) for x in n["rectangleCornerRadii"]))
        for e in n.get("effects") or []:
            if e.get("visible") is not False and e["type"] == "DROP_SHADOW": bits.append("shadow")
        if n["type"] == "TEXT" and n.get("style"):
            fk = font_key(n["style"]); bits.append(f"font {tname.get(('font', fk), fk)} ({font_detail(n['style'])})")
            al_ = n["style"].get("textAlignHorizontal")
            if al_ and al_ != "LEFT": bits.append(al_.lower())
        if n.get("opacity", 1) < 1: bits.append(f"opacity {round(n['opacity'], 2)}")
        if n.get("layoutPositioning") == "ABSOLUTE": bits.append("absolute")
        return " · ".join(bits)

    def outline(n, d=0, origin=None, lines=None, flow=False):
        lines = [] if lines is None else lines
        if n.get("visible") is False: return lines
        bb = n.get("absoluteBoundingBox") or {}
        origin = origin or (bb.get("x", 0), bb.get("y", 0))
        # A child inside auto-layout is positioned by the layout — write coordinates only for absolute placement
        placed = d and (not flow or n.get("layoutPositioning") == "ABSOLUTE")
        pos = f"@{round(bb.get('x', 0) - origin[0])},{round(bb.get('y', 0) - origin[1])} " if placed else ""
        nm = n.get("name", "")
        label = "" if AUTO_NAME.match(nm) else f" “{nm}”"
        ind = "  " * d
        if n["type"] == "INSTANCE":
            k, _, var = def_key(n.get("componentId"))
            c = by_key.get(k)
            ref = f"[{c['name']}](../../components/{c['slug']}.md)" if c else f"`{n.get('componentId')}`"
            props = {pk.split("#")[0]: pv.get("value") for pk, pv in (n.get("componentProperties") or {}).items()}
            texts = []
            walk(n, lambda x, dd, p: texts.append(x["characters"]) if x["type"] == "TEXT" and x.get("characters") else None)
            lines.append(f"{ind}- {pos}**{ref}**{(' ' + var) if var else ''}{(' ' + json.dumps(props, ensure_ascii=False)) if props and not var else ''} `{n['id']}`"
                         + (f" — text: {' / '.join(t.replace(chr(10), ' ')[:60] for t in texts[:8])}" if texts else ""))
            return lines
        if n["type"] == "TEXT":
            lines.append(f"{ind}- {pos}TEXT “{(n.get('characters') or '').replace(chr(10), '⏎')[:200]}” · {describe(n)} `{n['id']}`")
            return lines
        svg = None
        if d and n["type"] in ("FRAME", "GROUP"):
            canon = (report.get("icons") or {}).get(icon_key(n), n["id"])
            svg = exists("icons", canon.replace(":", "-"))
        lines.append(f"{ind}- {pos}{n['type']}{label} · {describe(n)}" + (f" · **icon** {svg}" if svg else "") + f" `{n['id']}`")
        if svg or n["type"] in ("VECTOR", "BOOLEAN_OPERATION", "STAR", "POLYGON", "LINE", "ELLIPSE", "REGULAR_POLYGON"):
            return lines
        lm = n.get("layoutMode")
        for c in n.get("children", []) or []:
            outline(c, d + 1, origin, lines, bool(lm and lm != "NONE"))
        return lines

    def rel(p, depth):
        return ("../" * depth) + p if p else None

    for c in by_key.values():
        md = [f"# {c['name']}", "",
              f"- Figma: `{c['figmaName']}` · id `{c['id']}` · key `{c['key']}` · {'local definition' if c['local'] else 'remote (library) definition — original not in this file'}",
              f"- Purpose: {c['purpose'] or '_(fill in purpose in aliases.json)_'}"]
        if c["description"]: md.append(f"- Designer description: {c['description']}")
        if c["iconify"]: md.append(f"- **Iconify icon** `{c['iconify']}` — do not copy the SVG; use the same name via Iconify (`@iconify/react`, etc.)")
        if c["w"]: md.append(f"- Size: {c['w']}×{c['h']}")
        if c["props"]:
            md += ["", "## Properties", "", "| Property | Type | Default | Options |", "| --- | --- | --- | --- |"]
            md += [f"| {k} | {v['type']} | {v['default']} | {', '.join(v['options'] or [])} |" for k, v in c["props"].items()]
        md += ["", "## Variants", ""]
        for v in c["variants"]:
            img = exists("components", (v.get("id") or "").replace(":", "-")) if v.get("id") else None
            md.append(f"- `{v['name']}`" + (f" `{v['id']}`" if v.get("id") else "") + (f" — ![]({rel(img, 1)})" if img else ""))
        if c["node"]:
            md += ["", "## Structure (per variant)", ""]
            vs = c["node"].get("children", []) if c["type"] == "COMPONENT_SET" else [c["node"]]
            for v in vs:
                md += [f"### {v['name']}", ""] + outline(v) + [""]
        md += ["", f"## Usages ({len(c['uses'])})", ""]
        for sid, iid, var in c["uses"][:40]:
            s = next((x for x in screens if x["id"] == sid), None)
            if s: md.append(f"- {s['name']} `{sid}` ← instance `{iid}`{(' · ' + var) if var else ''}")
        c["file"] = f"components/{c['slug']}.md"
        open(os.path.join(out, c["file"]), "w").write("\n".join(md) + "\n")

    if candidates:
        os.makedirs(os.path.join(out, "components", "candidates"), exist_ok=True)
    for cd in candidates:
        cd["file"] = f"components/candidates/{slug(cd['name'] or cd['hint'] or 'candidate', 'candidate')}-{cd['sig']}.md"
        node = None
        for page in doc["document"]["children"]:
            def find(n, d, p):
                nonlocal node
                if n["id"] == cd["example"]: node = n
            if node is None: walk(page, find)
        md = [f"# Candidate: {cd['name'] or cd['hint'] or '(unnamed)'}", "",
              "This was not made a component in Figma, but the same structure repeats. In code, **make it one component**.", "",
              f"- Signature `{cd['sig']}` · {cd['count']}times · screens {cd['screens']}· representative size {cd['size']}",
              f"- Verdict: {'adopted → ' + cd['name'] if cd['name'] else ('rejected — ' + cd['reject'] if cd['reject'] else ('sub-structure — built together inside candidate `' + cd['nestedIn'] + '`' if cd.get('nestedIn') else '_undecided (aliases.json candidates)_'))}",
              f"- Purpose: {cd['purpose'] or '-'}", f"- Occurrence nodes: {', '.join('`' + x + '`' for x in cd['nodes'])}", "", "## Representative structure", ""]
        md += outline(node) if node else ["(node not found)"]
        open(os.path.join(out, cd["file"]), "w").write("\n".join(md) + "\n")

    cand_by_node = {nid: cd for cd in candidates if cd["name"] for nid in cd["nodes"]}
    sig_groups = defaultdict(list)
    for s in screens: sig_groups[(s["page"], s["sig"], s["w"])].append(s["id"])
    sid2 = {s["id"]: s for s in screens}
    flows_by_screen = defaultdict(list)
    seen_flow = set()
    for f in flows:   # REST puts the same link in both transitionNodeID and interactions — count it once
        k = (f["from"], f["to"], f.get("trigger") or "ON_CLICK")
        if k in seen_flow: continue
        seen_flow.add(k); flows_by_screen[f["screen"]].append(f)
    def variant_label(nid):
        cm = comps_meta.get(nid)
        if not cm: return None
        c = by_key.get(def_key(nid)[0])
        return f"variant switch → {(c['name'] if c else def_key(nid)[1]) or '?'} / `{cm.get('name')}`"
    screen_nodes = {}
    for page in doc["document"]["children"]:
        for s, _ in screens_of(page): screen_nodes[s["id"]] = s
    pslug = {p["id"]: p["slug"] for p in pages}
    used_slugs = Counter()
    for s in screens:
        base = slug(s["name"], s["id"].replace(":", "-")); used_slugs[(s["page"], base)] += 1
        s["file"] = f"screens/{pslug[s['page']]}/{base}{'' if used_slugs[(s['page'], base)] == 1 else '-' + s['id'].replace(':', '-')}.md"
    for s in screens:
        os.makedirs(os.path.join(out, os.path.dirname(s["file"])), exist_ok=True)
        img = exists("screens", s["id"].replace(":", "-"))
        s["preview"] = img
        sib = [x for x in sig_groups[(s["page"], s["sig"], s["w"])] if x != s["id"]]
        md = [f"# {s['name']}", "", f"- Figma id `{s['id']}` · {s['w']}×{s['h']} · page {next(p['name'] for p in pages if p['id'] == s['page'])}" + (f" · section {s['section']}" if s["section"] else "")]
        if img: md += [f"- Preview: ![]({rel(img, 2)})"]
        if sib: md.append("- Other states of the same structure: " + ", ".join(f"[{sid2[x]['name']}](../../{sid2[x]['file']})" for x in sib[:12]))
        outs = flows_by_screen.get(s["id"], [])
        if outs:
            md += ["", "## Flow (prototype links)", ""]
            for f in outs[:40]:
                t = sid2.get(f["to"])
                md.append(f"- `{f['from']}` {f.get('trigger') or 'ON_CLICK'} → " + (f"[{t['name']}](../../{t['file']})" if t else (variant_label(f["to"]) or f"`{f['to']}` (node outside the selected range)")))
        md += ["", "## Layout (top to bottom, coordinates in px relative to the screen)", ""]
        lines = outline(screen_nodes[s["id"]])
        # An adopted candidate gets a marker saying it points to the candidate doc instead of the structure
        for i, ln in enumerate(lines):
            m = re.search(r"`([^`]+)`$", ln)
            if m and m.group(1) in cand_by_node:
                lines[i] = ln + f"  ⟵ **[{cand_by_node[m.group(1)]['name']}](../../{cand_by_node[m.group(1)]['file']})**"
        md += lines
        open(os.path.join(out, s["file"]), "w").write("\n".join(md) + "\n")

    # Flowchart — shapes (SHAPE_WITH_TEXT) and connectors (CONNECTOR) drawn on the page. The planning branches and order live here
    diagrams = []
    shutil.rmtree(os.path.join(out, "flows"), ignore_errors=True)
    owner = {}   # node id → (name, owning screen id) — when an annotation connector points at an element inside a screen, spell it out by name
    for page in doc["document"]["children"]:
        for sc_, _ in screens_of(page):
            walk(sc_, lambda n, d, p, sid=sc_["id"]: owner.setdefault(n["id"], (n.get("name", ""), sid)))
        for c_ in page.get("children", []):
            owner.setdefault(c_["id"], (c_.get("name", ""), None))
    for page in doc["document"]["children"]:
        shapes, conns = {}, []
        def fl(n, d, p):
            if n["type"] in ("SHAPE_WITH_TEXT", "STICKY"):
                shapes[n["id"]] = {"id": n["id"], "text": (n.get("characters") or n.get("name") or "").strip(), "shape": n.get("shapeType", n["type"])}
            elif n["type"] == "CONNECTOR":
                conns.append({"from": (n.get("connectorStart") or {}).get("endpointNodeId"), "to": (n.get("connectorEnd") or {}).get("endpointNodeId"),
                              "label": (n.get("characters") or "").strip(), "id": n["id"]})
        walk(page, fl)
        if not shapes and not conns: continue
        os.makedirs(os.path.join(out, "flows"), exist_ok=True)
        fpath = f"flows/{pslug[page['id']]}.md"
        def label(nid):
            if nid in shapes: return shapes[nid]["text"].replace("\n", " ")
            if nid in sid2: return f"[screen] {sid2[nid]['name']}"
            if nid in owner:
                nm, sid = owner[nid]
                return f"«{nm}»" + (f" ({sid2[sid]['name']})" if sid in sid2 else "")
            return f"`{nid}`"
        def link(nid):
            if nid in sid2: return f"[{sid2[nid]['name']}](../{sid2[nid]['file']})"
            if nid in owner and owner[nid][1] in sid2:
                s_ = sid2[owner[nid][1]]; return f"«{owner[nid][0]}» in [{s_['name']}](../{s_['file']}) `{nid}`"
            return label(nid)
        mid = {}
        def m(nid):
            mid.setdefault(nid, f"n{len(mid)}"); return mid[nid]
        mer = ["```mermaid", "flowchart TD"]
        for nid, sh in shapes.items():
            t = sh["text"].replace('"', "'").replace("\n", " ")
            mer.append(f'  {m(nid)}{{"{t}"}}' if sh["shape"] in ("DIAMOND",) else f'  {m(nid)}["{t}"]')
        for c in conns:
            if not c["from"] or not c["to"]: continue
            for e in (c["from"], c["to"]):
                if e not in shapes and e not in mid: mer.append(f'  {m(e)}(["{label(e).replace(chr(34), chr(39))}"])')
            mer.append(f"  {m(c['from'])} -->{'|' + c['label'].replace('|', '/') + '|' if c['label'] else ''} {m(c['to'])}")
        mer.append("```")
        md = [f"# Flowchart — {page['name']}", "", "This is the planning flow drawn on the page. A diamond (DIAMOND) is a branch — the connector label is the branch condition.", "",
              f"- Shapes {len(shapes)} · Connections {len(conns)}", "", "## Diagram", ""] + mer + ["", "## Connections", ""]
        md += [f"- {link(c['from'])} → {link(c['to'])}" + (f" — **{c['label']}**" if c["label"] else "") + f" `{c['id']}`" for c in conns]
        orphan = [sh for nid, sh in shapes.items() if not any(nid in (c["from"], c["to"]) for c in conns)]
        if orphan:
            md += ["", "## Shapes with no connection (may be notes or a legend)", ""] + [f"- {o['text']} ({o['shape'].lower()}) `{o['id']}`" for o in orphan]
        open(os.path.join(out, fpath), "w").write("\n".join(md) + "\n")
        diagrams.append({"page": page["id"], "file": fpath, "shapes": len(shapes), "connectors": len(conns)})

    def pub(c):
        return {k: v for k, v in c.items() if k not in ("node",)}
    src = doc.get("_source", {})
    manifest = {"schema": "figma-bundle/1", "source": {"file": doc.get("name"), "version": doc.get("version"), "lastModified": doc.get("lastModified"), **src},
                "fidelity": "full" if src.get("via") == "rest" else "summary",
                "pages": pages, "screens": screens, "components": [pub(c) for c in by_key.values()], "candidates": candidates,
                "images": img_list, "iconify": icon_names, "flows": flows, "diagrams": diagrams, "fetch": report}
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"coverage": TOKEN_COVERAGE, **tokens}, open(os.path.join(out, "tokens.json"), "w"), ensure_ascii=False, indent=1)

    # README — the index the implementing agent reads first
    T = lambda kind, k=12: "\n".join(f"| `{t['name'] or '—'}` | `{t['value']}` | {t['uses']} |" for t in tokens[kind]["tokens"][:k])
    rd = [f"# Design bundle — {doc.get('name')}", "",
          f"Source: {src.get('url', '')}  ", f"Version {doc.get('version')} · modified {doc.get('lastModified')} · extracted {src.get('fetchedAt', '')} · fidelity **{manifest['fidelity']}**", "",
          "## Reading order when implementing", "", "> `assets/…` paths in the document body are relative to this bundle root. The `id` at the end of a node line lets you find the Figma original again.", "",
          "1. The token tables in this file → move them into the code's theme/CSS variables. **Use the token name instead of hardcoding the value.** Snap `offToken` values to the `nearest` token",
          "2. `components/*.md` → one code component each. The variant and property tables are the props. Adopted candidates in `components/candidates/` also become components",
          "3. `screens/<page>/*.md` → screens. Instance lines become the matching component; assemble the remaining lines in place. Compare side by side with the preview PNG",
          "4. Images come from `assets/images/`; icons go through the Iconify library when there is an Iconify name, otherwise use the `assets/icons/` SVG",
          "5. The flowcharts in `flows/` are the reference for branching and order — if they differ from the prototype flow in a screen doc, follow the flowchart",
          "6. If you can access Figma, call `get_design_context` again by id only for nodes whose details are unclear (the bundle is the primary source)", "",
          f"## Scale", "", f"- Pages {len(pages)} · Screens {len(screens)} · Components {len(by_key)} (local {sum(c['local'] for c in by_key.values())}) · Adopted candidates {sum(1 for c in candidates if c['name'])} · Images {len(img_list)} · Iconify {len(icon_names)}", ""]
    for kind, title in (("color", "Background and fill color"), ("text-color", "Text color"), ("font", "Typography (family|weight|size|line-height|letter-spacing)"), ("radius", "Corners"), ("spacing", "Spacing"), ("shadow", "Shadows")):
        if tokens[kind]["tokens"]:
            tot = sum(t["uses"] for t in tokens[kind]["tokens"] + tokens[kind]["offToken"]) or 1
            cov = round(100 * sum(t["uses"] for t in tokens[kind]["tokens"]) / tot)
            rd += [f"### {title}", "", f"{len(tokens[kind]['tokens'])} tokens cover {cov}% of usages. Snap the remaining {len(tokens[kind]['offToken'])} values to the `nearest` token in `tokens.json`.", "",
                   "| Name | Value | Uses |", "| --- | --- | --- |", T(kind, 30), ""]
    rd += ["## Components", "", "| Name | Figma name | Variants | Uses |", "| --- | --- | --- | --- |"]
    rd += [f"| [{c['name']}]({c['file']}) | `{c['figmaName']}` | {len(c['variants'])} | {len(c['uses'])} |" for c in sorted(by_key.values(), key=lambda c: -len(c['uses']))]
    rd += ["", "## Screens", ""]
    for p in pages:
        rd.append(f"### {p['name']}")
        rd += [f"- [{sid2[x]['name']}]({sid2[x]['file']})" for x in p["screens"]] + [""]
    if diagrams:
        rd += ["## Flowcharts (planning)", ""] + [f"- [{next(p['name'] for p in pages if p['id'] == d['page'])}]({d['file']}) — shapes {d['shapes']} · connections {d['connectors']}" for d in diagrams] + [""]
    if icon_names: rd += ["## Iconify icons", "", ", ".join(f"`{x}`" for x in icon_names), ""]
    open(os.path.join(out, "README.md"), "w").write("\n".join(rd) + "\n")
    print(f"✓ build — screens {len(screens)} · components {len(by_key)} · candidates {len(candidates)} · images {len(img_list)} → {out}")
    return 0


# ── check ───────────────────────────────────────────────────────────────
def cmd_check(a):
    out = a.out
    mp = os.path.join(out, "manifest.json")
    if not os.path.exists(mp):
        print("cannot decide — manifest.json is missing (before build)", file=sys.stderr); return 2
    m = json.load(open(mp)); tk = json.load(open(os.path.join(out, "tokens.json")))
    fails, warns = [], []
    F = lambda code, msg: fails.append(f"{code} {msg}")
    for s in m["screens"]:
        if not s.get("preview"): F("SCREEN-PREVIEW", f"{s['name']} `{s['id']}` preview PNG missing")
        if not os.path.exists(os.path.join(out, s["file"])): F("SCREEN-DOC", s["file"])
    names = Counter(c["name"] for c in m["components"])
    cdir = os.path.join(out, "assets", "components")
    rendered = {f.rsplit(".", 1)[0] for f in os.listdir(cdir)} if os.path.isdir(cdir) else set()
    for c in m["components"]:
        if c["needsAlias"]: F("COMP-NAME", f"`{c['figmaName']}` `{c['id']}` — a meaningless or duplicated name. Add name and purpose under aliases.json components")
        elif not c.get("purpose") and c["uses"]: warns.append(f"COMP-PURPOSE {c['name']} no purpose")
        if names[c["name"]] > 1: F("COMP-DUP", f"`{c['name']}` name appears {names[c['name']]} times — code component names would collide")
        if c["local"] and not c["iconify"]:
            for v in c["variants"]:
                if v.get("id") and v["id"].replace(":", "-") not in rendered:
                    F("COMP-PREVIEW", f"{c['name']} / {v['name']} render missing"); break
    for cd in m["candidates"]:
        if not cd["name"] and not cd["reject"] and not cd.get("nestedIn"): F("CAND-UNDECIDED", f"signature {cd['sig']} ({cd['count']}times, e.g. `{cd['example']}`, hint “{cd['hint']}”) — adopt (name) or reject (reject)")
    for i in m["images"]:
        if not i["file"]: F("IMG-MISSING", f"img {i['hash'][:10]} ({i['uses']}times) file missing")
        elif not i["name"]: warns.append(f"IMG-NAME {i['hash'][:10]} {i['w']}x{i['h']} no name")
    for kind in ("color", "text-color", "font", "radius", "spacing", "shadow"):
        for t in tk[kind]["tokens"]:
            if not t["name"]: F("TOKEN-NAME", f"{kind} `{t['value']}` ({t['uses']}times) no name — aliases.json tokens.{kind}");
    tn = Counter((k, t["name"]) for k in tk if isinstance(tk[k], dict) for t in tk[k].get("tokens", []) if t["name"])
    for (k, n), c in tn.items():
        if c > 1: F("TOKEN-DUP", f"{k} token name `{n}`is attached to {c} values")
    if m["fidelity"] != "full": warns.append("FIDELITY summary — this is an MCP-fallback bundle. Fill in detailed styles with get_design_context at implementation time")
    for w in warns[:30]: print(f"  ! {w}")
    if len(warns) > 30: print(f"  ! … {len(warns) - 30} more warnings")
    for f in fails[:60]: print(f"  ✗ {f}")
    if len(fails) > 60: print(f"  ✗ … {len(fails) - 60} more defects")
    byc = Counter(f.split()[0] for f in fails)
    print(("✗ check failed — " + " · ".join(f"{k} {v}" for k, v in byc.items())) if fails else f"✓ check passed (warnings {len(warns)})")
    return 1 if fails else 0


# ── self-test ───────────────────────────────────────────────────────────
def fixture():
    C = lambda r, g, b: {"r": r, "g": g, "b": b, "a": 1}
    orange, cream, gray = C(0.949, 0.451, 0.129), C(0.996, 0.984, 0.973), C(0.549, 0.549, 0.580)
    bb = lambda x, y, w, h: {"x": x, "y": y, "width": w, "height": h}
    txt = lambda i, s, col, size, x, y: {"id": i, "type": "TEXT", "name": s, "characters": s, "absoluteBoundingBox": bb(x, y, 200, 20),
                                        "fills": [{"type": "SOLID", "color": col}], "style": {"fontFamily": "Inter", "fontWeight": 500, "fontSize": size, "lineHeightPx": 19.3, "letterSpacing": -0.2}}
    btn = lambda i, label, x, y: {"id": i, "type": "GROUP", "name": "Group 1", "absoluteBoundingBox": bb(x, y, 343, 50), "children": [
        {"id": i + "r", "type": "RECTANGLE", "name": "Rectangle 1", "absoluteBoundingBox": bb(x, y, 343, 50), "cornerRadius": 5, "fills": [{"type": "SOLID", "color": orange}]},
        txt(i + "t", label, cream, 16, x, y + 15), {"id": i + "i", "type": "RECTANGLE", "name": "ChatGPT Image 1", "absoluteBoundingBox": bb(x + 90, y + 10, 30, 30), "fills": [{"type": "IMAGE", "imageRef": "abc123"}]}]}
    inst = lambda i, x, y: {"id": i, "type": "INSTANCE", "name": "Card", "componentId": "1:11", "absoluteBoundingBox": bb(x, y, 150, 100), "children": [txt(i + "t", "Walk 1k", orange, 14, x, y)]}
    screen = lambda i, name, k: {"id": i, "type": "FRAME", "name": name, "absoluteBoundingBox": bb(k * 500, 0, 393, 852), "fills": [{"type": "SOLID", "color": cream}],
                                 "children": [txt(i + ":h", "Hello", orange, 30, k * 500, 100), btn(i + ":b1", "Email", k * 500 + 25, 200), btn(i + ":b2", "Google", k * 500 + 25, 260), inst(i + ":c", k * 500, 400)],
                                 "interactions": [{"trigger": {"type": "ON_CLICK"}, "actions": [{"destinationId": "9:2"}]}] if i == "9:1" else []}
    comp_set = {"id": "1:10", "type": "COMPONENT_SET", "name": "Component 11", "absoluteBoundingBox": bb(0, -400, 320, 120),
                "componentPropertyDefinitions": {"State#1": {"type": "VARIANT", "defaultValue": "on", "variantOptions": ["on", "off"]}},
                "children": [{"id": "1:11", "type": "COMPONENT", "name": "State=on", "absoluteBoundingBox": bb(0, -400, 150, 100), "fills": [{"type": "SOLID", "color": gray}], "children": [txt("1:11t", "Walk", orange, 14, 0, -400)]},
                             {"id": "1:12", "type": "COMPONENT", "name": "State=off", "absoluteBoundingBox": bb(170, -400, 150, 100), "children": []}]}
    dup = {"id": "1:20", "type": "COMPONENT", "name": "Walk", "absoluteBoundingBox": bb(400, -400, 50, 50)}
    dup2 = {"id": "1:21", "type": "COMPONENT", "name": "Walk", "absoluteBoundingBox": bb(500, -400, 50, 50), "children": [txt("1:21t", "3k", orange, 12, 500, -400)]}
    s3 = screen("9:3", "Join", 2); s3["children"].append(txt("9:3:x", "extra", gray, 12, 1000, 600))
    s4 = screen("9:4", "Reset", 3); s4["children"] += [txt("9:4:x", "a", gray, 12, 1500, 600), txt("9:4:y", "b", gray, 12, 1500, 640)]
    flow = [{"id": "5:1", "type": "SHAPE_WITH_TEXT", "name": "Permission granted?", "characters": "Permission granted?", "shapeType": "DIAMOND"},
            {"id": "5:2", "type": "SHAPE_WITH_TEXT", "name": "Sync", "characters": "Sync steps", "shapeType": "SQUARE"},
            {"id": "5:3", "type": "CONNECTOR", "name": "Yes", "characters": "Yes", "connectorStart": {"endpointNodeId": "5:1"}, "connectorEnd": {"endpointNodeId": "5:2"}},
            {"id": "5:4", "type": "CONNECTOR", "name": "c", "characters": "", "connectorStart": {"endpointNodeId": "5:2"}, "connectorEnd": {"endpointNodeId": "9:1"}}]
    page = {"id": "0:1", "type": "CANVAS", "name": "Sign-up", "children": [comp_set, dup, dup2, screen("9:1", "Login", 0), screen("9:2", "Login", 1), s3, s4] + flow}
    # the same set copied onto another page — must fold into one
    copy = json.loads(json.dumps(comp_set).replace('"1:1', '"7:1'))
    page2 = {"id": "0:2", "type": "CANVAS", "name": "Library copy", "children": [copy]}
    return {"name": "Fixture", "version": "1", "lastModified": "2026-11-03", "document": {"id": "0:0", "type": "DOCUMENT", "children": [page, page2]},
            "components": {"1:11": {"key": "k11", "name": "State=on", "componentSetId": "1:10"}, "1:12": {"key": "k12", "name": "State=off", "componentSetId": "1:10"},
                           "1:20": {"key": "k20", "name": "Walk"}, "1:21": {"key": "k21", "name": "Walk"}},
            "componentSets": {"1:10": {"key": "kset", "name": "Component 11"}, "7:10": {"key": "kcopy", "name": "Component 11"}}, "_source": {"via": "rest", "url": "fixture"}}


def self_test():
    ok = bad = 0
    def expect(name, cond, detail=""):
        nonlocal ok, bad
        if cond: ok += 1; print(f"  ✓ {name}")
        else: bad += 1; print(f"  ✗ {name} {detail}")
    import io, contextlib
    def run(fn, out):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = fn(argparse.Namespace(out=out))
        return rc, buf.getvalue()
    with tempfile.TemporaryDirectory() as t:
        os.makedirs(os.path.join(t, "raw")); json.dump(fixture(), open(os.path.join(t, "raw", "file.json"), "w"))
        rc, _ = run(cmd_build, t)
        expect("build exit 0", rc == 0)
        m = json.load(open(os.path.join(t, "manifest.json")))
        expect("4 screens · 3 components (1 set + 2 singles)", len(m["screens"]) == 4 and len(m["components"]) == 3, f"{len(m['screens'])}/{len(m['components'])}")
        expect("a copy of the same set on another page folds into one", "kcopy" in (next(c for c in m["components"] if c["key"] == "kset").get("mergedKeys") or []))
        expect("instance usages merge into the set", next(c for c in m["components"] if c["key"] == "kset")["uses"].__len__() == 4)
        cand = [c for c in m["candidates"] if c["count"] >= 8]
        expect("a repeated non-component button is picked up as a candidate", len(cand) == 1 and cand[0]["hint"] == "", json.dumps(m["candidates"])[:200])
        expect("screens with the same structure are grouped as siblings", "Other states of the same structure" in open(os.path.join(t, m["screens"][0]["file"])).read())
        fd = open(os.path.join(t, "flows", "sign-up.md")).read() if os.path.exists(os.path.join(t, "flows", "sign-up.md")) else ""
        expect("flowchart: branch label and screen endpoint remain in the doc", '{"Permission granted?"}' in fd and "|Yes|" in fd and "[Login](../screens/sign-up/" in fd, fd[:300])
        expect("flows resolve to screen links", "[Login](../../screens/sign-up/login-9-2.md)" in open(os.path.join(t, m["screens"][0]["file"])).read())
        # State with planted defects: no name · duplicate · undecided candidate · no preview · no image → must fail for each reason
        rc, outp = run(cmd_check, t)
        for code in ("COMP-NAME", "CAND-UNDECIDED", "SCREEN-PREVIEW", "IMG-MISSING", "TOKEN-NAME", "COMP-PREVIEW"):
            expect(f"check fails with {code}", rc == 1 and code in outp)
        # Fixed state: filling in aliases and assets must pass
        tk = json.load(open(os.path.join(t, "tokens.json")))
        names = {k: {x["value"]: f"{k}/{i}" for i, x in enumerate(tk[k]["tokens"])} for k in ("color", "text-color", "font", "radius", "spacing", "shadow", "stroke", "gradient")}
        json.dump({"components": {"1:10": {"name": "MissionCard", "purpose": "Mission card"}, "1:20": {"name": "WalkBadge", "purpose": "x"}, "1:21": {"name": "WalkBadgeLarge", "purpose": "x"}},
                   "candidates": {cand[0]["sig"]: {"name": "SocialLoginButton", "purpose": "Social login"}} | {c["sig"]: {"reject": "coincidence"} for c in m["candidates"] if c is not cand[0]},
                   "tokens": names, "images": {"abc123": "google-logo"}}, open(os.path.join(t, "aliases.json"), "w"))
        for d, ids in (("screens", ["9-1", "9-2", "9-3", "9-4"]), ("components", ["1-11", "1-12", "1-20", "1-21"]), ("images", ["abc123"])):
            os.makedirs(os.path.join(t, "assets", d), exist_ok=True)
            for i in ids: open(os.path.join(t, "assets", d, i + ".png"), "wb").write(b"\x89PNG")
        rc, _ = run(cmd_build, t)
        rc, outp = run(cmd_check, t)
        expect("check passes once aliases and assets are filled in", rc == 0, outp[-400:])
        expect("an adopted candidate is linked in the screen doc", "SocialLoginButton" in open(os.path.join(t, json.load(open(os.path.join(t, "manifest.json")))["screens"][0]["file"])).read())
        # A planted duplicate name must fail with COMP-DUP
        al = json.load(open(os.path.join(t, "aliases.json"))); al["components"]["1:21"]["name"] = "WalkBadge"; json.dump(al, open(os.path.join(t, "aliases.json"), "w"))
        run(cmd_build, t); rc, outp = run(cmd_check, t)
        expect("a duplicate alias fails with COMP-DUP", rc == 1 and "COMP-DUP" in outp)
    with tempfile.TemporaryDirectory() as t:
        rc, _ = run(cmd_check, t)
        expect("check before build cannot decide (2)", rc == 2)
    print(f"\nself-test: pass {ok} · fail {bad}")
    return 1 if bad else 0


def main():
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("probe"); p.add_argument("--url", required=True)
    p = sp.add_parser("fetch"); p.add_argument("--url", required=True); p.add_argument("--out", required=True); p.add_argument("--pages")
    p.add_argument("--resume", action="store_true", help="do not re-download raw/file.json, and skip assets already on disk")
    p = sp.add_parser("fetch-urls"); p.add_argument("--list", required=True); p.add_argument("--out", required=True)
    for c in ("build", "check"):
        p = sp.add_parser(c); p.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.exit({"probe": cmd_probe, "fetch": cmd_fetch, "fetch-urls": cmd_fetch_urls, "build": cmd_build, "check": cmd_check}[a.cmd](a) or 0)


if __name__ == "__main__":
    main()
