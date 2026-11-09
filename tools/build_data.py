#!/usr/bin/env python3
"""彦根のまち歩き x 避難場所の地図: CSV と OSM から app/data.json を作り、app/index.html に埋め込む。

使い方:  python3 -I tools/build_data.py            (data.json を作り、index.html の埋め込みも更新)
         python3 -I tools/build_data.py --out DIR  (DIR/data.json だけ作る。テスト用)

再現性: 作った時刻 (generated_at) 以外は、同じ入力から同じ出力になる。
"""
import argparse
import csv
import json
import math
import os
import re
import statistics
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

WALK_FACTOR = 1.3        # 道のりは直線距離の 1.3 倍と推定
WALK_SPEED_M_PER_MIN = 80.0
LONG_WALK_MIN = 15.0
DEDUP_M = 30.0

# 災害の種類: キー -> (画面の名前, CSV の列名)
HAZARDS = [
    ("flood", "洪水", "洪水"),
    ("quake", "地震", "地震"),
    ("slope", "土砂", "崖崩れ、土石流及び地滑り"),
    ("inner", "内水氾濫", "内水氾濫"),
]

# 主な名所の札は編集上の選び (名前で指定)。同じ名前が複数あるときは先頭の印だけに付く。
FEATURED_NAMES = ["彦根城", "彦根城博物館", "埋木舎", "開国記念館", "中村商家保存館",
                  "松原下屋敷（お浜御殿）", "井伊直政公像", "石田三成 屋敷跡", "佐和山城"]

# 船でしか行けない場所 (琵琶湖の島)。徒歩の分は参考にならないので、集計とランキングから外す。
BOAT_ONLY_BOXES = [("多景島", 35.2955, 35.2980, 136.1765, 136.1800)]

# 佐和山の山城の跡: 佐和山城の印からこの距離 (m) 以内の「城・史跡」
SAWAYAMA_CENTER_NAME = "佐和山城"
SAWAYAMA_RADIUS_M = 600

TOURISM_OK = {"attraction", "museum", "viewpoint", "artwork"}
HISTORIC_OK = {"castle", "monument", "ruins", "memorial"}


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def walk_min(dist_m):
    return round(dist_m * WALK_FACTOR / WALK_SPEED_M_PER_MIN, 1)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_shelters(path):
    out = []
    for r in read_csv(path):
        flags = [k for k, _, col in HAZARDS if (r.get(col) or "").strip() == "1"]
        out.append({
            "name": r["施設・場所名"].strip(),
            "address": r["住所"].strip(),
            "lat": float(r["緯度"]),
            "lon": float(r["経度"]),
            "hazards": flags,
            "also_hinanjo": (r.get("指定避難所との住所同一") or "").strip() == "1",
        })
    return out


def load_hinanjo(path):
    out = []
    for r in read_csv(path):
        out.append({
            "name": r["施設・場所名"].strip(),
            "address": r["住所"].strip(),
            "lat": float(r["緯度"]),
            "lon": float(r["経度"]),
        })
    return out


def element_point(e):
    if e["type"] == "node":
        return e["lat"], e["lon"]
    if "center" in e:
        return e["center"]["lat"], e["center"]["lon"]
    if "bounds" in e:
        b = e["bounds"]
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    if "geometry" in e and e["geometry"]:
        g = e["geometry"]
        return (sum(p["lat"] for p in g) / len(g), sum(p["lon"] for p in g) / len(g))
    return None


def spot_kind(t):
    """画面に出す種別。優先: 名所・博物館・眺め > 城や史跡 > 碑 > 社寺。"""
    if t.get("tourism") == "museum":
        return "博物館"
    if t.get("tourism") in ("attraction", "viewpoint", "artwork"):
        return "名所・眺め"
    h = t.get("historic")
    if h in ("castle", "ruins"):
        return "城・史跡"
    if h in ("monument", "memorial"):
        return "碑・記念物"
    if t.get("amenity") == "place_of_worship":
        return "社寺"
    return "その他"


