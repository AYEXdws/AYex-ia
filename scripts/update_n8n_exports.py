from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/Users/ayexdws/Desktop")
REPO_DIR = Path("/Users/ayexdws/ayex-ia/automation/n8n/workflows")
PLACEHOLDER = "REPLACE_WITH_INGEST_TOKEN"
WRAPPER = """={{ JSON.stringify({
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
}) }}\n"""

MACRO_CODE = """const forexData = $('Get USD/TRY Rate').first().json || {};
const goldData = $('Get Gold Price').first().json || {};
const brentData = $('Get Brent Price').first().json || {};
const us10yData = $('Get US 10Y Price').first().json || {};

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

function parseYahooChartClose(payload) {
  const result = payload?.chart?.result?.[0];
  const meta = result?.meta || {};
  const closes = result?.indicators?.quote?.[0]?.close || [];
  const valid = closes.filter((v) => Number.isFinite(Number(v))).map((v) => Number(v));
  const last = valid.length ? valid[valid.length - 1] : num(meta.regularMarketPrice);
  const prev = valid.length > 1 ? valid[valid.length - 2] : num(meta.chartPreviousClose || last);
  return {
    price: num(last),
    previous: num(prev || last),
  };
}

const tryRate = num(forexData.rates?.TRY);
const eurRate = num(forexData.rates?.EUR);
const gbpRate = num(forexData.rates?.GBP);
const jpyRate = num(forexData.rates?.JPY);
const goldUsd = parseGoldUsd(goldData);
const brent = parseYahooChartClose(brentData);

if (tryRate === 0) return [];

const eurTry = eurRate ? tryRate / eurRate : 0;
const gbpTry = gbpRate ? tryRate / gbpRate : 0;
const jpyTry = jpyRate ? tryRate / jpyRate : 0;
const eurUsd = eurRate ? (1 / eurRate) : 0;
const gbpUsd = gbpRate ? (1 / gbpRate) : 0;
const goldTry = goldUsd ? goldUsd * tryRate : 0;
const brentUsd = brent.price;
const brentChange = brentUsd && brent.previous ? ((brentUsd - brent.previous) / brent.previous) * 100 : 0;
const us10yRaw = parseYahooChartClose(us10yData).price;
const us10y = us10yRaw > 20 ? us10yRaw / 10 : us10yRaw;
const fxStress = tryRate > 41 || eurTry > 46 || gbpTry > 53;
const safeHaven = goldUsd > 4300 || goldTry > 180000;
const importPressure = tryRate > 38 || eurTry > 43;
const energyStress = brentUsd > 95 || brentChange > 4;
const rateStress = us10y >= 4.5;
const rateTight = us10y >= 4.2;
const riskMode = fxStress && safeHaven ? 'savunmaci'
  : fxStress ? 'kur baskisi'
  : safeHaven ? 'guvenli liman'
  : energyStress && rateStress ? 'enerji-ve-faiz-baskisi'
  : energyStress ? 'enerji-baskisi'
  : rateStress ? 'faiz-baskisi'
  : 'dengeli';

const title = `Makro Ozet: USD/TRY ${tryRate.toFixed(2)} | EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'} | GBP/TRY ${gbpTry ? gbpTry.toFixed(2) : 'N/A'}`;
const summary =
  `USD/TRY ${tryRate.toFixed(2)} seviyesinde. ` +
  `EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'}, GBP/TRY ${gbpTry ? gbpTry.toFixed(2) : 'N/A'}, JPY/TRY ${jpyTry ? jpyTry.toFixed(4) : 'N/A'}. ` +
  `EUR/USD ${eurUsd ? eurUsd.toFixed(4) : 'N/A'}, GBP/USD ${gbpUsd ? gbpUsd.toFixed(4) : 'N/A'}. ` +
  `XAU/USD ${goldUsd ? goldUsd.toFixed(2) : 'N/A'}, ons altin TRY karsiligi ${goldTry ? goldTry.toFixed(0) : 'N/A'}. ` +
  `Brent ${brentUsd ? brentUsd.toFixed(2) : 'N/A'} USD (${brentChange >= 0 ? '+' : ''}${brentChange.toFixed(2)}%). ` +
  `US 10Y ${us10y ? us10y.toFixed(2) : 'N/A'}%. ` +
  `Risk modu su an ${riskMode}. Kur tarafi Turkiye odakli fiyatlama, ithalat maliyeti, enerji maliyeti, global faiz baskisi ve enflasyon beklentileri icin izlenmeli.`;

let importance = 6;
if (tryRate > 35 || eurTry > 38) importance = 7;
if (tryRate > 38 || eurTry > 41) importance = 8;
if (tryRate > 41 || eurTry > 44) importance = 9;
if (goldTry > 130000) importance = Math.max(importance, 7);
if (goldTry > 145000) importance = Math.max(importance, 8);
if (energyStress) importance = Math.max(importance, 8);
if (rateTight) importance = Math.max(importance, 7);
if (rateStress) importance = Math.max(importance, 8);
if (fxStress && safeHaven) importance = Math.max(importance, 9);
if (energyStress && rateStress) importance = Math.max(importance, 9);
if (importPressure) importance = Math.max(importance, 8);

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
    tags: ['makro', 'usdtry', 'eurtry', 'gbptry', 'xauusd', 'brent', 'us10y', riskMode, importPressure ? 'ithalat-baskisi' : 'denge'],
    why_it_matters: 'Kur sepeti, dolar paritesi, ons altin, Brent ve ABD 10 yillik faiz birlikte bakildiginda enflasyon baskisi, enerji maliyeti, finansal kosullar ve riskten kacis daha net okunur.',
    immediate_impact: `USD/TRY ${tryRate.toFixed(2)} | EUR/TRY ${eurTry ? eurTry.toFixed(2) : 'N/A'} | XAU/USD ${goldUsd ? goldUsd.toFixed(2) : 'N/A'} | Brent ${brentUsd ? brentUsd.toFixed(2) : 'N/A'} | US10Y ${us10y ? us10y.toFixed(2) : 'N/A'} | mod ${riskMode}`,
    possible_outcomes: [
      'Kur sepeti, altin, Brent ve faiz birlikte yukselirse savunmaci fiyatlama ve maliyet baskisi guclenebilir',
      'Kur sakinlesip altin, Brent ve faiz gevserse kisa vadeli risk algisi yumusayabilir'
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
  'city center celebration',
  'dies at',
  'billionaire owner',
  'lifestyle blogger',
  'homesick',
  'pharmacist',
  'blogger',
  'civilians killed in the war',
  'civilian cost of war',
  'civilian cost',
  'profile-style story',
  'personal lives',
  'civilian toll',
  'families flee',
  'grieving families',
  'personal accounts',
  'survivors tell',
  'mourning families'
];

const hardStrategicMarkers = ['troops', 'ground invasion', 'missile', 'ballistic', 'hezbollah', 'nuclear', 'border', 'sanction', 'tariff', 'trade', 'oil', 'gas', 'energy', 'blackout', 'power grid', 'ceasefire', 'drone', 'air strike', 'hostage', 'shipping', 'red sea', 'refinery'];
const softConflictMarkers = ['war', 'conflict', 'attack', 'civilian', 'civilians', 'toll', 'killed'];
const politicalMarkers = ['election', 'vote', 'poll', 'snap election', 'coalition', 'parliament vote', 'cabinet collapse'];
const economicMarkers = ['trade', 'tariff', 'sanction', 'oil', 'gas', 'energy', 'blackout', 'power grid', 'shipping', 'red sea', 'refinery'];

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
  if (hardStrategicMarkers.some((marker) => has(text, marker))) return 'global';
  if (politicalMarkers.some((marker) => has(text, marker))) return 'global';
  if (['economy', 'market', 'trade', 'gdp', 'inflation', 'bank', 'oil', 'energy', 'sanctions', 'tariff', 'workers'].some((marker) => has(text, marker))) return 'economy';
  if (['cyber', 'hack', 'breach', 'vulnerability', 'malware'].some((marker) => has(text, marker))) return 'security';
  if (['tech', 'software', 'chip', 'semiconductor', 'platform'].some((marker) => has(text, marker))) return 'tech';
  return 'global';
};

const pickImportance = (text) => {
  if (['breaking', 'urgent', 'crisis', 'emergency'].some((marker) => has(text, marker))) return 9;
  if (['missile', 'nuclear', 'hezbollah', 'ground invasion', 'ballistic', 'sanction', 'tariff', 'oil', 'gas', 'energy', 'blackout', 'power grid'].some((marker) => has(text, marker))) return 8;
  if (['election', 'vote', 'poll', 'trade', 'sanctions', 'tariff', 'blackout', 'power grid', 'shipping', 'red sea'].some((marker) => has(text, marker))) return 7;
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
    const strategic = hardStrategicMarkers.some((marker) => has(fullText, marker));
    const softConflict = softConflictMarkers.some((marker) => has(fullText, marker));
    const political = politicalMarkers.some((marker) => has(fullText, marker));
    const economic = economicMarkers.some((marker) => has(fullText, marker));
    const profileLike = lowSignal.some((marker) => lower(fullText).includes(marker));
    return {
      title,
      summary: snippet.slice(0, 600),
      category,
      importance,
      tags,
      strategic,
      softConflict,
      political,
      economic,
      profileLike,
      link: row.link || 'https://bbc.com/news/world',
      isoDate: row.isoDate || new Date().toISOString(),
      low: lower(fullText),
      score: importance + (strategic ? 0.8 : 0) + (political ? 0.4 : 0) + (economic ? 0.4 : 0)
    };
  })
  .filter((row) => row.title && row.summary && row.summary.length >= 90)
  .filter((row) => !row.profileLike)
  .filter((row) => row.importance >= 8)
  .filter((row) => row.strategic || row.economic || (row.political && row.importance >= 9))
  .filter((row) => !(row.softConflict && !row.strategic && !row.economic))
  .sort((a, b) => b.score - a.score || new Date(b.isoDate).getTime() - new Date(a.isoDate).getTime())
  .slice(0, 1);

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

CYBER_CODE = """const items = $input.all();
if (!Array.isArray(items) || items.length === 0) return [];

