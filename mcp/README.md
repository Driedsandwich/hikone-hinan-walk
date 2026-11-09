# MCP サーバー（hikone-walk-shelter）

node だけで動く stdio の MCP サーバーです（依存なし・外へ通信しない）。`../app/data.json` を読みます。1 行に 1 つの JSON-RPC 2.0 メッセージを標準入力へ送ると、標準出力へ 1 行ずつ返します。

## 道具

| 名前 | 引数 | 返す物 |
|---|---|---|
| `nearest_shelter` | `lat`, `lon`, `hazard`（洪水・地震・土砂・内水氾濫。省略時は洪水） | 一番近い指定緊急避難場所（その災害に印のある場所）と一番近い指定避難所、直線距離（m）と徒歩の推定分 |
| `far_spots` | `min_minutes`（省略時 15）, `hazard`, `limit`（省略時 20） | 避難場所まで min_minutes 分以上の観光の地点を遠い順に。島の地点は除く |
| `spot_info` | `name`（部分一致）, `hazard` | その地点の最寄りの避難場所・避難所と分。同じ名前が複数あれば全部 |

返りは `content[0].text`（JSON の文字列）と `structuredContent`（同じ内容）です。注意の文（災害の時は指定緊急避難場所へ／分は推定／データは最新でない場合がある）と出典も入ります。引数が不正なときは `isError: true` で理由を返します。

## 使い方

Claude Code などの設定では、command に `node`、args に `mcp/server.mjs` の絶対パスを指定します。例（Claude Code）:

```
claude mcp add hikone-walk-shelter -- node /絶対パス/mcp/server.mjs
```

手で試す:

```
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"nearest_shelter","arguments":{"lat":35.2770307,"lon":136.2521014,"hazard":"洪水"}}}' \
 | node mcp/server.mjs
```

## 対応

`initialize`・`ping`・`tools/list`・`tools/call` と、`notifications/*`（返事なし）。バッチは未対応。標準入力が閉じると終了します。
