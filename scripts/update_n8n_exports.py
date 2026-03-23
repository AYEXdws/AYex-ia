from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/Users/ayexdws/Desktop")
REPO_DIR = Path("/Users/ayexdws/ayex-ia/automation/n8n/workflows")
PLACEHOLDER = "REPLACE_WITH_INGEST_TOKEN"
WRAPPER = """{{ JSON.stringify({
  type: $json.type || 'intel',
  source: $json.source || 'n8n',
  payload: {
    title: $json.title,
    summary: $json.summary,
    category: $json.category,
    importance: $json.importance,
    tags: $json.tags,
    timestamp: $json.timestamp || new Date().toISOString()
  }
}) }}"""

MACRO_CODE = """const forexData = $('Get USD/TRY Rate').first().json || {};
const goldData = $('Get Gold Price').first().json || {};

function num(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function parseGoldUsd(payload) {
  const direct = [
    payload?.gold,
    payload?.price,
    payload?.close,
    payload?.Close,
    payload?.last,
  ];
  for (const value of direct) {
    const parsed = num(value);
    if (parsed > 0) return parsed;
  }
  const blob = [
    typeof payload?.body === 'string' ? payload.body : '',
    typeof payload?.data === 'string' ? payload.data : '',
    typeof payload?.raw === 'string' ? payload.raw : '',
  ].filter(Boolean).join('\\n');
  if (!blob) return 0;
  const lines = blob.split(/\\r?\\n/).map((line) => line.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const parts = lines[i].split(',');
    if (parts.length < 5) continue;
    const close = num(parts[4]);
    if (close > 0) return close;
  }
  return 0;
}

const tryRate = num(forexData.rates?.TRY);
const eurRate = num(forexData.rates?.EUR);
const gbpRate = num(forexData.rates?.GBP);
const jpyRate = num(forexData.rates?.JPY);
const goldUsd = parseGoldUsd(goldData);

if (tryRate === 0) return [];

const eurTry = eurRate ? tryRate / eurRate : 0;
const gbpTry = gbpRate ? tryRate / gbpRate : 0;
const jpyTry = jpyRate ? tryRate / jpyRate : 0;
const eurUsd = eurRate ? (1 / eurRate) : 0;
const gbpUsd = gbpRate ? (1 / gbpRate) : 0;
const goldTry = goldUsd ? goldUsd * tryRate : 0;
const fxStress = tryRate > 41 || eurTry > 46 || gbpTry > 53;
const safeHaven = goldUsd > 4300 || goldTry > 180000;
const importPressure = tryRate > 38 || eurTry > 43;
const riskMode = fxStress && safeHaven ? 'savunmaci' : fxStress ? 'kur baskisi' : safeHaven ? 'guvenli liman' : 'dengeli';

const title = `Makro Ozet: USD/TRY ${tryRate.toFixed(2)} | EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'} | GBP/TRY ${gbpTry ? gbpTry.toFixed(2) : 'N/A'}`;
const summary =
  `USD/TRY ${tryRate.toFixed(2)} seviyesinde. ` +
  `EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'}, GBP/TRY ${gbpTry ? gbpTry.toFixed(2) : 'N/A'}, JPY/TRY ${jpyTry ? jpyTry.toFixed(4) : 'N/A'}. ` +
  `EUR/USD ${eurUsd ? eurUsd.toFixed(4) : 'N/A'}, GBP/USD ${gbpUsd ? gbpUsd.toFixed(4) : 'N/A'}. ` +
  `XAU/USD ${goldUsd ? goldUsd.toFixed(2) : 'N/A'}, ons altin TRY karsiligi ${goldTry ? goldTry.toFixed(0) : 'N/A'}. ` +
  `Risk modu su an ${riskMode}. Kur tarafi Turkiye odakli fiyatlama, ithalat maliyeti ve enflasyon beklentileri icin izlenmeli.`;

let importance = 6;
if (tryRate > 35 || eurTry > 38) importance = 7;
if (tryRate > 38 || eurTry > 41) importance = 8;
if (tryRate > 41 || eurTry > 44) importance = 9;
if (goldTry > 130000) importance = Math.max(importance, 7);
if (goldTry > 145000) importance = Math.max(importance, 8);
if (fxStress && safeHaven) importance = Math.max(importance, 9);

return [{
  json: {
    source: 'er_api',
    source_url: 'https://open.er-api.com/v6/latest/USD',
    source_type: 'market_api',
    type: 'intel',
    title,
    summary,
    category: 'economy',
    importance,
    tags: ['makro', 'usdtry', 'eurtry', 'gbptry', 'xauusd', riskMode],
    why_it_matters: 'Kur sepeti, dolar paritesi ve ons altin birlikte bakildiginda hem enflasyon baskisi hem de riskten kacis daha net okunur.',
    immediate_impact: `USD/TRY ${tryRate.toFixed(2)} | EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'} | XAU/USD ${goldUsd ? goldUsd.toFixed(2) : 'N/A'} | mod ${riskMode}`,
    possible_outcomes: [
      'Kur sepeti ve altin birlikte yukselirse savunmaci fiyatlama ve riskten kacis guclenebilir',
      'Kur sakinlesip altin gevserse kisa vadeli risk algisi yumusayabilir'
    ],
    confidence_hint: 0.9,
    source_quality: 'high',
    region: 'Turkey/Global',
    market_relevance: 'high',
    timestamp: new Date().toISOString()
  }
}];"""

