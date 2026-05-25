/**
 * Khoj submissions sheet → CSV web app.
 *
 * Serves the active spreadsheet as CSV at the deployment URL, with one twist:
 * if a URL cell holds title text but has a hyperlink attached (Google Sheets
 * does this when someone pastes a "rich" link or uses Insert → Link), we
 * substitute the underlying URL so the scraper sees a real http(s) string
 * instead of "Bernard Brooklyn Home... | Amber".
 *
 * Deploy:
 *   1. Extensions → Apps Script from the sheet.
 *   2. Replace Code.gs with this file.
 *   3. Project Settings → Script Properties → add KHOJ_KEY = <secret>
 *      (skip if you want the endpoint unauthenticated).
 *   4. Deploy → Manage deployments → Edit existing → New version → Deploy.
 *      The URL is stable, so the GitHub secret KHOJ_SUBMISSIONS_URL doesn't
 *      need to change.
 *
 * Call as: https://script.google.com/.../exec?key=<secret>
 */

const SHEET_NAME = 'Sheet1';  // change if your tab is named differently

function doGet(e) {
  const requiredKey = PropertiesService.getScriptProperties().getProperty('KHOJ_KEY');
  if (requiredKey && e.parameter.key !== requiredKey) {
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

  const rows = [header];
  for (let r = 1; r < values.length; r++) {
    const row = values[r].slice();
    if (urlCol >= 0) {
      const cell = String(row[urlCol] || '').trim();
      if (!/^https?:\/\//i.test(cell)) {
        const link = extractLink(richText[r][urlCol]);
        if (link) row[urlCol] = link;
      }
    }
    rows.push(row);
  }

  const csv = rows.map(r => r.map(csvEscape).join(',')).join('\n');
  return textResponse(csv, ContentService.MimeType.CSV);
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
