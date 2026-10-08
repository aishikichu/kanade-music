/**
 * Kanade 奏 — Frontend Controller
 * Fast, 100% Async REST API client (Zero COM Deadlocks)
 */

// Application State
const state = {
  currentTab: 'search',
  searchResults: [],
  queueTasks: {},
  libraryTracks: [],
  settings: {},
  isPlaying: false,
  currentTrack: null,
  pollTimer: null,
};

// Start application immediately on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

function initApp() {
  setupNavigation();
  setupDriveControls();
  setupSearch();
  setupUrls();
  setupPlaylistImporter();
  setupQueue();
  setupLibrary();
  setupSettings();
  setupAudioPlayer();

  // Load initial settings and drive info
  refreshSettingsAndDrives();

  // Start queue poller
  startQueuePoller();
}

/* ---------------- Navigation ---------------- */
function setupNavigation() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabId = tab.dataset.tab;
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  state.currentTab = tabId;

  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tabId);
  });

  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === `tab-${tabId}`);
  });

  if (tabId === 'library') {
    loadLibrary();
  } else if (tabId === 'queue') {
    loadQueue();
  } else if (tabId === 'settings') {
    refreshSettingsAndDrives();
  }
}

/* ---------------- Drive Management & Quick Switcher ---------------- */
function setupDriveControls() {
  const btnBrowse = document.getElementById('btnBrowseFolder');
  btnBrowse.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/browse-folder', { method: 'POST' });
      const data = await res.json();
      if (data && data.success) {
        showToast(`Destination set to: ${data.path}`);
        refreshSettingsAndDrives();
        if (state.currentTab === 'library') loadLibrary();
      }
    } catch (e) {
      console.error(e);
    }
  });

  const currDisplay = document.getElementById('currentDriveDisplay');
  currDisplay.addEventListener('click', async () => {
    try {
      await fetch('/api/open-folder', { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  });
}

async function refreshSettingsAndDrives() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    state.settings = data.config || {};

    const driveInfo = data.drive_info || {};
    const currentPath = data.config.download_dir || '';

    // Update top bar display
    const statsEl = document.getElementById('driveStatsText');
    if (statsEl) statsEl.textContent = `${driveInfo.drive || 'Drive'} ${currentPath}`;

    const tagEl = document.getElementById('driveFreeTag');
    if (tagEl) tagEl.textContent = `${driveInfo.free_gb || 0} GB Free`;

    // Render quick drive pill buttons (e.g. C:, D:, E:, F:)
    const listContainer = document.getElementById('quickDrivesList');
    if (listContainer) {
      listContainer.innerHTML = '';
      const drives = data.available_drives || [];
      drives.forEach(d => {
        const isCurrent = currentPath.toLowerCase().startsWith(d.letter.toLowerCase());
        const btn = document.createElement('button');
        btn.className = `quick-drive-btn ${isCurrent ? 'active' : ''}`;
        btn.innerHTML = `<span>⚡</span> <span>${d.letter}</span> <span style="opacity:0.7">(${d.free_gb > 1000 ? (d.free_gb / 1024).toFixed(1) + ' TB' : d.free_gb + ' GB'})</span>`;
        btn.title = `Switch destination drive to ${d.letter}\\HiRes Music`;
        btn.addEventListener('click', async () => {
          const resp = await fetch('/api/set-quick-drive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ letter: d.letter })
          });
          const setRes = await resp.json();
          if (setRes && setRes.success) {
            showToast(`Target storage switched to Drive ${d.letter}!`);
            refreshSettingsAndDrives();
            if (state.currentTab === 'library') loadLibrary();
          }
        });
        listContainer.appendChild(btn);
      });
    }

    // Update Settings Tab fields
    const setDirInput = document.getElementById('settingDownloadDir');
    if (setDirInput) setDirInput.value = currentPath;

    const meterTitle = document.getElementById('meterDriveTitle');
    if (meterTitle) meterTitle.textContent = `Drive [${driveInfo.drive || 'C:'}] Storage Capacity`;

    const meterVals = document.getElementById('meterDriveValues');
    if (meterVals) meterVals.textContent = `${driveInfo.free_gb || 0} GB Free / ${driveInfo.total_gb || 0} GB Total (${driveInfo.percent_used || 0}% Used)`;

    const meterFill = document.getElementById('meterFill');
    if (meterFill) {
      const pct = driveInfo.percent_used || 0;
      meterFill.style.width = `${pct}%`;
      meterFill.style.background = pct > 90 ? '#ef4444' : pct > 75 ? '#f59e0b' : 'linear-gradient(90deg, #10b981, #00f0ff)';
    }

    const meterFooter = document.getElementById('meterFooterPath');
    if (meterFooter) meterFooter.textContent = `Current Save Location: ${currentPath}`;

    // Populate dropdowns/checkboxes
    const qualitySelect = document.getElementById('settingQualityPreset');
    const quickSelect = document.getElementById('quickQualitySelect');
    if (state.settings.audio_quality_preset) {
      if (qualitySelect) qualitySelect.value = state.settings.audio_quality_preset;
      if (quickSelect) quickSelect.value = state.settings.audio_quality_preset;
    }

    const tmplSelect = document.getElementById('settingFolderTemplate');
    if (tmplSelect && state.settings.folder_template) tmplSelect.value = state.settings.folder_template;

    const resSelect = document.getElementById('settingArtworkRes');
    if (resSelect && state.settings.artwork_resolution) resSelect.value = state.settings.artwork_resolution;

    const chkEmbed = document.getElementById('settingEmbedArt');
    if (chkEmbed) chkEmbed.checked = state.settings.embed_cover_art !== false;

    const chkCover = document.getElementById('settingExternalCover');
    if (chkCover) chkCover.checked = state.settings.save_external_cover !== false;

    const compSlider = document.getElementById('settingCompression');
    if (compSlider && state.settings.flac_compression_level !== undefined) {
      compSlider.value = state.settings.flac_compression_level;
      updateCompressionBadge(state.settings.flac_compression_level);
    }
  } catch (err) {
    console.error('Error refreshing settings:', err);
  }
}

