'use strict';
const $ = id => document.getElementById(id);
let result = null;
let exampleData = null;
let generation = 0;
const mappingInputs = new Map();

function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function invalidate() {
  generation++;
  result = null;
  $('results').hidden = true;
  $('emptyState').hidden = false;
  $('resultBadge').textContent = 'AWAITING INPUT';
  $('allowPartial').checked = false;
  $('error').hidden = true;
}
function clearMappings() {
  mappingInputs.clear();
  $('missingMappings').replaceChildren();
  $('missingAddonNotice').hidden = true;
  $('convertButton').textContent = 'Convert to Fusion →';
}
function showError(message) {
  $('error').textContent = message;
  $('error').hidden = false;
}
function inputMode() {
  $('fileSource').hidden = $('inputMode').value !== 'file';
  $('pasteSource').hidden = $('inputMode').value !== 'paste';
}
async function api(path, body) {
  const response = await fetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid request. Check the export.');
  return data;
}
$('fusionForm').addEventListener('input', event => {
  if (['sourceFile', 'rawJson', 'inputMode'].includes(event.target.id)) {
    exampleData = null;
    clearMappings();
  }
  invalidate();
  inputMode();
});
$('fusionForm').addEventListener('submit', async event => {
  event.preventDefault();
  invalidate();
  const requestGeneration = generation;
  $('convertButton').disabled = true;
  $('inputStatus').textContent = 'Checking the layout and addon references…';
  try {
    let raw = exampleData;
    if (raw === null) {
      let text;
      if ($('inputMode').value === 'paste') text = $('rawJson').value;
      else {
        const file = $('sourceFile').files[0];
        if (!file) throw new Error('Choose your Nuvio collections or Fusion widgets JSON.');
        if (file.size > 5 * 1024 * 1024) throw new Error('The JSON file must be smaller than 5 MiB.');
        text = await file.text();
      }
      try { raw = JSON.parse(text); }
      catch { throw new Error('The source is not valid JSON. No export was generated.'); }
    }
    let mappings;
    try { mappings = JSON.parse($('addonUrls').value.trim() || '{}'); }
    catch { throw new Error('Addon URL mappings must be a JSON object.'); }
    if (!mappings || Array.isArray(mappings) || typeof mappings !== 'object' || Object.values(mappings).some(v => typeof v !== 'string')) {
      throw new Error('Addon URL mappings must map addon IDs to URL strings.');
    }
    for (const [id, input] of mappingInputs) if (input.value.trim()) mappings[id] = input.value.trim();
    const data = await api('/api/fusion/convert', {export_data: raw, addon_urls: mappings});
    if (requestGeneration !== generation) return;
    result = data;
    render();
    $('inputStatus').textContent = data.report.missingAddons.length
      ? 'Export blocked: paste the original addon manifest URL into each highlighted field, then convert again.'
      : data.report.canExport ? 'Conversion complete. Review compatibility before importing.' : 'Export blocked. Review the source issues before trying again.';
    if (data.report.missingAddons.length) mappingInputs.get(data.report.missingAddons[0].addonId)?.focus();
  } catch (err) {
    if (requestGeneration === generation) { showError(err.message); $('inputStatus').textContent = 'No export generated.'; }
  } finally { $('convertButton').disabled = false; }
});
for (const button of document.querySelectorAll('[data-preset]')) button.addEventListener('click', async () => {
  invalidate();
  clearMappings();
  const requestGeneration = generation;
  try {
    const data = await api('/api/presets/' + button.dataset.preset);
    if (requestGeneration !== generation) return;
    exampleData = data.rawData;
    $('inputMode').value = 'file';
    $('sourceFile').value = '';
    inputMode();
    $('inputStatus').textContent = 'Sanitized example loaded. Click Convert to Fusion. Example addon URLs are not live.';
  } catch (err) { if (requestGeneration === generation) showError(err.message); }
});
function render() {
  const report = result.report;
  $('results').hidden = false;
  $('emptyState').hidden = true;
  $('resultBadge').textContent = !report.canExport ? 'EXPORT BLOCKED' : report.complete ? 'READY TO REVIEW' : 'NEEDS ATTENTION';
  $('stats').replaceChildren();
  for (const [number, label, style] of [[report.widgets, 'Widgets', 'native'], [report.folders, 'Folders', 'native'],
    [report.counts.preserved, 'Sources kept', 'native'], [report.counts.unsupported, 'Sources omitted', 'unsupported']]) {
    const stat = element('div', undefined, 'stat');
    stat.append(element('strong', number, style), element('span', label));
    $('stats').append(stat);
  }
  $('resultSummary').textContent = `${report.inputFormat} → Fusion widget v1 · ${report.requiredAddonCount} required addons · ${report.issues.length} layout issues.`;
  $('coverage').textContent = !report.canExport ? report.exportBlockReason : report.complete
    ? 'All source references and supported layout fields were carried across. Live addon availability and import into your Fusion version still need checking.'
    : `${report.counts.unsupported} sources omitted; ${report.emptyFolders} empty folders; ${report.skippedWidgets} widgets omitted. Review the issues below. The download is marked partial.`;
  $('partialApproval').hidden = !report.canExport || !report.requiresPartialApproval;
  updateDownload();
  $('warnings').replaceChildren(...report.warnings.map(w => element('li', w)));
  $('issuesSection').hidden = report.issues.length === 0;
  $('issues').replaceChildren(...report.issues.map(issue => element('li', `${issue.path}: ${issue.message}${issue.fields ? ' Fields: ' + issue.fields.join(', ') : ''}`)));
  $('missingAddonNotice').hidden = report.missingAddons.length === 0;
  $('convertButton').textContent = report.missingAddons.length ? 'Connect addons & convert →' : 'Convert to Fusion →';
  for (const [id, input] of mappingInputs) {
    const missing = report.missingAddons.some(addon => addon.addonId === id);
    input.setAttribute('aria-required', String(missing));
    input.setAttribute('aria-invalid', String(missing));
  }
  for (const missing of report.missingAddons) {
    if (mappingInputs.has(missing.addonId)) continue;
    const input = element('input');
    input.id = 'addon-map-' + mappingInputs.size;
    input.type = 'text'; input.autocomplete = 'off'; input.spellcheck = false;
    input.setAttribute('aria-required', 'true');
    input.setAttribute('aria-invalid', 'true');
    input.placeholder = 'https://your-addon/config/manifest.json';
    const label = element('label', `Manifest URL for ${missing.addonId}`);
    label.htmlFor = input.id;
    $('missingMappings').append(label, input, element('p', `${missing.references} catalog reference${missing.references === 1 ? '' : 's'} need this exact addon instance. Copy its configured install URL (ending in /manifest.json) from Nuvio or your addon configuration page. A display name or the site's homepage is not enough.`, 'hint'));
    mappingInputs.set(missing.addonId, input);
  }
  renderTable();
  $('layoutSummary').textContent = `Widget layout (${report.widgets})`;
  $('layoutPreview').replaceChildren();
  for (const widget of result.fusionConfig?.widgets || result.previewWidgets) {
    const row = element('div', undefined, 'layout-entry');
    row.append(element('strong', widget.title));
    if (widget.type === 'collection.row') for (const folder of widget.dataSource.payload.items) {
      row.append(element('p', `${folder.title} · ${folder.imageAspect} · ${folder.dataSources.length} sources${folder.imageURL ? ' · cover retained' : ''}`));
    } else row.append(element('p', `${widget.type} · ${widget.dataSource.kind}`));
    $('layoutPreview').append(row);
  }
}
function updateDownload() {
  $('downloadFusion').disabled = !result?.report.canExport || (result.report.requiresPartialApproval && !$('allowPartial').checked);
}
$('allowPartial').addEventListener('change', updateDownload);
function renderTable() {
  if (!result) return;
  const query = $('search').value.toLowerCase(), status = $('statusFilter').value;
  $('reportBody').replaceChildren();
  for (const record of result.report.items) {
    if (status !== 'all' && record.status !== status) continue;
    if (!`${record.name} ${record.sourceId} ${record.reason} ${record.path}`.toLowerCase().includes(query)) continue;
    const row = element('tr'), source = element('td', record.name), outcome = element('td');
    source.append(element('small', `${record.sourceType} · ${record.sourceId || record.path}`));
    outcome.append(element('span', record.status === 'preserved' ? 'Preserved' : 'Needs attention', 'pill ' + (record.status === 'preserved' ? 'native' : 'unsupported')), element('p', record.reason));
    row.append(source, outcome);
    $('reportBody').append(row);
  }
}
$('search').addEventListener('input', renderTable);
$('statusFilter').addEventListener('change', renderTable);
function download(data, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
  const a = element('a'); a.href = url; a.download = name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('downloadFusion').addEventListener('click', () => {
  if (result?.fusionConfig && result.report.canExport && (!result.report.requiresPartialApproval || $('allowPartial').checked)) {
    download(result.fusionConfig, `fusion-widgets${result.report.complete ? '' : '-partial'}.json`);
  }
});
$('downloadReport').addEventListener('click', () => { if (result) download(result.report, 'fusion-compatibility-report.json'); });
