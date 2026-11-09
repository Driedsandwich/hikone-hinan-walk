#!/usr/bin/env python3
"""前処理・埋め込み・MCP の確かめ。使い方: python3 -I test/test_data.py (どこからでも可)

独立の照合: build_data.py を import せず、CSV と OSM から 彦根城 の結果を別実装で求めて data.json と突き合わせる。
"""
import csv, json, math, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + str(detail)) if detail != "" else ""))
    if not cond:
        FAILS.append(name)


def hav(a, b, c, d):
    r = 6371008.8
    p1, p2 = math.radians(a), math.radians(c)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


data = json.load(open(os.path.join(ROOT, "app", "data.json"), encoding="utf-8"))
spots = data["spots"]
st = data["stats"]

# 1. 件数
check("避難場所 63 行", len(data["shelters"]) == 63, len(data["shelters"]))
check("指定避難所 18 行", len(data["hinanjo"]) == 18, len(data["hinanjo"]))
check("地点の id が一意", len({s["id"] for s in spots}) == len(spots))
check("全地点に 洪水/地震/土砂/内水氾濫/any/jo がある",
      all(all(k in s["near"] for k in ("flood", "quake", "slope", "inner", "any", "jo")) for s in spots))

# 2. 独立の再計算 (CSV と OSM を直接読む)
shel = list(csv.DictReader(open(os.path.join(ROOT, "data", "hinanbasho_hikone.csv"), encoding="utf-8-sig")))
check("CSV の避難場所 63 行", len(shel) == 63)
osm = json.load(open(os.path.join(ROOT, "data", "osm_hikone_poi.json"), encoding="utf-8"))
raw = 0
for e in osm["elements"]:
    t = e.get("tags", {})
    if e["type"] == "relation" or not t.get("name"):
        continue
    if t.get("tourism") in ("attraction", "museum", "viewpoint", "artwork") or \
       t.get("historic") in ("castle", "monument", "ruins", "memorial") or t.get("amenity") == "place_of_worship":
        raw += 1
check("OSM の条件に合う要素数 (重なり除く前) が build_info と一致", raw == data["build_info"]["spots"]["raw_elements"], raw)
check("まとめた後の地点数 = 要素数 - まとめた数",
      len(spots) == raw - data["build_info"]["spots"]["merged"], (len(spots), raw, data["build_info"]["spots"]["merged"]))

# 正の対照: 彦根城 (way 209262408) が地点に含まれる
castle = [s for s in spots if s["osm"] == "way/209262408"]
check("【正の対照】彦根城 (way/209262408) が地点にある", len(castle) == 1)
c = castle[0]
check("彦根城の座標が OSM の center と一致", (c["lat"], c["lon"]) == (35.2770307, 136.2521014), (c["lat"], c["lon"]))
best = min(((hav(c["lat"], c["lon"], float(r["緯度"]), float(r["経度"])), r["施設・場所名"]) for r in shel if r["洪水"] == "1"))
mine = data["shelters"][c["near"]["flood"]["i"]]
check("彦根城の最寄り避難場所(洪水)が独立計算と同じ", mine["name"] == best[1], (mine["name"], best[1]))
check("彦根城の距離と分が独立計算と一致", c["near"]["flood"]["d"] == round(best[0]) and
      c["near"]["flood"]["m"] == round(best[0] * 1.3 / 80, 1), (c["near"]["flood"], round(best[0]), round(best[0] * 1.3 / 80, 1)))
check("彦根城 洪水 5.5 分・避難場所は西中学校", c["near"]["flood"]["m"] == 5.5 and mine["name"] == "彦根市立西中学校")

# 負の対照: 存在しない地点が無い (道具が動いている正の対照と同じ実行)
check("【負の対照】存在しない名前の地点は 0", not [s for s in spots if "存在しない地点XYZ" in s["name"]])

# 3. 集計が地点から再現できる
walk = [s for s in spots if not s["boat_only"]]
over = sum(1 for s in walk if s["near"]["flood"]["m"] > 15)
check("15 分超の数 (洪水) が集計と一致", over == st["by"]["flood"]["over15"], over)
check("徒歩で行ける地点数が集計と一致", len(walk) == st["walkable"], len(walk))
ms = sorted(s["near"]["flood"]["m"] for s in walk)
n = len(ms)
med = ms[n // 2] if n % 2 else (ms[n // 2 - 1] + ms[n // 2]) / 2
check("中央値 (洪水) が集計と一致", round(med, 1) == st["by"]["flood"]["median"], round(med, 1))
print("INFO 地点数", st["spots"], "徒歩で行ける", st["walkable"], "島", st["boat_only"], "15分超(洪水)", over,
      "中央値 避難場所", st["by"]["flood"]["median"], "避難所", st["by"]["jo"]["median"],
      "佐和山", st["sawayama"]["min"], "-", st["sawayama"]["max"])

# 4. 再現性: 別の場所に作り直した data.json が、作った時刻以外は同じ
with tempfile.TemporaryDirectory() as td:
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "build_data.py"), "--out", td],
                   check=True, stdout=subprocess.DEVNULL)
    again = json.load(open(os.path.join(td, "data.json"), encoding="utf-8"))