/* ---------------- Search & Discovery ---------------- */
function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  const btnSearch = document.getElementById('btnSearch');
  const btnClear = document.getElementById('btnClearSearch');
  const btnDownloadAll = document.getElementById('btnDownloadAll');

  btnSearch.addEventListener('click', () => performSearch());
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
  });

  btnClear.addEventListener('click', () => {
    searchInput.value = '';
    searchInput.focus();
  });

  btnDownloadAll.addEventListener('click', async () => {
    if (!state.searchResults.length) return;
    const count = state.searchResults.length;
    btnDownloadAll.textContent = 'Queuing...';
    btnDownloadAll.disabled = true;

    try {
      await fetch('/api/download-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tracks: state.searchResults })
      });
      showToast(`Added all ${count} tracks to FLAC download queue!`);
      btnDownloadAll.textContent = '✓ All Queued';
      loadQueue();
    } catch (e) {
      btnDownloadAll.disabled = false;
      btnDownloadAll.textContent = '⬇ Download All';
    }
  });

  const quickSelect = document.getElementById('quickQualitySelect');
  if (quickSelect) {
    quickSelect.addEventListener('change', async (e) => {
      const val = e.target.value;
      state.settings.audio_quality_preset = val;
      const modalSelect = document.getElementById('settingQualityPreset');
      if (modalSelect) modalSelect.value = val;
      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(state.settings)
        });
        const label = val === 'flac_24bit' ? '👑 24-bit Hi-Res Studio FLAC' :
                      val === 'flac_16bit' ? '🎧 16-bit Lossless CD FLAC' :
                      val === 'hifi_first' ? '🌟 Hi-Fi Lossless First' : '⚡ Native Clean M4A';
        showToast(`Download Quality set to: ${label}`);
      } catch (err) {
        console.error('Error saving quick quality preset:', err);
      }
    });
  }
}

