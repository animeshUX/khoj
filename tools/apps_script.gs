/**
 * Khoj submissions sheet → CSV web app.
 *
 * Serves the active spreadsheet as CSV with two enrichments the raw export
 * can't give us:
 *
 *   1. Hyperlink resolution — when a URL cell holds rich text like
 *      "Bernard Brooklyn Home... | Amber" with a link attached underneath
 *      (Google Sheets does this on "smart" paste), we substitute the
 *      underlying URL so the scraper sees a real http(s) string.
 *
 *   2. OpenGraph pre-fetch — for each URL row we fetch the page via
 *      UrlFetchApp (Google's IP space, not the CI runner's Azure block)
 *      and extract og:title / og:description into extra CSV columns.
 *      Sites like AmberStudent serve full OG metadata to Google but
 *      strip it for datacenter IPs. The pre-fetch is cached for 6h so
 *      repeated calls don't re-fetch every URL.
 *
 * Deploy:
 *   1. Extensions → Apps Script from the sheet.
 *   2. Replace Code.gs with this file.
 *   3. Project Settings → Script Properties → add KHOJ_KEY = <secret>.
 *      Required — doGet fails closed without it.
 *   4. Deploy → Manage deployments → Edit existing → New version → Deploy.
 *      The URL is stable, so the GitHub secret KHOJ_SUBMISSIONS_URL doesn't
 *      need to change.
 *
 * Call as: https://script.google.com/.../exec?key=<secret>
 */

const SHEET_NAME = 'Sheet1';  // change if your tab is named differently
const OG_CACHE_TTL_SECONDS = 21600;  // 6h — CacheService max is 21600

function doGet(e) {
  // Fail-closed: if KHOJ_KEY was never set (or got wiped during a redeploy),
  // the endpoint stays locked instead of silently serving the whole sheet.
  const requiredKey = PropertiesService.getScriptProperties().getProperty('KHOJ_KEY');
  if (!requiredKey || e.parameter.key !== requiredKey) {
    return textResponse('forbidden', ContentService.MimeType.TEXT);
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
  const range = sheet.getDataRange();
  const values = range.getValues();
  if (values.length === 0) return textResponse('', ContentService.MimeType.CSV);

  const richText = range.getRichTextValues();
  const header = values[0].map(v => String(v).trim());
  const urlCol = header.findIndex(h => h.toLowerCase() === 'url');

  // og_title + og_description are appended to whatever columns the sheet already has.
  // The scraper's csv.DictReader picks them up by name; sheets without the columns
  // get "" and the scraper falls back to a slug-derived title.
  const outHeader = header.concat(['og_title', 'og_description']);
  const rows = [outHeader];
  for (let r = 1; r < values.length; r++) {
    const row = values[r].slice();
    if (urlCol >= 0) {
      const cell = String(row[urlCol] || '').trim();
      if (!/^https?:\/\//i.test(cell)) {
        const link = extractLink(richText[r][urlCol]);
        if (link) row[urlCol] = link;
      }
    }
    const url = urlCol >= 0 ? String(row[urlCol] || '').trim() : '';
    const og = /^https?:\/\//i.test(url) ? fetchOg(url) : { title: '', description: '' };
    rows.push(row.concat([og.title, og.description]));
  }

  const csv = rows.map(r => r.map(csvEscape).join(',')).join('\n');
  return textResponse(csv, ContentService.MimeType.CSV);
}

function fetchOg(url) {
  const cache = CacheService.getScriptCache();
  // CacheService keys are limited to 250 chars; URLs can exceed that with utm params.
  // Truncating is fine — collisions across distinct listings are astronomically unlikely
  // at our scale, and even then a stale cached value is just a stale title.
  const key = 'og:' + url.substring(0, 240);
  const cached = cache.get(key);
  if (cached) return JSON.parse(cached);

  let title = '', description = '';
  try {
    const resp = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
      },
    });
    if (resp.getResponseCode() === 200) {
      const html = resp.getContentText();
      title = extractMeta(html, 'og:title')
        || extractMeta(html, 'twitter:title')
        || extractTitleTag(html);
      description = extractMeta(html, 'og:description')
        || extractMeta(html, 'description');
    }
  } catch (err) {
    // Swallow network errors — scraper will fall back to its own fetch / slug.
  }

  const out = { title: title.trim(), description: description.trim() };
  try { cache.put(key, JSON.stringify(out), OG_CACHE_TTL_SECONDS); } catch (err) {}
  return out;
}

function extractMeta(html, name) {
  // Walk every <meta ...> tag; match property= or name= against `name` in
  // either attribute order. Regex on raw HTML is fine here — we don't need
  // a real parser to pick a single attribute off a self-closing tag.
  const tagRx = /<meta\b[^>]*>/gi;
  const wantLower = name.toLowerCase();
  let m;
  while ((m = tagRx.exec(html)) !== null) {
    const tag = m[0];
    const propMatch = tag.match(/(?:property|name)\s*=\s*["']([^"']+)["']/i);
    if (!propMatch || propMatch[1].toLowerCase() !== wantLower) continue;
    const contentMatch = tag.match(/content\s*=\s*["']([^"']*)["']/i);
    if (contentMatch) return decodeEntities(contentMatch[1]);
  }
  return '';
}

function extractTitleTag(html) {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i);
  return m ? decodeEntities(m[1]) : '';
}

function decodeEntities(s) {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/gi, "'");
}

function extractLink(richText) {
  if (!richText) return null;
  const single = richText.getLinkUrl && richText.getLinkUrl();
  if (single && /^https?:\/\//i.test(single)) return single;
  // Mixed-format cell — first run with a link wins.
  const runs = richText.getRuns ? richText.getRuns() : [];
  for (const run of runs) {
    const u = run.getLinkUrl && run.getLinkUrl();
    if (u && /^https?:\/\//i.test(u)) return u;
  }
  return null;
}

function csvEscape(value) {
  const s = value === null || value === undefined ? '' : String(value);
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function textResponse(body, mime) {
  return ContentService.createTextOutput(body).setMimeType(mime);
}
