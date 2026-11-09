# 彦根市まち歩き地図 データの出どころ（取得: 2026-11-09 10:44〜10:46 JST）

HTTP 取得は合計 7 回（上限 8）。User-Agent は x189-hikone-map/0.1。

取得の記録（date コマンドの時刻）:
1. 10:44:46 https://www.gsi.go.jp/bousaichiri/hinanbasho.html （入口の頁）
2. 10:45 頃 https://hinanmap.gsi.go.jp/index.html （「ご利用上の注意」同意の頁。リンク先）
3. 10:45 頃 https://hinanmap.gsi.go.jp/hinanjocp/hinanbasho/koukaidate.html （都道府県・市町村別ダウンロード一覧。CSV の項目定義と取得経路が書かれている）
4. 10:45:20 https://hinanmap.gsi.go.jp/hinanjocp/defaultFtpData/csv/25202_2.csv
5. 10:45:23 https://hinanmap.gsi.go.jp/hinanjocp/defaultFtpData/csv/25202_1.csv
6. 10:45:34 https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html （国土地理院コンテンツ利用規約）
7. 10:45:45 https://overpass-api.de/api/interpreter （POST 1 回）

CSV の URL の根拠: 3 の頁の JavaScript が、市町村コード + `_2` を指定緊急避難場所、`_1` を指定避難所として
`../defaultFtpData/csv/<コード>_<番号>.csv` を取る作りになっている（頁の dlFile 関数と各ボタンの引数から読んだ。ブラウザでのボタン操作は実施していない）。
市町村コードは 25202（彦根市）。

## 1. data/hinanbasho_hikone.csv（指定緊急避難場所）
- 元 URL: https://hinanmap.gsi.go.jp/hinanjocp/defaultFtpData/csv/25202_2.csv
- 取得: 2026-11-09 10:45:20 JST
- 件数: データ行 63（ヘッダ除く）。元が彦根市単独の CSV なので抜き出しはしていない。
- 文字コード: 元は UTF-8（BOM 付き）。保存時に BOM だけ外した UTF-8。内容は無加工。
- 列（16）: NO, 共通ID, 施設・場所名, 住所, 洪水, 崖崩れ、土石流及び地滑り, 高潮, 地震, 津波, 大規模な火事, 内水氾濫, 火山現象, 指定避難所との住所同一, 緯度, 経度, 備考
- 印の意味（頁の原文）: 「該当は「1」、非該当は無記入」
- 印の付いた行数: 洪水 62／崖崩れ、土石流及び地滑り 63／高潮 0／地震 62／津波 0／大規模な火事 0／内水氾濫 62／火山現象 0／指定避難所との住所同一 18。緯度・経度の空欄 0 行。備考の記入 0 行。

## 2. data/hinanjo_hikone.csv（指定避難所）
- 元 URL: https://hinanmap.gsi.go.jp/hinanjocp/defaultFtpData/csv/25202_1.csv
- 取得: 2026-11-09 10:45:23 JST
- 件数: データ行 18。文字コードの扱いは上と同じ。
- 列（10）: NO, 共通ID, 施設・場所名, 住所, 指定緊急避難場所との住所同一, その他市町村長が必要と認める事項, 受入対象者, 緯度, 経度, 備考
- 「指定緊急避難場所との住所同一」は 18 行すべてが 1。緯度・経度の空欄 0 行。

## 利用条件と出典（CSV）
- 規約: 国土地理院コンテンツ利用規約（令和7年11月20日改正） https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html
  - 原文: 「本サイトのコンテンツには特段の記載が無い限り公共データ利用規約（第1.0 版）（PDL1.0）が適用されています。」
  - 出典（原文）: 「コンテンツを利用する際は、出典を記載してください。…（出典記載例）出典：国土地理院ウェブサイト （当該ページのURL）」
  - 加工（原文）: 「コンテンツを編集・加工等して利用する場合は、上記出典とは別に、編集・加工等を行ったことを記載してください。…「○○データ」（国土地理院） （当該ページの URL）をもとに○○株式会社作成 … 編集・加工した情報を、あたかも国土地理院が作成したかのような態様で公表・利用してはいけません。」
- データ配布頁（https://hinanmap.gsi.go.jp/index.html）の注意（原文）: 「指定緊急避難場所・指定避難所データ…を利用される場合は、国土地理院コンテンツ利用規約のほか、以下のご利用上の注意をご確認いただき、内容に同意された場合のみご利用ください。」
  - 「最新でない場合や未掲載の場合があるため、最新かつ詳細の状況などは必ず当該市町村にご確認ください。」
  - 「本データを用いた情報を第三者に提供する場合は、上記1．～3．の注意事項が正確に伝わるよう、十分にご留意ください。」（1=市町村の登録で最新でない場合がある／2=緊急避難場所と避難所の違い・災害種別ごとの指定／3=随時更新）