async function performSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) return;

  const statusEl = document.getElementById('searchStatus');
  const btnSearch = document.getElementById('btnSearch');
  const btnDownloadAll = document.getElementById('btnDownloadAll');
  const container = document.getElementById('resultsContainer');

  btnSearch.disabled = true;
  btnSearch.textContent = 'Searching...';
  statusEl.textContent = `Searching studio catalog for "${query}"...`;
  statusEl.style.color = 'var(--accent-cyan)';
  btnDownloadAll.style.display = 'none';

  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon" style="animation: spin 1s infinite linear;">💿</div>
      <h3>Querying High-Res Audio Databases...</h3>
      <p>Fetching studio tags, uncompressed album artwork, and lossless audio streams.</p>
    </div>
  `;

  try {
    const filterUnwanted = document.getElementById('chkFilterUnwanted')?.checked ? '1' : '0';
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&filter_unwanted=${filterUnwanted}`);
    const results = await res.json();
    state.searchResults = results || [];

    btnSearch.disabled = false;
    btnSearch.textContent = 'Search Studio Catalog';

    if (!results || results.length === 0) {
      statusEl.textContent = `No tracks found for "${query}". Try another search term.`;
      statusEl.style.color = 'var(--accent-rose)';
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <h3>No Results Found</h3>
          <p>We could not find any matches. Check the spelling or try searching by artist name.</p>
        </div>
      `;
      return;
    }

    statusEl.textContent = `Found ${results.length} studio releases. Click ▶ Preview to audition or ⬇ Download.`;
    statusEl.style.color = 'var(--accent-emerald)';
    btnDownloadAll.style.display = 'inline-flex';
    btnDownloadAll.textContent = `⬇ Download All (${results.length} tracks)`;
    btnDownloadAll.disabled = false;

    renderResults(results);
  } catch (err) {
    btnSearch.disabled = false;
    btnSearch.textContent = 'Search Studio Catalog';
    statusEl.textContent = `Search error: ${err}`;
    statusEl.style.color = 'var(--accent-rose)';
  }
}

function renderResults(tracks) {
  const container = document.getElementById('resultsContainer');
  container.innerHTML = '';

  tracks.forEach((track) => {
    const card = document.createElement('div');
    card.className = 'track-card';

    const durMin = Math.floor(track.duration_sec / 60);
    const durSec = String(track.duration_sec % 60).padStart(2, '0');
    const durStr = track.duration_sec > 0 ? `${durMin}:${durSec}` : '';

    const thumb = track.thumbnail_url || 'https://via.placeholder.com/150/1e293b/00f0ff?text=Audio';
    const isCleanStudio = track.score_breakdown && !track.score_breakdown.is_unwanted && track.match_score >= 130;
    const penalties = track.score_breakdown?.penalties_applied || [];
    const hasPenalty = penalties.length > 0;
    const penaltyLabel = hasPenalty ? penalties[0].split(' ')[0] : '';

    card.innerHTML = `
      <img src="${thumb}" class="track-cover" alt="Cover" loading="lazy" />
      <div class="track-info">
        <div>
          <div class="track-title" title="${escapeHtml(track.title)}">
            ${escapeHtml(track.title)}
            ${isCleanStudio ? `<span class="badge-tag" style="background:rgba(16,185,129,0.18);color:#34d399;border:1px solid rgba(16,185,129,0.3);font-size:10px;margin-left:6px;">✨ Studio Original</span>` : ''}
            ${hasPenalty ? `<span class="badge-tag" style="background:rgba(239,68,68,0.18);color:#f87171;border:1px solid rgba(239,68,68,0.3);font-size:10px;margin-left:6px;">⚠️ ${escapeHtml(penaltyLabel)}</span>` : ''}
          </div>
          <div class="track-artist" title="${escapeHtml(track.artist)} • ${escapeHtml(track.album)}">${escapeHtml(track.artist)} • ${escapeHtml(track.album)}</div>
          <div class="track-meta-row">
            <span class="badge-tag" style="background:rgba(0,240,255,0.1);color:var(--accent-cyan);border:1px solid rgba(0,240,255,0.2);">Studio Master</span>
            ${track.year ? `<span class="badge-tag">${track.year}</span>` : ''}
            ${track.genre ? `<span class="badge-tag">${escapeHtml(track.genre)}</span>` : ''}
            ${durStr ? `<span class="badge-tag">${durStr}</span>` : ''}
            ${track.isrc ? `<span class="badge-tag" style="font-size:10px;opacity:0.8;">ISRC: ${escapeHtml(track.isrc)}</span>` : ''}
            ${track.match_score !== undefined ? `<span class="badge-tag" style="background:rgba(56,189,248,0.12);color:#38bdf8;font-size:10px;" title="Rank Score: ${track.match_score}">Match: ${Math.round(track.match_score)}</span>` : ''}
          </div>
        </div>
        <div class="track-actions">
          <button class="btn btn-secondary btn-sm btn-preview" title="Audition 30-sec studio preview">▶ Preview</button>
          <button class="btn btn-emerald btn-sm btn-download">⬇ Download</button>
        </div>
      </div>
    `;

    // Preview click
    const btnPreview = card.querySelector('.btn-preview');
    if (btnPreview) {
      btnPreview.addEventListener('click', () => {
        playTrackAudio(track);
      });
    }

    // Download click
    const btnDown = card.querySelector('.btn-download');
    btnDown.addEventListener('click', async () => {
      btnDown.disabled = true;
      btnDown.textContent = 'Queuing...';
      btnDown.style.background = '#475569';

      try {
        const resp = await fetch('/api/download-track', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(track)
        });
        const res = await resp.json();
        if (res && res.success) {
          state.queueTasks[res.task_id] = { button: btnDown, track };
          btnDown.textContent = '0%';
          showToast(`Added "${track.title}" to download queue!`);
          loadQueue();
        }
      } catch (e) {
        btnDown.disabled = false;
        btnDown.textContent = '⬇ Download';
      }
    });

    container.appendChild(card);
  });
}

/* ---------------- Direct URLs & Batch ---------------- */
function setupUrls() {
  const btnPaste = document.getElementById('btnPasteClipboard');
  const btnClear = document.getElementById('btnClearUrls');
  const btnQueue = document.getElementById('btnQueueUrls');
  const textarea = document.getElementById('urlsTextarea');

  btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        textarea.value = (textarea.value ? textarea.value + '\n' : '') + text;
        showToast('Pasted from clipboard!');
      }
    } catch {
      showToast('Please press Ctrl+V to paste into the box.');
    }
  });

  btnClear.addEventListener('click', () => {
    textarea.value = '';
  });

  btnQueue.addEventListener('click', async () => {
    const raw = textarea.value.trim();
    if (!raw) {
      showToast('Please enter or paste at least one URL.');
      return;
    }

    const lines = raw.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
    if (!lines.length) {
      showToast('No valid URLs found.');
      return;
    }

    btnQueue.disabled = true;
    btnQueue.textContent = 'Adding to Queue...';

    try {
      const resp = await fetch('/api/download-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls: lines })
      });
      const res = await resp.json();
      btnQueue.disabled = false;
      btnQueue.textContent = '⬇ Download';
      textarea.value = '';

      showToast(`✓ Added ${res.count} audio stream(s) to download queue!`);
      loadQueue();
      switchTab('queue');
    } catch (e) {
      btnQueue.disabled = false;
      btnQueue.textContent = '⬇ Download';
      showToast('Error adding URLs to queue.');
    }
  });
}

/* ---------------- Streaming Playlist Importer ---------------- */
function setupPlaylistImporter() {
  const urlInput = document.getElementById('playlistUrlInput');
  const btnResolve = document.getElementById('btnResolvePlaylist');
  const btnClear = document.getElementById('btnClearPlaylistInput');
  const btnPaste = document.getElementById('btnPastePlaylistClipboard');
  const previewContainer = document.getElementById('playlistPreviewContainer');
  const btnDismiss = document.getElementById('btnDismissPlaylistPreview');
  const btnQueueTracks = document.getElementById('btnQueuePlaylistTracks');

  const coverImg = document.getElementById('playlistCoverImg');
  const titleText = document.getElementById('playlistTitleText');
  const platformBadge = document.getElementById('playlistPlatformBadge');
  const creatorText = document.getElementById('playlistCreatorText');
  const trackCountBadge = document.getElementById('playlistTrackCountBadge');
  const descText = document.getElementById('playlistDescriptionText');
  const tracksList = document.getElementById('playlistTracksList');
  const statusNote = document.getElementById('playlistStatusNote');

  let currentResolvedPlaylist = null;

  if (btnClear && urlInput) {
    btnClear.addEventListener('click', () => {
      urlInput.value = '';
      if (previewContainer) previewContainer.style.display = 'none';
      currentResolvedPlaylist = null;
    });
  }

  if (btnDismiss && previewContainer) {
    btnDismiss.addEventListener('click', () => {
      previewContainer.style.display = 'none';
      currentResolvedPlaylist = null;
    });
  }

  if (btnPaste && urlInput && btnResolve) {
    btnPaste.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          showToast('Pasted playlist link from clipboard!');
          btnResolve.click();
        }
      } catch {
        showToast('Please press Ctrl+V to paste into the link input.');
      }
    });
  }

  if (urlInput && btnResolve) {
    urlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        btnResolve.click();
      }
    });
  }

  if (btnResolve && urlInput) {
    btnResolve.addEventListener('click', async () => {
      const url = urlInput.value.trim();
      if (!url) {
        showToast('Please enter a Spotify, Apple Music, or Deezer playlist link.');
        return;
      }

      btnResolve.disabled = true;
      btnResolve.textContent = 'Resolving...';

      try {
        const resp = await fetch('/api/playlist/resolve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, limit: 150 })
        });
        const data = await resp.json();
        btnResolve.disabled = false;
        btnResolve.textContent = '🔍 Preview Playlist';

        if (!data || !data.success || !data.playlist) {
          showToast(`Resolution failed: ${data.error || 'Could not parse playlist'}`);
          return;
        }

        const pl = data.playlist;
        currentResolvedPlaylist = pl;

        if (coverImg) coverImg.src = pl.cover_url || 'https://via.placeholder.com/100/1e293b/00f0ff?text=Playlist';
        if (titleText) titleText.textContent = pl.title || 'Untitled Playlist';

        let platClass = 'badge-tag';
        let platName = pl.platform.toUpperCase();
        if (pl.platform === 'spotify') { platClass += ' badge-spotify'; platName = 'Spotify'; }
        else if (pl.platform === 'apple_music') { platClass += ' badge-apple'; platName = 'Apple Music'; }
        else if (pl.platform === 'deezer') { platClass += ' badge-deezer'; platName = 'Deezer'; }
        
        if (platformBadge) {
          platformBadge.className = platClass;
          platformBadge.textContent = platName;
        }

        if (creatorText) creatorText.textContent = pl.creator ? `By ${pl.creator}` : 'Curated';
        if (trackCountBadge) trackCountBadge.textContent = `${pl.tracks.length} Tracks`;
        if (descText) descText.textContent = pl.description || '';

        if (tracksList) {
          tracksList.innerHTML = '';
          const previewLimit = Math.min(pl.tracks.length, 25);
          pl.tracks.slice(0, previewLimit).forEach((trk, idx) => {
            const row = document.createElement('div');
            row.className = 'playlist-track-item';
            const durMin = Math.floor(trk.duration_sec / 60);
            const durSec = String(trk.duration_sec % 60).padStart(2, '0');
            const durStr = trk.duration_sec > 0 ? `${durMin}:${durSec}` : '--:--';

            row.innerHTML = `
              <div class="playlist-track-left">
                <span class="playlist-track-num">${idx + 1}.</span>
                <div>
                  <div class="playlist-track-name">${escapeHtml(trk.title)}</div>
                  <div class="playlist-track-artist">${escapeHtml(trk.artist)} • ${escapeHtml(trk.album)}</div>
                </div>
              </div>
              <div class="playlist-track-right">
                <button class="btn btn-secondary btn-sm btn-prev-trk" style="font-size:11px;padding:2px 8px;margin-right:4px;" title="Audition preview">▶ Preview</button>
                ${trk.isrc ? `<span class="badge-tag" style="font-size:10px;">ISRC: ${escapeHtml(trk.isrc)}</span>` : ''}
                <span class="badge-tag badge-flac">${durStr}</span>
              </div>
            `;

            const btnPrevTrk = row.querySelector('.btn-prev-trk');
            if (btnPrevTrk) {
              btnPrevTrk.addEventListener('click', (e) => {
                e.stopPropagation();
                playTrackAudio(trk);
              });
            }

            tracksList.appendChild(row);
          });

          if (pl.tracks.length > previewLimit) {
            const moreRow = document.createElement('div');
            moreRow.style.padding = '6px 10px';
            moreRow.style.fontSize = '12px';
            moreRow.style.color = 'var(--text-muted)';
            moreRow.style.textAlign = 'center';
            moreRow.textContent = `... and ${pl.tracks.length - previewLimit} more tracks`;
            tracksList.appendChild(moreRow);
          }
        }

        if (statusNote) {
          statusNote.textContent = `Extracted ${pl.tracks.length} tracks with verified metadata. Ready to queue.`;
        }
        if (previewContainer) {
          previewContainer.style.display = 'block';
        }
        showToast(`✓ Resolved "${pl.title}" (${pl.tracks.length} tracks)`);

      } catch (err) {
        btnResolve.disabled = false;
        btnResolve.textContent = '🔍 Preview Playlist';
        showToast(`Network error resolving playlist: ${err}`);
      }
    });
  }

  if (btnQueueTracks) {
    btnQueueTracks.addEventListener('click', async () => {
      if (!currentResolvedPlaylist || !currentResolvedPlaylist.tracks) {
        showToast('No resolved playlist to queue.');
        return;
      }

      btnQueueTracks.disabled = true;
      btnQueueTracks.textContent = 'Queueing All Tracks...';

      try {
        const resp = await fetch('/api/playlist/queue', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tracks: currentResolvedPlaylist.tracks
          })
        });
        const data = await resp.json();

        btnQueueTracks.disabled = false;
        btnQueueTracks.textContent = '⬇ Download Entire Playlist';

        if (data && data.success) {
          showToast(`✓ Added ${data.count} songs from "${currentResolvedPlaylist.title}" to download queue!`);
          if (previewContainer) previewContainer.style.display = 'none';
          if (urlInput) urlInput.value = '';
          currentResolvedPlaylist = null;
          loadQueue();
          switchTab('queue');
        } else {
          showToast(`Error queueing playlist: ${data.error || 'Unknown error'}`);
        }
      } catch (e) {
        btnQueueTracks.disabled = false;
        btnQueueTracks.textContent = '⬇ Download Entire Playlist';
        showToast('Network error adding playlist to queue.');
      }
    });
  }
}

/* ---------------- Queue Manager & Poller ---------------- */
function setupQueue() {
  const btnClear = document.getElementById('btnClearFinished');
  btnClear.addEventListener('click', async () => {
    try {
      await fetch('/api/clear-queue', { method: 'POST' });
      loadQueue();
    } catch (e) {
      console.error(e);
    }
  });
}

function startQueuePoller() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(() => {
    loadQueue();
  }, 600);
}

async function loadQueue() {
  try {
    const res = await fetch('/api/queue');
    const tasks = await res.json();
    renderQueue(tasks);
    updateQueueBadge(tasks);

    // Update active card download buttons
    tasks.forEach(t => {
      const cardData = state.queueTasks[t.task_id];
      if (cardData && cardData.button) {
        if (t.status === 'completed') {
          cardData.button.textContent = '✓ Saved';
          cardData.button.style.background = 'var(--accent-emerald)';
        } else if (t.status === 'failed') {
          cardData.button.textContent = 'Failed';
          cardData.button.style.background = 'var(--accent-rose)';
          cardData.button.disabled = false;
        } else {
          cardData.button.textContent = `${Math.round(t.percent)}%`;
        }
      }
    });
  } catch (err) {
    // Quiet fail on network transient
  }
}

function renderQueue(tasks) {
  const list = document.getElementById('queueList');
  const summary = document.getElementById('queueSummaryText');
  if (!list || !summary) return;

  const active = tasks.filter(t => ['downloading', 'inspecting', 'converting'].includes(t.status)).length;
  const queued = tasks.filter(t => t.status === 'queued').length;
  const completed = tasks.filter(t => t.status === 'completed').length;
  const failed = tasks.filter(t => t.status === 'failed').length;

  summary.textContent = `${active} active • ${queued} queued • ${completed} saved • ${failed} failed`;

  if (!tasks.length) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⏳</div>
        <h3>No Active Downloads</h3>
        <p>Search for songs or paste URLs to queue up FLAC downloads.</p>
      </div>
    `;
    return;
  }

  list.innerHTML = '';
  tasks.forEach(t => {
    const item = document.createElement('div');
    item.className = 'queue-item';

    const thumb = t.artwork_url || 'https://via.placeholder.com/100/1e293b/00f0ff?text=Audio';
    const isDone = t.status === 'completed';
    const isErr = t.status === 'failed';
    const isFlac = (t.format === 'FLAC') || (t.output_file && t.output_file.toLowerCase().endsWith('.flac'));
    const fmtBadge = isFlac ?
      '<span class="badge-tag badge-lossless">🎧 True Lossless FLAC</span>' :
      '<span class="badge-tag badge-native">⚡ Native Clean M4A</span>';

    item.innerHTML = `
      <img src="${thumb}" class="queue-cover" alt="Cover" />
      <div class="queue-details">
        <div class="queue-name">${escapeHtml(t.title)} - ${escapeHtml(t.artist)}</div>
        <div class="queue-sub">
          ${isDone ? `
            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:2px;">
              <span style="color:var(--accent-emerald);font-weight:700;">✓ Saved:</span>
              ${fmtBadge}
              <span style="color:var(--text-muted);font-size:11px;" title="${escapeHtml(t.output_file)}">${escapeHtml(t.output_file ? t.output_file.split('\\').pop().split('/').pop() : '')}</span>
            </div>` :
            isErr ? `<span style="color:var(--accent-rose)">Failed: ${escapeHtml(t.error_msg)}</span>` :
            t.status === 'converting' ? 'Finalizing audio container & embedding tags...' :
            t.status === 'inspecting' ? 'Analyzing stream & matching official studio artwork...' :
            'Waiting in queue...'}
        </div>
      </div>
      <div class="queue-progress-col">
        <div class="queue-stats-row">
          <span>${Math.round(t.percent)}%</span>
          <span>${t.speed || ''}</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: ${t.percent}%; ${isDone ? 'background:var(--accent-emerald)' : ''}"></div>
        </div>
      </div>
      ${isDone && t.output_file ? `
        <button class="btn btn-secondary btn-sm" onclick="revealFile('${escapeJs(t.output_file)}')">
          📂 Reveal
        </button>
      ` : ''}
    `;

    list.appendChild(item);
  });
}

