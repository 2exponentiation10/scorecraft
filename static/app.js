const jobsListEl = document.getElementById('jobs-list');
const jobsEmptyEl = document.getElementById('jobs-empty');
const resultCardEl = document.getElementById('result-card');
const resultTitleEl = document.getElementById('result-title');
const resultStatusEl = document.getElementById('result-status');
const progressFillEl = document.getElementById('progress-fill');
const progressLabelEl = document.getElementById('progress-label');
const resultSummaryEl = document.getElementById('result-summary');
const downloadLinksEl = document.getElementById('download-links');
const chordListEl = document.getElementById('chord-list');
const scoreViewerEl = document.getElementById('score-viewer');
const formFeedbackEl = document.getElementById('form-feedback');
const refreshJobsButton = document.getElementById('refresh-jobs');
const jobForm = document.getElementById('job-form');

let activeJobId = null;
let pollHandle = null;
let osmd = null;

function apiUrl(path) {
  return new URL(path, window.location.href).toString();
}

function setFeedback(message, level = 'info') {
  formFeedbackEl.textContent = message || '';
  formFeedbackEl.className = `feedback ${level}`;
}

function prettyStatus(status) {
  return ({ queued: '대기 중', running: '처리 중', succeeded: '완료', failed: '실패' })[status] || status;
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ko-KR');
}

function renderJobs(jobs) {
  jobsListEl.innerHTML = '';
  jobsEmptyEl.style.display = jobs.length ? 'none' : 'block';
  jobs.forEach((job) => {
    const item = document.createElement('article');
    item.className = `job-item ${job.id === activeJobId ? 'active' : ''}`;
    item.innerHTML = `
      <div class="job-item-head">
        <div>
          <h3>${job.title || '새 작업'}</h3>
          <div class="job-meta">${formatDate(job.createdAt)}</div>
        </div>
        <span class="status-pill ${job.status}">${prettyStatus(job.status)}</span>
      </div>
      <p class="job-meta">${job.progressLabel || ''}</p>
    `;
    item.addEventListener('click', () => loadJob(job.id));
    jobsListEl.appendChild(item);
  });
}

function renderSummary(summary = {}) {
  const entries = [
    ['추정 노트 수', summary.noteCount ?? '-'],
    ['추정 마디 수', summary.estimatedMeasures ?? '-'],
    ['파트 수', summary.partCount ?? '-'],
    ['코드 수', summary.chordCount ?? '-'],
  ];
  resultSummaryEl.innerHTML = entries.map(([label, value]) => `
    <div class="summary-tile">
      <strong>${label}</strong>
      <span>${value}</span>
    </div>
  `).join('');
}

function renderDownloads(downloads = {}) {
  const links = [
    ['MusicXML 다운로드', downloads.musicxml],
    ['MIDI 다운로드', downloads.midi],
    ['코드 JSON 다운로드', downloads.chords],
  ].filter(([, href]) => href);
  downloadLinksEl.innerHTML = links.map(([label, href]) => `<a class="download-link" href="${href}">${label}</a>`).join('');
}

function renderChords(chords = []) {
  if (!chords.length) {
    chordListEl.innerHTML = '<p class="empty-state">아직 코드가 추출되지 않았습니다.</p>';
    return;
  }
  chordListEl.innerHTML = chords.map((item) => `
    <div class="chord-item">
      <div>
        <strong>${item.symbol}</strong>
        <div class="job-meta">마디 ${item.measure}</div>
      </div>
      <span class="job-meta">${(item.pitches || []).join(', ')}</span>
    </div>
  `).join('');
}

async function renderScore(musicxmlUrl) {
  if (!musicxmlUrl) {
    scoreViewerEl.innerHTML = '<p class="empty-state">악보 파일이 아직 준비되지 않았습니다.</p>';
    return;
  }
  try {
    const response = await fetch(musicxmlUrl);
    const xml = await response.text();
    scoreViewerEl.innerHTML = '';
    osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(scoreViewerEl, { drawingParameters: 'compacttight' });
    await osmd.load(xml);
    await osmd.render();
  } catch (error) {
    scoreViewerEl.innerHTML = `<p class="empty-state">악보 렌더링에 실패했습니다: ${error.message}</p>`;
  }
}

async function loadJob(jobId) {
  activeJobId = jobId;
  const response = await fetch(apiUrl(`./api/jobs/${jobId}`));
  const job = await response.json();
  renderJob(job);
  await loadJobs();
  if (job.status === 'queued' || job.status === 'running') {
    startPolling(job.id);
  } else {
    stopPolling();
  }
}

function renderJob(job) {
  resultCardEl.classList.remove('hidden');
  resultTitleEl.textContent = job.title || '악보 결과';
  resultStatusEl.textContent = prettyStatus(job.status);
  resultStatusEl.className = `status-pill ${job.status}`;
  progressFillEl.style.width = `${Math.round((job.progress || 0) * 100)}%`;
  progressLabelEl.textContent = job.error ? `${job.progressLabel || '실패'} · ${job.error}` : (job.progressLabel || '대기 중');
  renderSummary(job.summary);
  renderDownloads(job.downloads);
  renderChords(job.chords);
  renderScore(job.downloads.musicxml);
}

async function loadJobs() {
  const response = await fetch(apiUrl('./api/jobs'));
  const payload = await response.json();
  renderJobs(payload.jobs || []);
  if (!activeJobId && payload.jobs?.length) {
    await loadJob(payload.jobs[0].id);
  }
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
}

function startPolling(jobId) {
  stopPolling();
  pollHandle = setInterval(async () => {
    try {
      const response = await fetch(apiUrl(`./api/jobs/${jobId}`));
      const job = await response.json();
      if (job.id === activeJobId) {
        renderJob(job);
        await loadJobs();
      }
      if (job.status !== 'queued' && job.status !== 'running') {
        stopPolling();
      }
    } catch (error) {
      console.error(error);
      stopPolling();
    }
  }, 2500);
}

jobForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  setFeedback('작업을 생성하고 있습니다.', 'info');
  const formData = new FormData(jobForm);
  const hasYoutube = (formData.get('youtube_url') || '').toString().trim();
  const file = formData.get('audio_file');
  if (!hasYoutube && (!file || !file.name)) {
    setFeedback('유튜브 링크 또는 오디오 파일 중 하나를 입력해 주세요.', 'error');
    return;
  }
  try {
    const response = await fetch(apiUrl('./api/jobs'), { method: 'POST', body: formData });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || '작업 생성에 실패했습니다.');
    }
    setFeedback('작업이 시작되었습니다. 보통 30초~2분 정도 걸립니다.', 'success');
    jobForm.reset();
    activeJobId = payload.id;
    renderJob(payload);
    await loadJobs();
    startPolling(payload.id);
  } catch (error) {
    setFeedback(error.message, 'error');
  }
});

refreshJobsButton.addEventListener('click', () => loadJobs());
loadJobs();
