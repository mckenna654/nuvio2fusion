// State Management
let currentRawData = null;
let currentAioConfig = null;
let currentCatalogs = [];

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  setupDropZone();
});

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(el => {
    el.classList.remove('active', 'border-purple-500', 'text-purple-400');
    el.classList.add('border-transparent', 'text-slate-400');
  });

  const activeContent = document.getElementById(tabId);
  const activeBtn = document.getElementById('btn-' + tabId);

  if (activeContent) activeContent.classList.remove('hidden');
  if (activeBtn) {
    activeBtn.classList.add('active', 'border-purple-500', 'text-purple-400');
    activeBtn.classList.remove('border-transparent', 'text-slate-400');
  }
}

// Drag & Drop Setup
function setupDropZone() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');

  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add('border-purple-500', 'bg-purple-950/20');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-purple-500', 'bg-purple-950/20');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
      handleFileSelected({ target: fileInput });
    }
  });
}

function handleFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  document.getElementById('fileStatusText').innerHTML = `Selected: <span class="text-purple-400 font-semibold">${file.name}</span>`;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      currentRawData = JSON.parse(e.target.result);
      showToast(`Loaded ${file.name}`, 'success');
      triggerConversion();
    } catch (err) {
      showToast('Invalid JSON file format', 'error');
    }
  };
  reader.readAsText(file);
}

// Process Raw Text
function processRawJson() {
  const rawText = document.getElementById('rawJsonInput').value.trim();
  if (!rawText) {
    showToast('Please paste JSON content', 'error');
    return;
  }
  try {
    currentRawData = JSON.parse(rawText);
    showToast('Parsed JSON successfully', 'success');
    triggerConversion();
  } catch (err) {
    showToast('Failed to parse JSON string', 'error');
  }
}