function updateQueueBadge(tasks) {
  const badge = document.getElementById('queueBadge');
  if (!badge) return;

  const active = (tasks || []).filter(t => ['queued', 'downloading', 'converting', 'inspecting'].includes(t.status)).length;
  if (active > 0) {
    badge.textContent = active;
    badge.style.display = 'inline-block';
  } else {
    badge.style.display = 'none';
  }
}

/* ---------------- Library ---------------- */
function setupLibrary() {
  const btnRefresh = document.getElementById('btnRefreshLibrary');
  const btnOpen = document.getElementById('btnOpenFolder');
  const filterInput = document.getElementById('libraryFilterInput');

  btnRefresh.addEventListener('click', () => loadLibrary());
  btnOpen.addEventListener('click', async () => {
    try {
      await fetch('/api/open-folder', { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  });

  filterInput.addEventListener('input', () => {
    filterLibraryDisplay(filterInput.value.trim().toLowerCase());
  });

  // Filter Pills (All, Lossless FLAC, Native M4A)
  const pillBtns = document.querySelectorAll('#libraryFilterPills .btn');
  pillBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      pillBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedLibraryFmt = btn.getAttribute('data-fmt') || 'all';
      filterLibraryDisplay(filterInput ? filterInput.value.trim().toLowerCase() : '');
    });
  });
}

