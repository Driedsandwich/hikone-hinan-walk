#!/usr/bin/env node
// 彦根のまち歩き x 避難場所: MCP の stdio サーバー (JSON-RPC 2.0、1 行 1 メッセージ、依存なし)
// 読むのは ../app/data.json だけ。外へ通信しない。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = JSON.parse(readFileSync(join(HERE, "..", "app", "data.json"), "utf8"));
const { spots, shelters, hinanjo } = DATA;
const P = DATA.params;

const SERVER_INFO = { name: "hikone-walk-shelter", version: "0.1.0" };
const SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"];

// 災害の種類: 日本語の名前も英語のキーも受ける
const HZ_ALIAS = {
  "洪水": "flood", "flood": "flood",
  "地震": "quake", "quake": "quake", "earthquake": "quake",
  "土砂": "slope", "崖崩れ": "slope", "slope": "slope", "landslide": "slope",
  "内水氾濫": "inner", "内水": "inner", "inner": "inner",
};
const HZ_LABEL = { flood: "洪水", quake: "地震", slope: "土砂（崖崩れ、土石流及び地滑り）", inner: "内水氾濫" };
const HZ_SHORT = { flood: "洪水", quake: "地震", slope: "土砂", inner: "内水氾濫" };

const NOTES = [
  "徒歩の分は、直線距離 x " + P.walk_factor + " を分速 " + P.speed_m_per_min + "m で割った推定です。山道・階段・浸水・通行止めは入っていません。",
  "災害の時は、指定避難所ではなく指定緊急避難場所へ避難してください。",
  "避難場所のデータは市町村の登録で、最新でない場合があります。最新かつ詳細の状況は必ず彦根市に確認してください。",
];
const SOURCE = DATA.sources.gsi + " / " + DATA.sources.osm;

function haversineM(lat1, lon1, lat2, lon2) {
  const r = 6371008.8, rad = Math.PI / 180;
  const p1 = lat1 * rad, p2 = lat2 * rad, dp = p2 - p1, dl = (lon2 - lon1) * rad;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}
function walkMin(d) { return Math.round((d * P.walk_factor / P.speed_m_per_min) * 10) / 10; }

function nearestOf(lat, lon, items, pred) {
  let best = null;
  items.forEach((it, i) => {
    if (pred && !pred(it)) return;
    const d = haversineM(lat, lon, it.lat, it.lon);
    if (!best || d < best.d) best = { i, d };
  });
  return best;
}
function placeOut(it, b) {
  return { name: it.name, address: it.address, lat: it.lat, lon: it.lon,
           distance_m: Math.round(b.d), walk_minutes: walkMin(b.d) };
}
function band(m) { return m < 5 ? "5 分未満" : (m <= 15 ? "5〜15 分" : "15 分を超える"); }

function parseHazard(v) {
  if (v === undefined || v === null || v === "") return "flood";
  const k = HZ_ALIAS[String(v).trim()];
  if (!k) throw new Error("hazard は 洪水・地震・土砂・内水氾濫 のどれかです: " + v);
  return k;
}
function num(v, name) {
  const n = typeof v === "string" && v.trim() !== "" ? Number(v) : v;
  if (typeof n !== "number" || !Number.isFinite(n)) throw new Error(name + " は数値で指定してください");
  return n;
}

function spotOut(s, hz) {
  const n = s.near[hz], sh = shelters[n.i], jr = s.near.jo, hj = hinanjo[jr.i];
  return {
    id: s.id, name: s.label, kind: s.kind, lat: s.lat, lon: s.lon, osm: s.osm,
    boat_only: !!s.boat_only,
    hazard: HZ_SHORT[hz],
    nearest_shelter: { name: sh.name, address: sh.address, lat: sh.lat, lon: sh.lon,
                       distance_m: n.d, walk_minutes: n.m, band: band(n.m) },
    nearest_hinanjo: { name: hj.name, address: hj.address, lat: hj.lat, lon: hj.lon,
                       distance_m: jr.d, walk_minutes: jr.m },
    ...(s.boat_only ? { warning: "琵琶湖の島で、船が必要です。徒歩の分は参考になりません。" } : {}),
  };
}

const TOOLS = [
  {
    name: "nearest_shelter",
    description: "緯度と経度と災害の種類から、彦根市内で一番近い指定緊急避難場所（その災害に印のある場所だけから選ぶ）と、一番近い指定避難所、それぞれまでの直線距離と徒歩の推定分を返す。データは彦根市分だけ。",
    inputSchema: {
      type: "object",
      properties: {
        lat: { type: "number", description: "緯度（例 35.2770307）" },
        lon: { type: "number", description: "経度（例 136.2521014）" },
        hazard: { type: "string", enum: ["洪水", "地震", "土砂", "内水氾濫"], description: "災害の種類。省略時は洪水" },
      },
      required: ["lat", "lon"],
      additionalProperties: false,
    },
  },
  {
    name: "far_spots",
    description: "観光の地点のうち、一番近い指定緊急避難場所まで徒歩の推定分が min_minutes 以上の地点を、遠い順に返す。船でしか行けない島の地点は除く。",
    inputSchema: {
      type: "object",
      properties: {
        min_minutes: { type: "number", description: "分の下限（省略時は 15）" },
        hazard: { type: "string", enum: ["洪水", "地震", "土砂", "内水氾濫"], description: "災害の種類。省略時は洪水" },
        limit: { type: "integer", description: "返す件数の上限（省略時は 20）" },
      },
      additionalProperties: false,
    },
  },
  {
    name: "spot_info",
    description: "観光の地点の名前（部分一致）から、その地点の一番近い避難場所・避難所と徒歩の推定分を返す。同じ名前の地点が複数あるときはすべて返す。",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "地点の名前（例 彦根城）" },
        hazard: { type: "string", enum: ["洪水", "地震", "土砂", "内水氾濫"], description: "災害の種類。省略時は洪水" },
      },
      required: ["name"],
      additionalProperties: false,
    },
  },
];