WORLD_CODE = """const items = $input.all();
if (!Array.isArray(items) || items.length === 0) return [];

const cleanText = (v) => String(v || '').replace(/<[^>]*>/g, ' ').replace(/\\s+/g, ' ').trim();
const lower = (v) => cleanText(v).toLowerCase();
const has = (text, marker) => {
  const normalized = lower(text);
  const target = lower(marker);
  if (!target) return false;
  if (target.includes(' ') || target.includes('-') || target.includes('/')) return normalized.includes(target);
  const escaped = target.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(normalized);
};

const lowSignal = [
  'k-pop',
  'bts',
  'fans gather',
  'comeback show',
  'comeback',
  'onlyfans',
  'pornographic content',
  'celebrity',
  'showbiz',
  'entertainment',
  'influencer',
  'missing person',
  'abduction fears',
  'resurfaces after',
  'tv star',
  'viral clip',
  'wedding',
  'festival crowd',
  'city center celebration'
];

const strategicMarkers = ['war', 'conflict', 'troops', 'ground invasion', 'missile', 'ballistic', 'hezbollah', 'nuclear', 'attack', 'border', 'sanction', 'tariff', 'trade', 'oil', 'gas', 'energy', 'blackout', 'power grid'];
const politicalMarkers = ['election', 'president', 'prime minister', 'government', 'parliament', 'minister'];
const economicMarkers = ['trade', 'tariff', 'sanction', 'oil', 'gas', 'energy', 'blackout', 'power grid', 'workers', 'inflation', 'gdp', 'bank'];

const tagRules = [
  ['war', ['war', 'conflict', 'troops', 'ground invasion']],
  ['missile', ['missile', 'ballistic']],
  ['election', ['election', 'vote', 'poll']],
  ['trade', ['trade', 'tariff', 'sanction']],
  ['energy', ['energy', 'oil', 'gas', 'blackout', 'power grid']],
  ['israel', ['israel']],
  ['iran', ['iran']],
  ['lebanon', ['lebanon', 'hezbollah']],
  ['france', ['france', 'paris', 'marseille']],
  ['germany', ['germany']],
  ['india', ['india']],
  ['cuba', ['cuba']]
];

const pickCategory = (text) => {
  if (strategicMarkers.some((marker) => has(text, marker))) return 'global';
  if (politicalMarkers.some((marker) => has(text, marker))) return 'global';
  if (['economy', 'market', 'trade', 'gdp', 'inflation', 'bank', 'oil', 'energy', 'sanctions', 'tariff', 'workers'].some((marker) => has(text, marker))) return 'economy';
  if (['cyber', 'hack', 'breach', 'vulnerability', 'malware'].some((marker) => has(text, marker))) return 'security';
  if (['tech', 'software', 'chip', 'semiconductor', 'platform'].some((marker) => has(text, marker))) return 'tech';
  return 'global';
};

const pickImportance = (text) => {
  if (['breaking', 'urgent', 'crisis', 'emergency'].some((marker) => has(text, marker))) return 9;
  if (['war', 'attack', 'missile', 'nuclear', 'hezbollah', 'ground invasion'].some((marker) => has(text, marker))) return 8;
  if (['election', 'president', 'prime minister', 'government', 'trade', 'sanctions', 'tariff', 'blackout', 'power grid'].some((marker) => has(text, marker))) return 7;
  return 6;
};

const deriveTags = (text, category) => {
  const tags = [];
  for (const [tag, markers] of tagRules) {
    if (markers.some((marker) => has(text, marker)) && !tags.includes(tag)) tags.push(tag);
  }
  if (!tags.length) tags.push(category);
  return tags.slice(0, 5);
};

const rows = items
  .map((item) => {
    const row = item.json || {};
    const title = cleanText(row.title);
    const snippet = cleanText(row.contentSnippet || row.content || row.summary || '');
    const fullText = `${title} ${snippet}`;
    const category = pickCategory(fullText);
    const importance = pickImportance(fullText);
    const tags = deriveTags(fullText, category);
    const strategic = strategicMarkers.some((marker) => has(fullText, marker));
    const political = politicalMarkers.some((marker) => has(fullText, marker));
    const economic = economicMarkers.some((marker) => has(fullText, marker));
    return {
      title,
      summary: snippet.slice(0, 600),
      category,
      importance,
      tags,
      strategic,
      political,
      economic,
      link: row.link || 'https://bbc.com/news/world',
      isoDate: row.isoDate || new Date().toISOString(),
      low: lower(fullText),
      score: importance + (strategic ? 0.8 : 0) + (political ? 0.4 : 0) + (economic ? 0.4 : 0)
    };
  })
  .filter((row) => row.title && row.summary && row.summary.length >= 70)
  .filter((row) => !lowSignal.some((marker) => row.low.includes(marker)))
  .filter((row) => row.importance >= 7)
  .filter((row) => row.strategic || row.political || row.economic || row.importance >= 8)
  .sort((a, b) => b.score - a.score || new Date(b.isoDate).getTime() - new Date(a.isoDate).getTime())
  .slice(0, 3);

return rows.map((row) => ({
  json: {
    source: 'bbc_world',
    source_url: row.link,
    source_type: 'rss',
    type: 'intel',
    title: row.title,
    summary: row.summary,
    category: row.category,
    importance: row.importance,
    tags: row.tags,
    why_it_matters: 'Bu gelisme kuresel risk dengesi, diplomasi veya ekonomi akisina etki edebilir.',
    immediate_impact: 'Kisa vadeli etkisi izlenmeli.',
    possible_outcomes: ['Gelisme derinlesirse piyasa ve diplomasi etkisi buyuyebilir', 'Gerilim azalirsa risk algisi yumusayabilir'],
    confidence_hint: 0.84,
    source_quality: 'high',
    region: 'Global',
    market_relevance: row.category === 'economy' ? 'high' : 'medium',
    timestamp: row.isoDate
  }
}));"""