def load_spots(osm_path):
    with open(osm_path, encoding="utf-8") as f:
        osm = json.load(f)
    raw = []
    tag_counts = {}
    for e in osm["elements"]:
        if e["type"] == "relation":
            continue
        t = e.get("tags", {})
        if not t.get("name"):
            continue
        hit = []
        if t.get("tourism") in TOURISM_OK:
            hit.append("tourism=" + t["tourism"])
        if t.get("historic") in HISTORIC_OK:
            hit.append("historic=" + t["historic"])
        if t.get("amenity") == "place_of_worship":
            hit.append("amenity=place_of_worship")
        if not hit:
            continue
        pt = element_point(e)
        if pt is None:
            continue
        for h in hit:
            tag_counts[h] = tag_counts.get(h, 0) + 1
        raw.append({
            "osm": "%s/%d" % (e["type"], e["id"]),
            "name": t["name"].strip(),
            "lat": round(pt[0], 7),
            "lon": round(pt[1], 7),
            "kind": spot_kind(t),
            "rank": 0 if "wikipedia" in t else (1 if "heritage" in t else (2 if "wikidata" in t else 3)),
        })
    raw.sort(key=lambda s: (s["name"], s["rank"], s["lat"], s["lon"], s["osm"]))
    # 同じ名前で 30m 以内は 1 つにまとめる (先に来た物を代表にする。featured は引き継ぐ)
    spots = []
    merged = 0
    for s in raw:
        dup = None
        for k in spots:
            if k["name"] == s["name"] and haversine_m(k["lat"], k["lon"], s["lat"], s["lon"]) <= DEDUP_M:
                dup = k
                break
        if dup:
            merged += 1
            if dup["kind"] in ("社寺", "碑・記念物", "その他") and s["kind"] not in ("社寺", "碑・記念物", "その他"):
                dup["kind"] = s["kind"]
        else:
            spots.append(dict(s))
    # 同じ名前で離れた印は、2 つ目から label を変えて画面で見分ける
    seen = {}
    for s in spots:
        seen[s["name"]] = seen.get(s["name"], 0) + 1
        n = seen[s["name"]]
        s["label"] = s["name"] if n == 1 else "%s（%d つ目の印）" % (s["name"], n)
        s["featured"] = (n == 1 and s["name"] in FEATURED_NAMES)
        s["boat_only"] = any(lat0 <= s["lat"] <= lat1 and lon0 <= s["lon"] <= lon1
                             for _, lat0, lat1, lon0, lon1 in BOAT_ONLY_BOXES)
        del s["rank"]
    return spots, {"raw_elements": len(raw), "merged": merged, "by_tag": tag_counts}


def nearest(lat, lon, items, pred=None):
    best = None
    for i, it in enumerate(items):
        if pred and not pred(it):
            continue
        d = haversine_m(lat, lon, it["lat"], it["lon"])
        if best is None or d < best[1]:
            best = (i, d)
    return best


def boundary_polylines(osm_path, max_points=1500):
    with open(osm_path, encoding="utf-8") as f:
        osm = json.load(f)
    rel = [e for e in osm["elements"] if e["type"] == "relation"][0]
    ways = [m["geometry"] for m in rel["members"]
            if m.get("type") == "way" and m.get("role") == "outer" and m.get("geometry")]
    total = sum(len(w) for w in ways)
    step = max(1, math.ceil(total / max_points))
    lines = []
    for w in ways:
        pts = [[round(p["lat"], 5), round(p["lon"], 5)] for p in w]
        keep = [pts[0]] + pts[1:-1:step] + [pts[-1]] if len(pts) > 1 else pts
        lines.append(keep)
    return lines, {"relation": rel["id"], "ways": len(ways), "points_before": total,
                   "points_after": sum(len(x) for x in lines)}


def percentile_stats(values):
    return {
        "median": round(statistics.median(values), 1),
        "mean": round(statistics.mean(values), 1),
        "max": round(max(values), 1),
        "min": round(min(values), 1),
    }