const cleanText = (v) => String(v || '').replace(/<[^>]*>/g, ' ').replace(/\\s+/g, ' ').trim();
const lower = (v) => cleanText(v).toLowerCase();
const has = (text, marker) => lower(text).includes(String(marker || '').toLowerCase());
const securityMarkers = [
  'cve-', 'vulnerability', 'flaw', 'rce', 'remote code execution', 'actively exploited',
  'active exploitation', 'zero-day', 'zero day', 'ransomware', 'malware', 'phishing',
  'backdoor', 'botnet', 'data breach', 'breach', 'security update', 'patch', 'exploit',
  'critical', 'authentication bypass', 'privilege escalation', 'supply chain', 'infostealer',
  'ci/cd', 'secrets', 'firewall', 'attacker', 'attack'
];

const buildTags = (text) => {
  const low = lower(text);
  const tags = [];
  const add = (t) => { if (!tags.includes(t) && tags.length < 5) tags.push(t); };
  if (low.includes('cve-')) add('cve');
  if (low.includes('rce') || low.includes('remote code execution')) add('rce');
  if (low.includes('critical')) add('critical');
  if (low.includes('actively exploited') || low.includes('active exploitation')) add('exploited');
  if (low.includes('vulnerability') || low.includes('flaw')) add('vuln');
  if (low.includes('malware')) add('malware');
  if (low.includes('ransomware')) add('ransomware');
  if (low.includes('phishing')) add('phishing');
  if (low.includes('breach')) add('breach');
  if (low.includes('supply chain')) add('supply-chain');
  if (low.includes('infostealer')) add('infostealer');
  return tags;
};

