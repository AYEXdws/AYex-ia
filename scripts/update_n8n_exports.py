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

function num(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

const tryRate = num(forexData.rates?.TRY);
const eurRate = num(forexData.rates?.EUR);
const gbpRate = num(forexData.rates?.GBP);

if (tryRate === 0) return [];

const eurTry = eurRate ? tryRate / eurRate : 0;
const gbpTry = gbpRate ? tryRate / gbpRate : 0;
const eurUsd = eurRate ? (1 / eurRate) : 0;
const gbpUsd = gbpRate ? (1 / gbpRate) : 0;

const title = `Makro Ozet: USD/TRY ${tryRate.toFixed(2)} | EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'}`;
const summary =
  `USD/TRY ${tryRate.toFixed(2)} seviyesinde. ` +
  `EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'}, GBP/TRY ${gbpTry ? gbpTry.toFixed(2) : 'N/A'}. ` +
  `EUR/USD ${eurUsd ? eurUsd.toFixed(4) : 'N/A'}, GBP/USD ${gbpUsd ? gbpUsd.toFixed(4) : 'N/A'}. ` +
  `Kur tarafi su an Turkiye odakli fiyatlama ve enflasyon beklentileri icin izlenmeli.`;

let importance = 6;
if (tryRate > 35 || eurTry > 38) importance = 7;
if (tryRate > 38 || eurTry > 41) importance = 8;
if (tryRate > 41 || eurTry > 44) importance = 9;

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
    tags: ['makro', 'usdtry', 'eurtry', 'forex', 'turkiye'],
    why_it_matters: 'Kur tarafi enflasyon, fiyatlama davranisi ve risk istahi icin temel gostergedir.',
    immediate_impact: `USD/TRY ${tryRate.toFixed(2)} | EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'}`,
    possible_outcomes: [
      'Kur yukselisi surerse fiyatlama baskisi ve enflasyon beklentisi bozulabilir',
      'Kur sakinlesirse kisa vadeli risk algisi yumusayabilir'
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

const lowSignal = [
  'k-pop',
  'comeback show',
  'onlyfans',
  'pornographic content',
  'celebrity',
  'showbiz',
  'entertainment',
  'influencer'
];

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
  const low = lower(text);
  if (low.includes('war') || low.includes('attack') || low.includes('military') || low.includes('conflict') || low.includes('troops') || low.includes('missile') || low.includes('hezbollah') || low.includes('nuclear')) return 'global';
  if (low.includes('election') || low.includes('president') || low.includes('prime minister') || low.includes('government') || low.includes('parliament') || low.includes('minister')) return 'global';
  if (low.includes('economy') || low.includes('market') || low.includes('trade') || low.includes('gdp') || low.includes('inflation') || low.includes('bank') || low.includes('oil') || low.includes('energy') || low.includes('sanctions')) return 'economy';
  if (low.includes('cyber') || low.includes('hack') || low.includes('breach')) return 'security';
  if (low.includes('tech') || low.includes('ai') || low.includes('software')) return 'tech';
  return 'global';
};

const pickImportance = (text) => {
  const low = lower(text);
  if (low.includes('breaking') || low.includes('urgent') || low.includes('crisis') || low.includes('emergency')) return 9;
  if (low.includes('war') || low.includes('attack') || low.includes('missile') || low.includes('nuclear') || low.includes('hezbollah')) return 8;
  if (low.includes('election') || low.includes('president') || low.includes('prime minister') || low.includes('government')) return 7;
  if (low.includes('economy') || low.includes('market') || low.includes('inflation') || low.includes('trade') || low.includes('sanctions')) return 7;
  return 6;
};

const deriveTags = (text, category) => {
  const low = lower(text);
  const tags = [];
  for (const [tag, markers] of tagRules) {
    if (markers.some((marker) => low.includes(marker)) && !tags.includes(tag)) tags.push(tag);
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
    return {
      title,
      summary: snippet.slice(0, 600),
      category,
      importance,
      tags,
      link: row.link || 'https://bbc.com/news/world',
      isoDate: row.isoDate || new Date().toISOString(),
      low: lower(fullText)
    };
  })
  .filter((row) => row.title && row.summary && row.summary.length >= 40)
  .filter((row) => !lowSignal.some((marker) => row.low.includes(marker)))
  .filter((row) => row.importance >= 7)
  .slice(0, 8);

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
        for node in doc["nodes"]:
            if node.get("name") == build_name:
                node.setdefault("parameters", {})["jsCode"] = code
            elif node.get("name") == "Send Event to AYEX":
                update_send_event(node)
            elif filename == "World News Feed v1.json" and node.get("name") == "Onem Esigi":
                node["parameters"]["conditions"]["conditions"][0]["rightValue"] = 7
        remove_login_and_rewire(doc)
        out_name = filename.replace(" v1.json", " v2.json")
        out_path = ROOT / out_name
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (REPO_DIR / out_name).write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