function callTool(name, args) {
  args = args || {};
  if (name === "nearest_shelter") {
    const lat = num(args.lat, "lat"), lon = num(args.lon, "lon");
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new Error("緯度経度の範囲が不正です");
    const hz = parseHazard(args.hazard);
    const b = nearestOf(lat, lon, shelters, (x) => x.hazards.includes(hz));
    const j = nearestOf(lat, lon, hinanjo);
    const out = {
      query: { lat, lon, hazard: HZ_LABEL[hz] },
      nearest_shelter: { ...placeOut(shelters[b.i], b), designated_for: shelters[b.i].hazards.map((k) => HZ_SHORT[k]) },
      nearest_hinanjo: placeOut(hinanjo[j.i], j),
      notes: NOTES, source: SOURCE,
    };
    if (b.d > 10000) out.warning = "指定した地点は、最寄りの避難場所から 10km 以上離れています。データは彦根市分だけなので、彦根市の外では使えません。";
    return out;
  }
  if (name === "far_spots") {
    const min = args.min_minutes === undefined ? P.long_walk_min : num(args.min_minutes, "min_minutes");
    const limit = args.limit === undefined ? 20 : Math.max(1, Math.floor(num(args.limit, "limit")));
    const hz = parseHazard(args.hazard);
    const hits = spots.filter((s) => !s.boat_only && s.near[hz].m >= min)
      .sort((a, b) => b.near[hz].m - a.near[hz].m || a.id.localeCompare(b.id));
    return {
      query: { min_minutes: min, hazard: HZ_LABEL[hz], limit },
      total_matches: hits.length,
      walkable_spots: spots.filter((s) => !s.boat_only).length,
      spots: hits.slice(0, limit).map((s) => ({
        id: s.id, name: s.label, kind: s.kind, lat: s.lat, lon: s.lon,
        walk_minutes: s.near[hz].m, distance_m: s.near[hz].d,
        nearest_shelter: shelters[s.near[hz].i].name,
      })),
      notes: NOTES, source: SOURCE,
    };
  }
  if (name === "spot_info") {
    const q = String(args.name ?? "").trim();
    if (!q) throw new Error("name を指定してください");
    const hz = parseHazard(args.hazard);
    let hits = spots.filter((s) => s.name === q || s.label === q);
    if (!hits.length) hits = spots.filter((s) => s.name.includes(q) || s.label.includes(q));
    return {
      query: { name: q, hazard: HZ_LABEL[hz] },
      matches: hits.length,
      spots: hits.slice(0, 10).map((s) => spotOut(s, hz)),
      ...(hits.length > 10 ? { truncated: "先頭 10 件だけ返しています。名前をもっと具体的にしてください。" } : {}),
      ...(hits.length ? {} : { hint: "該当する地点がありません。観光の地点は OpenStreetMap に登録された物だけです。" }),
      notes: NOTES, source: SOURCE,
    };
  }
  const e = new Error("unknown tool: " + name);
  e.code = -32602;
  throw e;
}

function send(msg) { process.stdout.write(JSON.stringify(msg) + "\n"); }
function reply(id, result) { send({ jsonrpc: "2.0", id, result }); }
function fail(id, code, message) { send({ jsonrpc: "2.0", id: id ?? null, error: { code, message } }); }

function handle(msg) {
  const { id, method, params } = msg;
  const isNotification = id === undefined || id === null;
  if (typeof method !== "string") { if (!isNotification) fail(id, -32600, "Invalid Request"); return; }
  if (method === "initialize") {
    const want = params && params.protocolVersion;
    return reply(id, {
      protocolVersion: SUPPORTED.includes(want) ? want : SUPPORTED[0],
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
      instructions: "彦根市の観光の地点から、一番近い指定緊急避難場所までの徒歩の推定分を返す。分は直線距離 x 1.3 を分速 80m で割った推定。災害の時は指定避難所ではなく指定緊急避難場所へ。",
    });
  }
  if (method.startsWith("notifications/")) return; // 返事はしない
  if (isNotification) return;
  if (method === "ping") return reply(id, {});
  if (method === "tools/list") return reply(id, { tools: TOOLS });
  if (method === "tools/call") {
    const name = params && params.name;
    if (!TOOLS.some((t) => t.name === name)) return fail(id, -32602, "unknown tool: " + name);
    try {
      const out = callTool(name, params.arguments);
      return reply(id, { content: [{ type: "text", text: JSON.stringify(out) }], structuredContent: out, isError: false });
    } catch (e) {
      return reply(id, { content: [{ type: "text", text: String(e.message || e) }], isError: true });
    }
  }
  return fail(id, -32601, "Method not found: " + method);
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on("line", (line) => {
  line = line.trim();
  if (!line) return;
  let msg;
  try { msg = JSON.parse(line); } catch { return fail(null, -32700, "Parse error"); }
  if (Array.isArray(msg)) return fail(null, -32600, "batch は未対応です");
  try { handle(msg); } catch (e) { fail(msg && msg.id, -32603, "Internal error: " + (e && e.message)); }
});
rl.on("close", () => process.exit(0));