def build():
    shelters = load_shelters(os.path.join(ROOT, "data", "hinanbasho_hikone.csv"))
    hinanjo = load_hinanjo(os.path.join(ROOT, "data", "hinanjo_hikone.csv"))
    osm_path = os.path.join(ROOT, "data", "osm_hikone_poi.json")
    spots, spot_info = load_spots(osm_path)
    boundary, boundary_info = boundary_polylines(osm_path)

    for n, s in enumerate(spots):
        s["id"] = "S%03d" % (n + 1)
        res = {}
        for key, _, _ in HAZARDS:
            i, d = nearest(s["lat"], s["lon"], shelters, lambda x, k=key: k in x["hazards"])
            res[key] = {"i": i, "d": round(d), "m": walk_min(d)}
        i, d = nearest(s["lat"], s["lon"], shelters)
        res["any"] = {"i": i, "d": round(d), "m": walk_min(d)}
        j, dj = nearest(s["lat"], s["lon"], hinanjo)
        res["jo"] = {"i": j, "d": round(dj), "m": walk_min(dj)}
        s["near"] = res

    # 集計: 災害の種類ごと (+ 種類を問わない any と、避難所 jo)
    walk_spots = [s for s in spots if not s["boat_only"]]
    stats = {"spots": len(spots), "walkable": len(walk_spots), "boat_only": len(spots) - len(walk_spots),
             "long_walk_min": LONG_WALK_MIN, "by": {}}
    for key in [h[0] for h in HAZARDS] + ["any", "jo"]:
        mins = [s["near"][key]["m"] for s in walk_spots]
        st = percentile_stats(mins)
        st["over15"] = sum(1 for m in mins if m > LONG_WALK_MIN)
        st["under5"] = sum(1 for m in mins if m < 5)
        stats["by"][key] = st
    center = [s for s in spots if s["name"] == SAWAYAMA_CENTER_NAME]
    if center:
        c = center[0]
        saw = [s for s in spots if s["kind"] == "城・史跡"
               and haversine_m(c["lat"], c["lon"], s["lat"], s["lon"]) <= SAWAYAMA_RADIUS_M]
        stats["sawayama"] = {
            "names": [s["label"] for s in saw],
            "min": min(s["near"]["any"]["m"] for s in saw),
            "max": max(s["near"]["any"]["m"] for s in saw),
        }
    stats["basis"] = ("徒歩の分 = 直線距離(haversine) x 1.3 / 分速 80m、小数 1 桁。"
                      "災害の種類ごとの値は、その災害に印のある避難場所だけから最寄りを選ぶ。"
                      "any は印を問わない最寄り。jo は指定避難所の最寄り。"
                      "集計は船でしか行けない島の地点 (boat_only) を除いた徒歩で行ける地点が対象。")

    jst = timezone(timedelta(hours=9))
    data = {
        "generated_at": datetime.now(jst).strftime("%Y-%m-%d %H:%M JST"),
        "hazards": [{"key": k, "label": lab} for k, lab, _ in HAZARDS],
        "params": {"walk_factor": WALK_FACTOR, "speed_m_per_min": WALK_SPEED_M_PER_MIN,
                   "long_walk_min": LONG_WALK_MIN, "dedup_m": DEDUP_M},
        "sources": {
            "gsi": "国土地理院「指定緊急避難場所・指定避難所データ」(https://hinanmap.gsi.go.jp/index.html) をもとに作成（彦根市分を抽出・加工）。取得 2026-11-09",
            "osm": "© OpenStreetMap contributors (ODbL)。Overpass API から取得 2026-11-09",
        },
        "stats": stats,
        "spots": spots,
        "shelters": shelters,
        "hinanjo": hinanjo,
        "boundary": boundary,
        "build_info": {"spots": spot_info, "boundary": boundary_info},
    }
    return data


def embed(html_path, data):
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("<", "\\u003c")  # </script> を作らない
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    pat = re.compile(r"(<!--DATA-START-->).*?(<!--DATA-END-->)", re.S)
    if not pat.search(html):
        raise SystemExit("index.html に <!--DATA-START--> と <!--DATA-END--> の印がない")
    new = pat.sub(lambda m: m.group(1) + '<script id="data" type="application/json">' + blob + "</script>" + m.group(2), html)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="data.json の出力先フォルダ (指定時は index.html を更新しない)")
    args = ap.parse_args()
    data = build()
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, "data.json")
    else:
        path = os.path.join(ROOT, "app", "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    if not args.out:
        embed(os.path.join(ROOT, "app", "index.html"), data)
    st = data["stats"]
    print("wrote", path)
    print("spots", st["spots"], "build_info", json.dumps(data["build_info"], ensure_ascii=False))
    for k, v in st["by"].items():
        print(k, v)
    print("sawayama", st.get("sawayama"))


if __name__ == "__main__":
    main()