const pickImportance = (text) => {
  const low = lower(text);
  if (low.includes('cve-') && (low.includes('critical') || low.includes('actively exploited'))) return 10;
  if (low.includes('known exploited') || low.includes('actively exploited') || low.includes('zero-day') || low.includes('zero day')) return 9;
  if (low.includes('remote code execution') || low.includes('rce') || low.includes('ransomware') || low.includes('data breach')) return 9;
  if (low.includes('critical') || low.includes('authentication bypass') || low.includes('privilege escalation')) return 8;
  if (low.includes('patch') || low.includes('vulnerability') || low.includes('malware') || low.includes('phishing') || low.includes('supply chain') || low.includes('infostealer')) return 7;
  return 6;
};

const sourceForLink = (link) => {
  const low = lower(link);
  if (low.includes('bleepingcomputer.com')) return 'bleeping_computer';
  if (low.includes('darkreading.com')) return 'dark_reading';
  return 'the_hacker_news';
};

return items
  .map((item) => {
    const row = item.json || {};
    const title = cleanText(row.title);
    const snippet = cleanText(row.contentSnippet || row.content || row.summary || '');
    const fullText = `${title} ${snippet}`.trim();
    const source = sourceForLink(row.link || '');
    const importance = pickImportance(fullText);
    const tags = buildTags(fullText);
    const securitySignal = securityMarkers.some((marker) => has(fullText, marker));
    return {
      json: {
        source,
        source_url: row.link || (source === 'dark_reading' ? 'https://www.darkreading.com/' : source === 'bleeping_computer' ? 'https://www.bleepingcomputer.com/' : 'https://thehackernews.com/'),
        source_type: 'rss',
        type: 'intel',
        title,
        summary: snippet.slice(0, 500),
        category: 'security',
        importance,
        tags,
        why_it_matters: 'Bu gelisme kisa vadede siber risk gorunumunu etkileyebilir.',
        immediate_impact: 'Etkilenen urun, aktif somuru sinyali ve yama gereksinimi izlenmeli.',
        possible_outcomes: ['Aktif somuru yayilirsa etki alani buyuyebilir', 'Yama uygulanirsa risk azalir'],
        confidence_hint: source === 'dark_reading' ? 0.8 : source === 'bleeping_computer' ? 0.78 : 0.82,
        source_quality: source === 'the_hacker_news' ? 'high' : 'medium_high',
        region: 'Global',
        market_relevance: 'medium',
        timestamp: row.isoDate || new Date().toISOString(),
        security_signal: securitySignal,
      }
    };
  })
  .filter((item) => item.json.title && item.json.summary && item.json.summary.length >= 40)
  .filter((item) => item.json.security_signal || item.json.tags.length >= 2 || item.json.importance >= 7)
  .map((item) => {
    delete item.json.security_signal;
    return item;
  });"""

CYBER_SCORE_CODE = """const item = $json;
const title = String(item.title || '').toLowerCase();
const summary = String(item.summary || '').toLowerCase();
let intelScore = Number(item.importance || 5);
if (title.includes('critical')) intelScore += 1;
if (title.includes('cve-')) intelScore += 1;
if (summary.includes('remote code execution') || summary.includes('rce')) intelScore += 2;
if (summary.includes('active exploitation') || summary.includes('actively exploited') || summary.includes('known exploited')) intelScore += 2;
if (summary.includes('zero-day') || summary.includes('zero day')) intelScore += 2;
if (summary.includes('ransomware') || summary.includes('data breach')) intelScore += 1;
if (summary.includes('missing authentication') || summary.includes('authentication bypass')) intelScore += 1;
intelScore = Math.min(intelScore, 10);
const shouldAlert = intelScore >= 7;
return { json: { ...item, intel_score: intelScore, should_alert: shouldAlert } };"""


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


def build_cyber_v2() -> dict:
    src = ROOT / "Cyber Feed v1-2.json"
    doc = json.loads(src.read_text(encoding="utf-8"))
    doc["name"] = "Cyber Feed v2"
    remove_login_and_rewire(doc)

    for node in doc["nodes"]:
        if node.get("name") == "Schedule Trigger":
            node["parameters"]["rule"]["interval"][0]["minutesInterval"] = 15
        elif node.get("name") == "Limit Latest Items":
            node["parameters"]["maxItems"] = 8
        elif node.get("name") == "Build Cyber Intel Event":
            node.setdefault("parameters", {})["jsCode"] = CYBER_CODE
        elif node.get("name") == "Score & Intelligence Engine":
            node.setdefault("parameters", {})["jsCode"] = CYBER_SCORE_CODE
        elif node.get("name") == "Onem Esigi":
            node["parameters"]["conditions"]["conditions"][0]["rightValue"] = 6
        elif node.get("name") == "Send Event to AYEX":
            update_send_event(node)

    doc["nodes"].append(
        {
            "parameters": {"url": "https://www.darkreading.com/rss.xml", "options": {}},
            "id": "cyber-rss-darkreading",
            "name": "RSS Read Dark Reading",
            "type": "n8n-nodes-base.rssFeedRead",
            "typeVersion": 1.2,
            "position": [64, -208],
        }
    )
    doc["nodes"].append(
        {
            "parameters": {"maxItems": 8},
            "id": "cyber-limit-darkreading",
            "name": "Limit Dark Reading Items",
            "type": "n8n-nodes-base.limit",
            "typeVersion": 1,
            "position": [224, -208],
        }
    )
    doc["nodes"].append(
        {
            "parameters": {"mode": "append"},
            "id": "cyber-merge",
            "name": "Combine Cyber Feeds",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3.2,
            "position": [320, -96],
        }
    )

    doc["connections"] = {
        "Schedule Trigger": {
            "main": [[
                {"node": "RSS Read", "type": "main", "index": 0},
                {"node": "RSS Read Dark Reading", "type": "main", "index": 0},
            ]]
        },
        "RSS Read": {"main": [[{"node": "Limit Latest Items", "type": "main", "index": 0}]]},
        "RSS Read Dark Reading": {"main": [[{"node": "Limit Dark Reading Items", "type": "main", "index": 0}]]},
        "Limit Latest Items": {"main": [[{"node": "Combine Cyber Feeds", "type": "main", "index": 0}]]},
        "Limit Dark Reading Items": {"main": [[{"node": "Combine Cyber Feeds", "type": "main", "index": 1}]]},
        "Combine Cyber Feeds": {"main": [[{"node": "Build Cyber Intel Event", "type": "main", "index": 0}]]},
        "Build Cyber Intel Event": {"main": [[{"node": "Score & Intelligence Engine", "type": "main", "index": 0}]]},
        "Score & Intelligence Engine": {"main": [[{"node": "Payload Valid mi", "type": "main", "index": 0}]]},
        "Payload Valid mi": {"main": [[], [{"node": "Onem Esigi", "type": "main", "index": 0}]]},
        "Onem Esigi": {"main": [[{"node": "Clean Intel Payload", "type": "main", "index": 0}]]},
        "Clean Intel Payload": {"main": [[{"node": "Send Event to AYEX", "type": "main", "index": 0}]]},
    }
    return doc


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
                node["parameters"]["conditions"]["conditions"][0]["rightValue"] = 8
            elif filename == "World News Feed v1.json" and node.get("name") == "Schedule Trigger":
                node["parameters"]["rule"]["interval"][0]["minutesInterval"] = 240
            elif filename == "Macro Economy Feed v1.json" and node.get("name") == "Schedule Trigger":
                node["parameters"]["rule"]["interval"][0]["minutesInterval"] = 60
        remove_login_and_rewire(doc)
        if filename == "Macro Economy Feed v1.json":
            doc["nodes"].append(
                {
                    "parameters": {
                        "url": "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?interval=1d&range=5d",
                        "options": {
                            "headerParameters": {
                                "parameters": [
                                    {"name": "User-Agent", "value": "Mozilla/5.0"},
                                    {"name": "Accept", "value": "application/json"},
                                ]
                            }
                        },
                    },
                    "id": "macro-brent",
                    "name": "Get Brent Price",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.4,
                    "position": [128, -96],
                }
            )
            doc["nodes"].append(
                {
                    "parameters": {
                        "url": "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval=1d&range=5d",
                        "options": {
                            "headerParameters": {
                                "parameters": [
                                    {"name": "User-Agent", "value": "Mozilla/5.0"},
                                    {"name": "Accept", "value": "application/json"},
                                ]
                            }
                        },
                    },
                    "id": "macro-us10y",
                    "name": "Get US 10Y Price",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.4,
                    "position": [128, 16],
                }
            )
            doc["connections"]["Schedule Trigger"] = {
                "main": [[
                    {"node": "Get USD/TRY Rate", "type": "main", "index": 0},
                    {"node": "Get Gold Price", "type": "main", "index": 0},
                    {"node": "Get Brent Price", "type": "main", "index": 0},
                    {"node": "Get US 10Y Price", "type": "main", "index": 0},
                ]]
            }
        out_name = filename.replace(" v1.json", " v2.json")
        out_path = ROOT / out_name
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (REPO_DIR / out_name).write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {out_path}")

    cyber_doc = build_cyber_v2()
    cyber_out = ROOT / "Cyber Feed v2.json"
    cyber_out.write_text(json.dumps(cyber_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPO_DIR / "Cyber Feed v2.json").write_text(cyber_out.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {cyber_out}")


if __name__ == "__main__":
    main()