async function loadLibrary() {
  const summary = document.getElementById('librarySummaryText');
  if (summary) summary.textContent = 'Scanning storage drive for audio tracks...';

  try {
    const res = await fetch('/api/library');
    const tracks = await res.json();
    state.libraryTracks = tracks || [];

    const flacCount = (tracks || []).filter(t => (t.format || '').toUpperCase() === 'FLAC').length;
    const m4aCount = (tracks || []).filter(t => (t.format || '').toUpperCase() === 'M4A').length;

    const elCountAll = document.getElementById('countAll');
    if (elCountAll) elCountAll.textContent = (tracks || []).length;
    const elCountFlac = document.getElementById('countFlac');
    if (elCountFlac) elCountFlac.textContent = flacCount;
    const elCountM4a = document.getElementById('countM4a');
    if (elCountM4a) elCountM4a.textContent = m4aCount;

    const totalSize = (tracks || []).reduce((acc, t) => acc + (t.size_mb || 0), 0);
    if (summary) {
      summary.textContent = `${(tracks || []).length} audio track(s) in library • ${flacCount} Lossless FLAC • ${m4aCount} Native M4A (${totalSize.toFixed(1)} MB storage used)`;
    }
    const filterInput = document.getElementById('libraryFilterInput');
    filterLibraryDisplay(filterInput ? filterInput.value.trim().toLowerCase() : '');
  } catch (err) {
    if (summary) summary.textContent = 'Error scanning library.';
  }
}