a, b = dict(data), dict(again)
a.pop("generated_at"); b.pop("generated_at")
check("再実行した data.json が 作った時刻以外は同一", a == b)

# 5. index.html の埋め込みが data.json と同じ
html = open(os.path.join(ROOT, "app", "index.html"), encoding="utf-8").read()
m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
emb = json.loads(m.group(1)) if m else None
check("index.html の埋め込みが data.json と同一", emb == data)
body = re.sub(r'<script id="data".*?</script>', '', html, flags=re.S)
loads = set(re.findall(r'<script[^>]*\ssrc="(https://[^"/]+)', body)) \
    | set(re.findall(r'<link[^>]*\shref="(https://[^"/]+)', body)) \
    | set(re.findall(r'tileLayer\("(https://[^"/]+)', body))
check("index.html が読み込む外部は cdnjs の Leaflet と OSM タイルだけ",
      loads == {"https://cdnjs.cloudflare.com", "https://tile.openstreetmap.org"}, sorted(loads))

# 6. MCP (node を起こして標準入力から流す)
reqs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nearest_shelter", "arguments": {"lat": 35.2770307, "lon": 136.2521014, "hazard": "洪水"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "far_spots", "arguments": {"min_minutes": 15, "limit": 100}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "spot_info", "arguments": {"name": "彦根城博物館"}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "spot_info", "arguments": {"name": "存在しない地点XYZ"}}},
    {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "nearest_shelter", "arguments": {"lat": 35.27, "lon": 136.25, "hazard": "噴火"}}},
    {"jsonrpc": "2.0", "id": 8, "method": "nope"},
]
p = subprocess.run(["node", os.path.join(ROOT, "mcp", "server.mjs")],
                   input="\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n",
                   capture_output=True, text=True, timeout=30)
lines = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
byid = {x["id"]: x for x in lines}
check("MCP: 終了コード 0 と返答 8 件 (通知には返さない)", p.returncode == 0 and len(lines) == 8, (p.returncode, len(lines)))
check("MCP: initialize が protocolVersion を返す", byid[1]["result"]["protocolVersion"] == "2025-06-18")
check("MCP: tools/list が 3 道具", [t["name"] for t in byid[2]["result"]["tools"]] == ["nearest_shelter", "far_spots", "spot_info"])
r3 = byid[3]["result"]["structuredContent"]
check("MCP: nearest_shelter(彦根城) が data.json と一致",
      r3["nearest_shelter"]["name"] == mine["name"] and r3["nearest_shelter"]["walk_minutes"] == c["near"]["flood"]["m"]
      and r3["nearest_shelter"]["distance_m"] == c["near"]["flood"]["d"], r3["nearest_shelter"]["walk_minutes"])
check("MCP: far_spots(15) の件数が集計の 15 分超と同じ",
      byid[4]["result"]["structuredContent"]["total_matches"] == over, byid[4]["result"]["structuredContent"]["total_matches"])
check("MCP: spot_info(彦根城博物館) が 1 件", byid[5]["result"]["structuredContent"]["matches"] == 1)
check("MCP: 【負の対照】存在しない名前は 0 件", byid[6]["result"]["structuredContent"]["matches"] == 0)
check("MCP: 不正な hazard は isError", byid[7]["result"]["isError"] is True)
check("MCP: 未知のメソッドは -32601", byid[8]["error"]["code"] == -32601)

# 7. 書式: 読点と鍵括弧を続けない
bad = []
for rel in ("app/index.html", "app/llms.txt", "README.md", "mcp/README.md", "mcp/server.mjs", "tools/build_data.py"):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        continue
    txt = re.sub(r'<script id="data".*?</script>', '', open(path, encoding="utf-8").read(), flags=re.S)
    for mm in re.finditer(r"、「|」、", txt):
        bad.append((rel, txt[max(0, mm.start() - 8):mm.end() + 8]))
check("「、「」と「」、」が無い", not bad, bad[:3])

print("FAILED:" if FAILS else "ALL PASS", FAILS if FAILS else "")
sys.exit(1 if FAILS else 0)