// Fetch Remote Manifest
async function fetchManifest() {
  const url = document.getElementById('manifestUrl').value.trim();
  if (!url) {
    showToast('Please enter a manifest URL', 'error');
    return;
  }

  showToast('Fetching manifest...', 'info');
  try {
    const res = await fetch('/api/nuvio/manifest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        manifest_url: url,
        addon_name: document.getElementById('optAddonName').value.trim() || 'AIOMetadata',
        prefix_mode: document.getElementById('optPrefixMode').value
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to fetch manifest');

    updateResults(data);
    showToast(`Loaded ${data.totalCatalogs} catalogs from manifest!`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Login Nuvio
async function loginNuvio() {
  const email = document.getElementById('nuvioEmail').value.trim();
  const password = document.getElementById('nuvioPassword').value;

  if (!email || !password) {
    showToast('Please enter Nuvio email and password', 'error');
    return;
  }

  showToast('Connecting to Nuvio account...', 'info');
  try {
    const res = await fetch('/api/nuvio/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        addon_name: document.getElementById('optAddonName').value.trim() || 'AIOMetadata',
        prefix_mode: document.getElementById('optPrefixMode').value
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to login to Nuvio');

    updateResults(data);
    showToast(`Successfully pulled ${data.totalCatalogs} catalogs from Nuvio!`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Trigger Conversion
async function triggerConversion() {
  if (!currentRawData) {
    showToast('Please provide an input source first', 'error');
    return;
  }

  const addonName = document.getElementById('optAddonName').value.trim() || 'AIOMetadata';
  const prefixMode = document.getElementById('optPrefixMode').value;
  const ratingPosters = document.getElementById('optRatingPosters').checked;
  const enableAll = document.getElementById('optEnableAll').checked;

  let baseConfig = null;
  const baseFileInput = document.getElementById('baseConfigInput');
  if (baseFileInput.files && baseFileInput.files[0]) {
    try {
      const baseText = await baseFileInput.files[0].text();
      baseConfig = JSON.parse(baseText);
    } catch (e) {
      console.warn('Could not parse base config JSON', e);
    }
  }

  try {
    const res = await fetch('/api/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nuvio_data: currentRawData,
        base_config: baseConfig,
        addon_name: addonName,
        prefix_mode: prefixMode,
        force_enabled: enableAll ? true : null,
        force_rating_posters: ratingPosters,
        allow_duplicates: false
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Conversion failed');

    updateResults(data);
    showToast(`Successfully generated AIOMetadata configuration!`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Update UI with Result Data
function updateResults(data) {
  currentAioConfig = data.aioConfig;
  currentCatalogs = data.catalogs || [];

  // Update Stats
  const total = currentCatalogs.length;
  let mdblistCount = 0;
  let traktCount = 0;
  let othersCount = 0;

  currentCatalogs.forEach(c => {
    const s = (c.source || '').toLowerCase();
    if (s === 'mdblist') mdblistCount++;
    else if (s === 'trakt') traktCount++;
    else othersCount++;
  });

  document.getElementById('statTotal').innerText = total;
  document.getElementById('statMdblist').innerText = mdblistCount;
  document.getElementById('statTrakt').innerText = traktCount;
  document.getElementById('statOthers').innerText = othersCount;
  document.getElementById('catalogCountDisplay').innerText = total;

  renderCatalogsTable(currentCatalogs);
}

// Render Catalogs Table
function renderCatalogsTable(catalogs) {
  const tbody = document.getElementById('catalogsTableBody');
  if (!catalogs || catalogs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500">No catalogs found.</td></tr>`;
    return;
  }

  const sourceBadgeColors = {
    mdblist: 'bg-purple-900/40 text-purple-300 border-purple-700/50',
    trakt: 'bg-pink-900/40 text-pink-300 border-pink-700/50',
    tmdb: 'bg-emerald-900/40 text-emerald-300 border-emerald-700/50',
    anilist: 'bg-sky-900/40 text-sky-300 border-sky-700/50',
    streaming: 'bg-amber-900/40 text-amber-300 border-amber-700/50',
    tvdb: 'bg-cyan-900/40 text-cyan-300 border-cyan-700/50',
  };

  tbody.innerHTML = catalogs.map((cat, index) => {
    const source = (cat.source || 'other').toLowerCase();
    const badgeClass = sourceBadgeColors[source] || 'bg-slate-800 text-slate-300 border-slate-700';

    return `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="px-4 py-2.5 font-medium text-slate-200">${escapeHtml(cat.name || 'Untitled')}</td>
        <td class="px-3 py-2.5">
          <span class="inline-block uppercase text-[10px] font-bold px-2 py-0.5 rounded-full border ${badgeClass}">
            ${escapeHtml(cat.source || 'N/A')}
          </span>
        </td>
        <td class="px-3 py-2.5 text-slate-400 capitalize">${escapeHtml(cat.type || 'all')}</td>
        <td class="px-3 py-2.5 font-mono text-[11px] text-slate-400">${escapeHtml(cat.id || '')}</td>
        <td class="px-3 py-2.5 text-center">
          <input type="checkbox" ${cat.enabled ? 'checked' : ''} onchange="toggleCatalogActive(${index}, this.checked)" class="w-3.5 h-3.5 accent-purple-500 rounded cursor-pointer">
        </td>
      </tr>
    `;
  }).join('');
}

function toggleCatalogActive(index, isChecked) {
  if (currentCatalogs[index]) {
    currentCatalogs[index].enabled = isChecked;
  }
  if (currentAioConfig && currentAioConfig.config && currentAioConfig.config.catalogs) {
    currentAioConfig.config.catalogs[index].enabled = isChecked;
    const enabledCount = currentCatalogs.filter(c => c.enabled).length;
    currentAioConfig.metadata.enabledCatalogs = enabledCount;
  }
}

// Filter Table Search
function filterCatalogsTable() {
  const query = document.getElementById('catalogSearch').value.toLowerCase();
  const filtered = currentCatalogs.filter(c => {
    return (c.name || '').toLowerCase().includes(query) ||
           (c.id || '').toLowerCase().includes(query) ||
           (c.source || '').toLowerCase().includes(query) ||
           (c.type || '').toLowerCase().includes(query);
  });
  renderCatalogsTable(filtered);
}

// Copy JSON to Clipboard
function copyToClipboard() {
  if (!currentAioConfig) {
    showToast('Generate configuration first', 'error');
    return;
  }
  navigator.clipboard.writeText(JSON.stringify(currentAioConfig, null, 2))
    .then(() => showToast('Copied AIOMetadata JSON to clipboard!', 'success'))
    .catch(() => showToast('Failed to copy to clipboard', 'error'));
}

// Download JSON File
function downloadJson() {
  if (!currentAioConfig) {
    showToast('Generate configuration first', 'error');
    return;
  }
  const str = JSON.stringify(currentAioConfig, null, 2);
  const blob = new Blob([str], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const dateStr = new Date().toISOString().slice(0, 10);
  a.download = `aiometadata-config-${dateStr}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('Download started!', 'success');
}

// Toast Notifications
function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toastMsg');
  const toastIcon = document.getElementById('toastIcon');

  if (!toast || !toastMsg) return;

  toastMsg.innerText = msg;
  toast.className = 'fixed bottom-6 right-6 px-4 py-3 rounded-xl shadow-2xl text-sm font-medium flex items-center space-x-2 z-50 transform transition-all duration-300 translate-y-0 opacity-100';

  if (type === 'success') {
    toast.classList.add('bg-emerald-600', 'text-white');
    toastIcon.className = 'fa-solid fa-circle-check';
  } else if (type === 'error') {
    toast.classList.add('bg-rose-600', 'text-white');
    toastIcon.className = 'fa-solid fa-triangle-exclamation';
  } else {
    toast.classList.add('bg-purple-600', 'text-white');
    toastIcon.className = 'fa-solid fa-circle-info';
  }

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-4');
  }, 3500);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}