function filterLibraryDisplay(query) {
  const list = document.getElementById('libraryList');
  if (!list) return;
  list.innerHTML = '';

  const selectedFmt = (state.selectedLibraryFmt || 'all').toLowerCase();

  const filtered = state.libraryTracks.filter(t => {
    const fmt = (t.format || '').toLowerCase();
    if (selectedFmt === 'flac' && fmt !== 'flac') return false;
    if (selectedFmt === 'm4a' && fmt !== 'm4a') return false;
    if (!query) return true;
    return (
      (t.title && t.title.toLowerCase().includes(query)) ||
      (t.artist && t.artist.toLowerCase().includes(query)) ||
      (t.album && t.album.toLowerCase().includes(query))
    );
  });

  if (!filtered.length) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📂</div>
        <h3>No Tracks Found</h3>
        <p>No audio files matched your active format filter or search term.</p>
      </div>
    `;
    return;
  }

  filtered.forEach(t => {
    const item = document.createElement('div');
    item.className = 'library-item';

    const durMin = Math.floor(t.duration_sec / 60);
    const durSec = String(t.duration_sec % 60).padStart(2, '0');
    const durStr = t.duration_sec > 0 ? `${durMin}:${durSec}` : '';
    const srKhz = (t.sample_rate / 1000).toFixed(1);
    const fmt = (t.format || 'AUDIO').toUpperCase();
    const isFlac = fmt === 'FLAC';
    const isHiRes = Boolean(t.is_hires || (t.bits > 16) || (t.sample_rate > 44100));

    const fmtColor = isHiRes ? '#facc15' : isFlac ? 'var(--accent-cyan)' : 'var(--accent-emerald)';
    const tierBadgeClass = isHiRes ? 'badge-hires' : isFlac ? 'badge-lossless' : 'badge-native';
    const tierText = isHiRes ? '👑 24-bit Hi-Res Master' : isFlac ? '🎧 16-bit Lossless FLAC' : '⚡ Native Clean AAC';
    const qBadge = t.quality_badge || `${t.bits}-bit / ${srKhz} kHz`;

    item.innerHTML = `
      <div class="library-cover" style="display:flex;align-items:center;justify-content:center;background:#1e293b;color:${fmtColor};font-weight:700;font-size:11px;border:1px solid rgba(255,255,255,0.08);">
        ${fmt}
      </div>
      <div class="library-details">
        <div class="library-name">${escapeHtml(t.title)}</div>
        <div class="library-sub">${escapeHtml(t.artist)} • ${escapeHtml(t.album || 'Single')} ${t.year ? `(${t.year})` : ''}</div>
        <div class="track-meta-row">
          <span class="badge-tag ${tierBadgeClass}">${escapeHtml(tierText)}</span>
          <span class="badge-tag">${escapeHtml(qBadge)}</span>
          <span class="badge-tag">${t.size_mb} MB</span>
          ${durStr ? `<span class="badge-tag">${durStr}</span>` : ''}
        </div>
      </div>
      <button class="btn btn-emerald btn-sm btn-play-local">
        ▶ Play
      </button>
      <button class="btn btn-secondary btn-sm" onclick="showSpectrogramModal('${escapeJs(t.path)}', '${escapeJs(t.title)}')">
        📊 Spectrum
      </button>
      <button class="btn btn-secondary btn-sm" onclick="revealFile('${escapeJs(t.path)}')">
        📂 Reveal
      </button>
    `;

    const btnPlay = item.querySelector('.btn-play-local');
    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        playTrackAudio({
          path: t.path,
          title: t.title,
          artist: t.artist,
          album: t.album,
          is_hires: isHiRes,
          tier_label: tierText,
          quality_badge: qBadge,
          source: `Local ${fmt} Master`
        });
      });
    }

    list.appendChild(item);
  });
}

window.revealFile = async function(filePath) {
  try {
    await fetch('/api/reveal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: filePath })
    });
  } catch (e) {
    console.error(e);
  }
};

window.showSpectrogramModal = function(filePath, trackTitle) {
  const modal = document.getElementById('spectrogramModal');
  const titleEl = document.getElementById('spectrogramModalTitle');
  const subEl = document.getElementById('spectrogramModalSubtitle');
  const loading = document.getElementById('spectrogramLoading');
  const wrapper = document.getElementById('spectrogramImgWrapper');
  const img = document.getElementById('spectrogramImg');
  const btnClose = document.getElementById('btnCloseSpectrogramModal');

  if (!modal) return;
  titleEl.textContent = `Acoustic Spectrum: ${trackTitle || 'Track'}`;
  subEl.textContent = filePath.split('\\').pop().split('/').pop();
  loading.style.display = 'block';
  wrapper.style.display = 'none';
  img.src = '';
  modal.style.display = 'flex';

  const closeHandler = () => {
    modal.style.display = 'none';
    img.src = '';
  };
  btnClose.onclick = closeHandler;
  modal.onclick = (e) => {
    if (e.target === modal) closeHandler();
  };

  const specUrl = `/api/spectrogram?path=${encodeURIComponent(filePath)}`;
  const testImg = new Image();
  testImg.onload = () => {
    img.src = specUrl;
    loading.style.display = 'none';
    wrapper.style.display = 'block';
  };
  testImg.onerror = () => {
    loading.innerHTML = `<span style="color:var(--accent-rose)">Failed to compute audio spectrogram. Ensure audio file exists.</span>`;
  };
  testImg.src = specUrl;
};

window.playLocalTrack = function(filePath, title, artist, format) {
  playTrackAudio({
    path: filePath,
    title: title,
    artist: artist,
    source: `Local ${format || 'Audio'} Master`
  });
};

/* ---------------- Settings Tab ---------------- */
function setupSettings() {
  const btnBrowse = document.getElementById('btnSettingsBrowse');
  const btnSave = document.getElementById('btnSaveSettings');
  const compSlider = document.getElementById('settingCompression');

  btnBrowse.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/browse-folder', { method: 'POST' });
      const data = await res.json();
      if (data && data.success) {
        document.getElementById('settingDownloadDir').value = data.path;
        refreshSettingsAndDrives();
      }
    } catch (e) {
      console.error(e);
    }
  });

  compSlider.addEventListener('input', () => {
    updateCompressionBadge(compSlider.value);
  });

  btnSave.addEventListener('click', async () => {
    const qualityPresetEl = document.getElementById('settingQualityPreset');
    const selectedPreset = qualityPresetEl ? qualityPresetEl.value : 'flac_24bit';
    const newCfg = {
      audio_quality_preset: selectedPreset,
      folder_template: document.getElementById('settingFolderTemplate').value,
      artwork_resolution: document.getElementById('settingArtworkRes').value,
      embed_cover_art: document.getElementById('settingEmbedArt').checked,
      save_external_cover: document.getElementById('settingExternalCover').checked,
      flac_compression_level: parseInt(document.getElementById('settingCompression').value, 10),
    };

    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCfg)
      });
      state.settings.audio_quality_preset = selectedPreset;
      const quickSelect = document.getElementById('quickQualitySelect');
      if (quickSelect) quickSelect.value = selectedPreset;

      const toast = document.getElementById('saveToast');
      toast.style.display = 'inline';
      setTimeout(() => { toast.style.display = 'none'; }, 3000);
      showToast('Settings saved successfully!');
    } catch (e) {
      showToast('Error saving settings.');
    }
  });
}

function updateCompressionBadge(level) {
  const badge = document.getElementById('compressionBadge');
  const lvl = parseInt(level, 10);
  const text = lvl === 8 ? 'Level 8 (Max Lossless Compression)' : lvl === 0 ? 'Level 0 (Fastest Encoding)' : `Level ${lvl}`;
  badge.textContent = text;
}

/* ---------------- Audio Player Dock (Native Web Audio Engine) ---------------- */
function setupAudioPlayer() {
  const btnToggle = document.getElementById('btnPlayerToggle');
  const btnStop = document.getElementById('btnPlayerStop');
  const volSlider = document.getElementById('volSlider');
  const volIcon = document.getElementById('volIcon');

  if (!state.audio) {
    state.audio = new Audio();
  }

  const audio = state.audio;
  audio.volume = volSlider ? parseFloat(volSlider.value) / 100.0 : 0.85;

  audio.addEventListener('play', () => {
    updatePlayerState(true);
  });

  audio.addEventListener('pause', () => {
    updatePlayerState(false);
  });

  audio.addEventListener('ended', () => {
    updatePlayerState(false);
    showToast('Preview playback finished.');
  });

  audio.addEventListener('error', (e) => {
    console.error('Audio playback error:', e);
    updatePlayerState(false);
    showToast('Audio stream could not be loaded or played.');
  });

  if (btnToggle) {
    btnToggle.addEventListener('click', () => {
      if (!audio.src) {
        showToast('Please select a track to audition.');
        return;
      }
      if (audio.paused) {
        audio.play().catch(err => {
          console.error(err);
          showToast('Could not resume audio preview.');
        });
      } else {
        audio.pause();
      }
    });
  }

  if (btnStop) {
    btnStop.addEventListener('click', () => {
      audio.pause();
      audio.currentTime = 0;
      updatePlayerState(false);
    });
  }

  if (volSlider) {
    volSlider.addEventListener('input', () => {
      const vol = parseFloat(volSlider.value) / 100.0;
      audio.volume = Math.max(0, Math.min(1, vol));
      if (volIcon) {
        volIcon.textContent = vol === 0 ? '🔇' : vol < 0.4 ? '🔉' : '🔊';
      }
    });
  }

  if (volIcon) {
    volIcon.style.cursor = 'pointer';
    volIcon.title = 'Click to Mute / Unmute';
    volIcon.addEventListener('click', () => {
      audio.muted = !audio.muted;
      volIcon.textContent = audio.muted ? '🔇' : (audio.volume < 0.4 ? '🔉' : '🔊');
      showToast(audio.muted ? 'Audio Muted' : 'Audio Unmuted');
    });
  }
}

async function playTrackAudio(track) {
  if (!track) return;
  const audio = state.audio || (state.audio = new Audio());

  state.currentTrack = track;
  const playerTitle = document.getElementById('playerTitle');
  const playerSubtitle = document.getElementById('playerSubtitle');
  const artContainer = document.getElementById('playerArt');

  if (playerTitle) playerTitle.textContent = track.title || 'Audio Stream';
  if (playerSubtitle) playerSubtitle.textContent = `${track.artist || ''} • ${track.album || ''} [${track.source || 'Studio Preview'}]`;

  const qualityBadge = document.getElementById('playerQualityBadge');
  if (qualityBadge) {
    if (track.path) {
      const isFlac = track.path.toLowerCase().endsWith('.flac');
      const isHiRes = Boolean(track.is_hires || (track.bits > 16) || (track.sample_rate > 44100));
      qualityBadge.style.display = 'inline-block';
      qualityBadge.className = `badge-tag ${isHiRes ? 'badge-hires' : isFlac ? 'badge-lossless' : 'badge-native'}`;
      qualityBadge.textContent = track.tier_label || (isHiRes ? '👑 24-bit Hi-Res' : isFlac ? '🎧 16-bit Lossless' : '⚡ Native M4A');
    } else {
      qualityBadge.style.display = 'inline-block';
      qualityBadge.className = 'badge-tag';
      qualityBadge.textContent = '30s Preview';
    }
  }

  const thumb = track.thumbnail_url || track.artwork_url;
  if (artContainer) {
    if (thumb) {
      artContainer.innerHTML = `<img src="${thumb}" alt="Art" />`;
    } else {
      artContainer.innerHTML = `<div class="player-art-placeholder">🎵</div>`;
    }
  }

  // Determine stream source URL
  let streamUrl = track.preview_url;

  // Local FLAC file playback via streaming endpoint
  if (track.path) {
    streamUrl = `/api/stream?path=${encodeURIComponent(track.path)}`;
  }

  // If no preview URL exists (e.g. from Spotify or Apple Music playlists), lookup on-demand 30s preview
  if (!streamUrl) {
    showToast(`Looking up 30-sec preview for "${track.title}"...`);
    try {
      const lookupResp = await fetch('/api/preview-lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          artist: track.artist,
          title: track.title
        })
      });
      const lookupData = await lookupResp.json();
      if (lookupData && lookupData.success && lookupData.preview_url) {
        streamUrl = lookupData.preview_url;
        track.preview_url = streamUrl;
      }
    } catch (err) {
      console.warn('Preview lookup error:', err);
    }
  }

  if (!streamUrl) {
    showToast(`No 30-sec audio preview available for "${track.title}".`);
    updatePlayerState(false);
    return;
  }

  try {
    audio.pause();
    audio.src = streamUrl;
    const volSlider = document.getElementById('volSlider');
    if (volSlider) {
      audio.volume = parseFloat(volSlider.value) / 100.0;
    }
    await audio.play();
    updatePlayerState(true);
    showToast(`▶ Now Auditioning: ${track.title}`);
  } catch (err) {
    console.error('Audio play error:', err);
    updatePlayerState(false);
    showToast(`Playback error: ${err.message || 'Stream blocked'}`);
  }
}

function updatePlayerState(isPlaying) {
  state.isPlaying = isPlaying;
  const btnToggle = document.getElementById('btnPlayerToggle');
  const visualizer = document.getElementById('waveformVisualizer');

  if (btnToggle) btnToggle.textContent = isPlaying ? '⏸' : '▶';
  if (visualizer) {
    if (isPlaying) {
      visualizer.classList.add('playing');
    } else {
      visualizer.classList.remove('playing');
    }
  }
}

/* ---------------- Toast Notification ---------------- */
function showToast(message) {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

/* ---------------- Helpers ---------------- */
function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[m]));
}

function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}