- 入口の頁（https://www.gsi.go.jp/bousaichiri/hinanbasho.html）の原文: 「閲覧・提供データは市町村が登録しかつ公開の同意を得たものに限る」「災害発生時には、指定避難所ではなく、指定緊急避難場所へ避難してください。」
- 書き方の案（規約の出典例に沿った形）: 「出典：国土地理院「指定緊急避難場所・指定避難所データ」 https://hinanmap.gsi.go.jp/index.html をもとに作成（彦根市分を抽出・加工）」
- 未確認: koukaidate 頁が「最終更新日」を JavaScript で後から表示する作りのため、彦根市の公開日・最終更新日は取っていない（取得回数を温存）。ZIP に同梱される「ご利用上の注意.txt」（`../assets/notice/ご利用上の注意.txt`）は取っていない。免責頁 https://www.gsi.go.jp/bousaichiri/hinanbasho-menseki.html も取っていない。

## 3. data/osm_hikone_poi.json（OpenStreetMap・Overpass の JSON のまま）
- 元: https://overpass-api.de/api/interpreter （POST 1 回）
- 取得: 2026-11-09 10:45:45 JST。Overpass の osm3s.timestamp_osm_base = 2026-11-09T01:44:35Z（OSM 本体の時点）、timestamp_areas_base = 2026-11-08T22:01:51Z
- 問い合わせ文（そのまま）:
```
[out:json][timeout:180];
rel["name"="彦根市"]["admin_level"="7"]["boundary"="administrative"]->.b;
.b map_to_area->.a;
(
  nwr(area.a)["tourism"~"^(attraction|museum|viewpoint)$"]["name"];
  nwr(area.a)["tourism"="information"]["information"!="board"]["name"];
  nwr(area.a)["historic"~"^(castle|monument|memorial|temple|shrine|city_gate|ruins|archaeological_site)$"]["name"];
  nwr(area.a)["amenity"="place_of_worship"]["name"];
  nwr(area.a)["railway"="station"]["name"~"彦根"];
);
out center tags;
.b out geom;
```
  - 注意: 指示の「historic=castle|monument|memorial|temple 系」は、上の値（castle, monument, memorial, temple, shrine, city_gate, ruins, archaeological_site）に解釈した。historic=temple 自体は 0 件。駅（railway=station・名前に彦根）は、彦根駅の座標を得るために同じ問い合わせへ足した。
- 要素数: 233（node 189・way 43・relation 1）。relation 1 は行政界（彦根市・relation 722198・admin_level=7・outer の way 21 本・out geom で座標つき・bounds: 緯度 35.190164〜35.3560088／経度 136.0836998〜136.351597）。
- 地点 232（すべて name あり）。内訳（タグ別・重なりは別々に数える）: amenity=place_of_worship 132／historic=memorial 25／historic=castle 9／historic=monument 3／historic=ruins 1／railway=station 4／tourism=information 44（information 値: map 21・guidepost 19・office 3・値なし 1）／tourism=attraction 5／tourism=museum 5／tourism=viewpoint 5／tourism=artwork 1（historic 側で当たった物）。
- tourism タグのある名前つきの地点: 60。
- 彦根城（name に「彦根城」を含む）: 13 件。うち historic=castle の way 209262408「彦根城」（国宝・wikidata Q1012374・center 35.2770307, 136.2521014）と way 363244224「彦根城」（天守・center 35.2764824, 136.2519245）、tourism=museum の way 363244231「彦根城博物館」（center 35.2756185, 136.2536182）。
- 出典の書き方: 「© OpenStreetMap contributors」＋ライセンス ODbL（Overpass の応答内の原文: "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."）。OSM の著作権頁は取っていない（回数温存）ので、頁の原文は未確認。ODbL の継承条項（加工した派生データベースの公開条件）はこの調べでは確かめていない。

## 3b. 中心の座標（上の JSON から読んだ値）
- 彦根駅（JR・node 3630162090・ref JR-A13）: 緯度 35.2722017／経度 136.2633658
- 彦根駅（近江鉄道・node 11449234789・ref OR04）: 緯度 35.2717159／経度 136.2635056
- 彦根城（way 209262408 の center）: 緯度 35.2770307／経度 136.2521014
- 行政界の外形: osm_hikone_poi.json の最後の要素（type=relation・id 722198）の members[].geometry