def update_send_event(node: dict) -> None:
    params = node.setdefault("parameters", {})
    params["method"] = "POST"
    params["url"] = "http://165.232.116.244:8000/events/ingest"
    params["sendHeaders"] = True
    params["headerParameters"] = {
        "parameters": [
            {
                "name": "x-ayex-ingest-token",
                "value": PLACEHOLDER,
            }
        ]
    }
    params["sendBody"] = True
    params["bodyContentType"] = "json"
    params["specifyBody"] = "json"
    params["jsonBody"] = WRAPPER
    params["authentication"] = "none"
    params["options"] = params.get("options", {})


def remove_login_and_rewire(doc: dict) -> None:
    doc["nodes"] = [node for node in doc["nodes"] if node.get("name") != "Login"]
    connections = doc.get("connections", {})
    if "Clean Intel Payload" in connections:
        connections["Clean Intel Payload"] = {
            "main": [[{"node": "Send Event to AYEX", "type": "main", "index": 0}]]
        }
    connections.pop("Login", None)


def main() -> None:
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    configs = [
        ("Macro Economy Feed v1.json", "Build Macro Intel Event", MACRO_CODE),
        ("World News Feed v1.json", "Build World News Event", WORLD_CODE),
    ]
    for filename, build_name, code in configs:
        src = ROOT / filename
        doc = json.loads(src.read_text(encoding="utf-8"))
        doc["name"] = filename.replace(" v1.json", " v2")
        for node in doc["nodes"]:
            if node.get("name") == build_name:
                node.setdefault("parameters", {})["jsCode"] = code
            elif node.get("name") == "Send Event to AYEX":
                update_send_event(node)
            elif filename == "World News Feed v1.json" and node.get("name") == "Onem Esigi":
                node["parameters"]["conditions"]["conditions"][0]["rightValue"] = 7
            elif filename == "World News Feed v1.json" and node.get("name") == "Schedule Trigger":
                node["parameters"]["rule"]["interval"][0]["minutesInterval"] = 60
            elif filename == "Macro Economy Feed v1.json" and node.get("name") == "Schedule Trigger":
                node["parameters"]["rule"]["interval"][0]["minutesInterval"] = 60
        remove_login_and_rewire(doc)
        if filename == "Macro Economy Feed v1.json":
            doc["connections"]["Schedule Trigger"] = {
                "main": [[
                    {"node": "Get USD/TRY Rate", "type": "main", "index": 0},
                    {"node": "Get Gold Price", "type": "main", "index": 0},
                ]]
            }
        out_name = filename.replace(" v1.json", " v2.json")
        out_path = ROOT / out_name
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (REPO_DIR / out_name).write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
