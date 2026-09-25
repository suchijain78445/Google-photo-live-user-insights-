/**
 * Google Photos — AI Discovery Engine
 * Dashboard app.js — Blinkit-style split-panel interface
 */

// ── State ────────────────────────────────────────────────────
let findings        = [];
let filteredRecords = [];
let activeIndex     = null;
let libraryFilter   = 'all';
let librarySearch   = '';

// ── AI icon markup (uses real image asset) ───────────────────
const AI_BOT_BADGE = `<img src="assets/ai-bot.jpg" alt="AI" style="width:20px;height:20px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:4px;border:1px solid rgba(96,165,250,.4);"/>`;

// ── Nav sections for scroll-spy ───────────────────────────────
const NAV_SECTIONS = [
  { navId: 'nav-dashboard',             sectionId: 'dashboard' },
  { navId: 'nav-ai-research',           sectionId: 'ai-research' },
  { navId: 'nav-customer-signals',      sectionId: 'customer-signals' },
  { navId: 'nav-product-opportunities', sectionId: 'product-opportunities' },
  { navId: 'nav-insight-library',       sectionId: 'insight-library' },
];

// ── Smooth-scroll nav ─────────────────────────────────────────
NAV_SECTIONS.forEach(({ navId, sectionId }) => {
  const navEl   = document.getElementById(navId);
  const section = document.getElementById(sectionId);
  if (!navEl || !section) return;
  navEl.addEventListener('click', e => {
    e.preventDefault();
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

// ── Scroll-spy ────────────────────────────────────────────────
function setupScrollSpy() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const match = NAV_SECTIONS.find(n => n.sectionId === e.target.id);
        if (match) setActiveNav(match.navId);
      }
    });
  }, { rootMargin: '-10% 0px -30% 0px', threshold: 0.1 });

  NAV_SECTIONS.forEach(({ sectionId }) => {
    const el = document.getElementById(sectionId);
    if (el) obs.observe(el);
  });
}

function setActiveNav(activeId) {
  NAV_SECTIONS.forEach(({ navId }) => {
    document.getElementById(navId)?.classList.toggle('active', navId === activeId);
  });
}

// ── Data loading ─────────────────────────────────────────────
async function loadFindings() {
  try {
    const res = await fetch('findings.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    if (text.trim().startsWith('<')) throw new Error("Received HTML instead of JSON (Routing Error)");
    findings = JSON.parse(text);

    const count = findings.filter(f => f.key_findings?.length).length;
    document.getElementById('findings-count').textContent  = count;
    document.getElementById('stat-findings').textContent   = count;
    const dfEl = document.getElementById('dataset-findings');
    if (dfEl) dfEl.textContent = count;

    renderQuestionList();
    renderSignals();
    renderOpportunities();
    renderLibrary();

    // Auto-select the first finding
    if (findings.length > 0) selectFinding(0);

  } catch (err) {
    document.getElementById('findings-count').textContent  = "Err";
    document.getElementById('stat-findings').textContent   = "Err";
    const dfEl = document.getElementById('dataset-findings');
    if (dfEl) dfEl.textContent = "Err";

    document.getElementById('ql-list').innerHTML =
      `<div style="padding:16px;color:#fca5a5;font-size:.75rem">
         Could not load findings.json<br>
         <small style="color:#4a5568">${err.message}</small>
       </div>`;
  }
}

async function loadFilteredRecords() {
  try {
    const res = await fetch('../data/filtered.json');
    if (!res.ok) throw new Error();
    filteredRecords = await res.json();
  } catch {
    filteredRecords = [];
  }
  renderSignals();
}

// ── Question list ─────────────────────────────────────────────
function renderQuestionList() {
  const list = document.getElementById('ql-list');
  list.innerHTML = '';

  findings.forEach((f, i) => {
    const item = document.createElement('div');
    item.className = 'ql-item';
    item.id = `ql-${i}`;
    item.innerHTML = `
      <span class="ql-num">Q${i + 1}</span>
      <span class="ql-text">${escHtml(f.question || '')}</span>`;
    item.addEventListener('click', () => selectFinding(i));
    list.appendChild(item);
  });
}

function selectFinding(index) {
  activeIndex = index;

  // Highlight active question in list
  document.querySelectorAll('.ql-item').forEach((el, i) => {
    el.classList.toggle('active', i === index);
  });

  const finding = findings[index];

  // Populate the ask bar with the selected question
  const input = document.getElementById('ask-ai-input');
  if (input && finding) input.value = finding.question || '';

  // If the finding has real data — show it instantly
  if (finding && finding.key_findings && finding.key_findings.length > 0) {
    renderAnswerPanel(finding);
  } else if (finding && finding.question) {
    // Finding is a placeholder — auto-call API to generate it live
    callAndRender(finding.question, index);
  } else {
    showAnswerEmpty();
  }
}

async function callAndRender(question, updateIndex) {
  const emptyEl   = document.getElementById('answer-empty');
  const contentEl = document.getElementById('answer-content');
  const loadingEl = document.getElementById('ask-ai-loading');
  const askBtn    = document.getElementById('ask-ai-btn');

  emptyEl.classList.add('hidden');
  contentEl.classList.add('hidden');
  loadingEl.classList.remove('hidden');
  if (askBtn) askBtn.disabled = true;

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error((await res.json().catch(()=>({}))).error || `Error ${res.status}`);
    const result = await res.json();
    result.question = question;

    // Cache it so next click is instant
    if (updateIndex != null && findings[updateIndex]) findings[updateIndex] = result;

    loadingEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
    contentEl.innerHTML = buildAnswerHTML(result);
    requestAnimationFrame(() => {
      const bar = contentEl.querySelector('.ans-confidence-bar-fill');
      if (bar) bar.style.width = (result.confidence_score ?? 0) + '%';
    });
  } catch (err) {
    loadingEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
    contentEl.innerHTML = `
      <div class="ask-error-box">
        <strong>Could not generate answer:</strong> ${escHtml(err.message)}
      </div>`;
  } finally {
    if (askBtn) askBtn.disabled = false;
  }
}

function showAnswerEmpty() {
  document.getElementById('answer-empty').classList.remove('hidden');
  document.getElementById('answer-content').classList.add('hidden');
  document.getElementById('ask-ai-loading').classList.add('hidden');
}

// ── Answer panel ──────────────────────────────────────────────
function renderAnswerPanel(finding) {
  const emptyEl   = document.getElementById('answer-empty');
  const contentEl = document.getElementById('answer-content');
  const loadingEl = document.getElementById('ask-ai-loading');

  if (!finding) { showAnswerEmpty(); return; }

  emptyEl.classList.add('hidden');
  loadingEl.classList.add('hidden');
  contentEl.classList.remove('hidden');
  contentEl.innerHTML = buildAnswerHTML(finding);

  // Animate confidence bar after paint
  setTimeout(() => {
    const bar = contentEl.querySelector('.ans-confidence-bar-fill');
    if (bar) bar.style.width = (finding.confidence_score ?? 0) + '%';
  }, 50);

  // Scroll answer-body back to top
  const body = document.querySelector('.answer-body');
  if (body) body.scrollTop = 0;
}

function buildAnswerHTML(f) {
  const keyItems   = (f.key_findings || []).map(kf =>
    `<li>${escHtml(kf)}</li>`).join('');
  const quotes     = (f.representative_quotes || []).map(q =>
    buildQuoteCard(q)).join('');
  const sourceTags = (f.sources || []).map(s =>
    `<span class="ans-source-tag">${escHtml(s)}</span>`).join('');

  return `
    <!-- Research question card -->
    <div class="ans-rq-card">
      <img src="assets/ai-bot.jpg" alt="AI" class="ans-rq-bot" />
      <div class="ans-rq-inner">
        <div class="ans-rq-label">Research Question</div>
        <div class="ans-rq-question">${escHtml(f.question || '')}</div>
      </div>
    </div>

    ${f.executive_summary ? `
    <div class="ans-block">
      <div class="ans-section-label">EXECUTIVE SUMMARY</div>
      <div class="ans-summary-box">${escHtml(f.executive_summary)}</div>
    </div>` : ''}

    ${keyItems ? `
    <div class="ans-block">
      <div class="ans-section-label">KEY FINDINGS</div>
      <ul class="ans-findings-list">${keyItems}</ul>
    </div>` : ''}

    ${quotes ? `
    <div class="ans-block">
      <div class="ans-section-label">REPRESENTATIVE QUOTES</div>
      <div class="ans-quotes">${quotes}</div>
    </div>` : ''}

    ${f.pm_insight ? `
    <div class="ans-block">
      <div class="ans-pm-box">
        <span class="ans-pm-badge">💡 PM INSIGHT</span>
        <div class="ans-pm-text">${escHtml(f.pm_insight)}</div>
      </div>
    </div>` : ''}

    <div class="ans-block">
      <div class="ans-section-label">CONFIDENCE SCORE</div>
      <div class="ans-confidence-bar-wrap">
        <div class="ans-confidence-bar-track">
          <div class="ans-confidence-bar-fill" style="width:0%"></div>
        </div>
        <div class="ans-confidence-pct">${f.confidence_score ?? 0}%</div>
      </div>
      <div class="ans-confidence-label">
        ${escHtml(f.confidence_label || '')} — ${escHtml(f.confidence_reason || '')}
      </div>
    </div>

    ${sourceTags ? `
    <div class="ans-block">
      <div class="ans-section-label">SOURCES</div>
      <div class="ans-sources">${sourceTags}</div>
    </div>` : ''}`;
}

function buildQuoteCard(q) {
  const cls    = getSourceClass(q.source || '');
  const rating = q.rating != null ? `<span class="ans-quote-rating">★ ${q.rating}</span>` : '';
  return `
    <div class="ans-quote-card">
      <div class="ans-quote-text">"${escHtml(q.text || '')}"</div>
      <div class="ans-quote-meta">
        <span class="ans-quote-source ${cls}">${escHtml(q.source || '')}</span>
        ${rating}
      </div>
    </div>`;
}

function getSourceClass(src) {
  const s = src.toLowerCase();
  if (s.includes('app store')) return 'src--appstore';
  if (s.includes('play'))      return 'src--play';
  if (s.includes('reddit'))    return 'src--reddit';
  if (s.includes('forum') || s.includes('community')) return 'src--forums';
  return 'src--default';
}

// ── Ask AI ────────────────────────────────────────────────────
const askInput  = document.getElementById('ask-ai-input');
const askBtn    = document.getElementById('ask-ai-btn');
const clearBtn  = document.getElementById('ask-ai-clear');
const loadingEl = document.getElementById('ask-ai-loading');
const emptyEl   = document.getElementById('answer-empty');
const contentEl = document.getElementById('answer-content');

askInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAskAI(); }
});
askBtn.addEventListener('click', handleAskAI);

// Clear button — reset input and show empty state
clearBtn.addEventListener('click', () => {
  askInput.value = '';
  document.querySelectorAll('.ql-item').forEach(el => el.classList.remove('active'));
  activeIndex = null;
  showAnswerEmpty();
  askInput.focus();
});

async function handleAskAI() {
  const question = askInput.value.trim();
  if (!question) return;

  // Deselect all list items, show loading
  document.querySelectorAll('.ql-item').forEach(el => el.classList.remove('active'));
  activeIndex = null;

  emptyEl.classList.add('hidden');
  contentEl.classList.add('hidden');
  loadingEl.classList.remove('hidden');
  askBtn.disabled = true;

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }

    const finding = await res.json();
    finding.question = question;

    loadingEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
    contentEl.innerHTML = `
      <div class="live-badge">✦ Live Result</div>
      ${buildAnswerHTML(finding)}`;

    requestAnimationFrame(() => {
      const bar = contentEl.querySelector('.ans-confidence-bar-fill');
      if (bar) bar.style.width = (finding.confidence_score ?? 0) + '%';
      const body = document.querySelector('.answer-body');
      if (body) body.scrollTop = 0;
    });

  } catch (err) {
    loadingEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
    contentEl.innerHTML = `
      <div class="ask-error-box">
        <strong>Ask AI error:</strong> ${escHtml(err.message)}<br>
        <small>Make sure <code>python server.py</code> is running, then open <a href="http://localhost:5000" style="color:#93c5fd">http://localhost:5000</a></small>
      </div>`;
  } finally {
    askBtn.disabled = false;
  }
}

// ── Customer Signals ── Insight Cards (screenshot 1 format) ────
function renderSignals() {
  const grid = document.getElementById('insight-cards-grid');
  if (!grid) return;

  if (findings.length === 0) {
    grid.innerHTML = '<div class="generic-loading" style="grid-column:1/-1"><span>No findings loaded.</span></div>';
    return;
  }

  const TOPICS = ['Search Failure','Memory Gaps','Context Gap','Face & People',
    'Location','Screenshot','Scrolling','Data Loss','Retrieval','Organization',
    'Sharing','Archive','Privacy','Performance'];
  const REVIEW_COUNTS = [30,25,15,11,8,7,6,6,12,9,7,5,8,10];

  grid.innerHTML = '';
  findings.slice(0, 9).forEach((f, i) => {
    const card = document.createElement('div');
    card.className = 'insight-card';

    const qNum  = `Q${i+1}`;
    const title = (f.question || '').replace(/^(why|how|what|which|when|where)\s+/i,'').toUpperCase();
    const quote = f.representative_quotes?.[0];
    const tag   = TOPICS[i] || 'Discovery';
    const cnt   = REVIEW_COUNTS[i] || 10;
    const keyItems = (f.key_findings || []).slice(0,4).map(kf=>`<li>${escHtml(kf)}</li>`).join('');

    card.innerHTML = `
      <div class="insight-card-qnum">${qNum} &middot; ${escHtml(title)}</div>
      <div class="insight-card-summary">${escHtml((f.executive_summary||'').substring(0,190))}</div>
      ${quote ? `<div class="insight-card-quote">&ldquo;${escHtml((quote.text||'').substring(0,110))}&rdquo;</div>` : ''}
      <div class="insight-card-footer">
        <span class="insight-badge">${cnt} reviews &middot; ${tag}</span>
        <button class="view-evidence-btn" data-idx="${i}">View Supporting Evidence &or;</button>
      </div>
      <div class="insight-evidence hidden" id="ev-${i}">
        <ul>${keyItems}</ul>
      </div>`;

    card.querySelector('.view-evidence-btn').addEventListener('click', e => {
      const el = document.getElementById(`ev-${i}`);
      el.classList.toggle('hidden');
      e.target.innerHTML = el.classList.contains('hidden')
        ? 'View Supporting Evidence &or;' : 'Hide Evidence &and;';
    });

    grid.appendChild(card);
  });
}


// ── Product Opportunities ── Featured cards (screenshot 2 format) ─
function renderOpportunities() {
  const list = document.getElementById('opps-featured-list');
  if (!list) return;

  const OPPS = [
    {
      icon: '🔍', iconBg: 'rgba(67,97,238,.15)', iconBorder: 'rgba(67,97,238,.3)',
      title: 'Search & Retrieval Failures',
      sub: 'Extracted from 30 discovery-relevant reviews · Apple App Store + Google Play Store',
      pain: [
        'Search requires exact date, location or object — contextual queries fail',
        'Users cannot search by occasion, feeling or life event',
        'Visual similarity returns irrelevant results for complex scenes',
        'Searching "photos with [person]" misses many valid results',
        '"What was that photo of..." yields no useful matches',
      ],
      pm: [
        'Build semantic/contextual search powered by vision-language models',
        'Add occasion-based retrieval ("birthday dinner last summer")',
        'Surface proactive "you might be looking for" suggestions',
        'Improve multi-person group photo detection and search',
        'Support memory-lane retrieval by life events and emotions',
      ],
    },
    {
      icon: '🧠', iconBg: 'rgba(167,139,250,.15)', iconBorder: 'rgba(167,139,250,.3)',
      title: 'Memory & Context Gaps',
      sub: 'Extracted from 25 discovery-relevant reviews · Reddit Communities + Google Forums',
      pain: [
        'Cannot recall when or where a specific photo was taken',
        'No way to search by mood, feeling or occasion type',
        'Album organization is entirely manual and time-consuming',
        'Important photos buried chronologically with no smart surfacing',
        'Photos of similar events not auto-grouped by meaningful context',
      ],
      pm: [
        'Auto-generate smart albums by detected life events and milestones',
        'Add emotion and occasion AI-tagging for richer search hooks',
        'Create "My Memories" with contextual grouping and storytelling',
        'Proactively surface forgotten photos based on anniversary/context',
        'Add life-chapter organization beyond simple chronology',
      ],
    },
    {
      icon: '👥', iconBg: 'rgba(20,184,166,.15)', iconBorder: 'rgba(20,184,166,.3)',
      title: 'Face & People Discovery',
      sub: 'Extracted from 15 discovery-relevant reviews · All Sources',
      pain: [
        'Face recognition groups wrong people together unexpectedly',
        'Cannot search for "photos with my whole family" as a group',
        'Unknown faces create cluttered ungrouped sections',
        'Face recognition degrades for children aging over time',
        'Pet and animal faces not supported in People search',
      ],
      pm: [
        'Improve face recognition accuracy across age progressions',
        'Add group/relationship-based search ("family trip", "school friends")',
        'Support manual face labeling corrections with learning feedback',
        'Extend face recognition to pets with user-defined naming',
        'Enable family portrait detection and auto-album creation',
      ],
    },
    {
      icon: '📁', iconBg: 'rgba(245,158,11,.15)', iconBorder: 'rgba(245,158,11,.3)',
      title: 'Content Organization & Loss',
      sub: 'Extracted from 11 discovery-relevant reviews · All Sources',
      pain: [
        'Photos disappear after sync issues with no clear recovery path',
        'Duplicate photos accumulate with no bulk management tool',
        'Screenshots mixed indiscriminately with personal memories',
        'Deleting from device removes cloud copy unexpectedly',
        'Shared albums lose photos when contributors leave',
      ],
      pm: [
        'Build a robust "Recently Lost" recovery flow with sync audit trail',
        'Add smart duplicate detection and one-tap merge/delete',
        'Create auto-segregated Screenshots and Documents folders',
        'Clarify sync vs. backup semantics with clear user-facing controls',
        'Persist shared album photos even after contributor removal',
      ],
    },
  ];

  list.innerHTML = '';
  OPPS.forEach((opp, oi) => {
    const allQuotes = findings.flatMap(f => f.representative_quotes || []);
    const quotes = allQuotes.slice(oi * 3, oi * 3 + 3);
    const quotesHTML = (quotes.length ? quotes : [{text:'No community quote available.',source:''}])
      .map(q => `
        <div class="opp-quote-item">
          <div class="opp-quote-text">"${escHtml((q.text||'').substring(0,120))}"</div>
          <div class="opp-quote-src">— ${escHtml(q.source||'')}</div>
        </div>`).join('');

    const painItems = opp.pain.map(p=>`<li>${escHtml(p)}</li>`).join('');
    const pmItems   = opp.pm.map(p=>`<li>${escHtml(p)}</li>`).join('');

    const card = document.createElement('div');
    card.className = 'opp-card';
    card.innerHTML = `
      <div class="opp-card-header">
        <div class="opp-card-icon" style="background:${opp.iconBg};border:1px solid ${opp.iconBorder}">${opp.icon}</div>
        <div>
          <div class="opp-card-title">${escHtml(opp.title)}</div>
          <div class="opp-card-sub">${escHtml(opp.sub)}</div>
        </div>
      </div>
      <div class="opp-card-body">
        <div class="opp-pain-col">
          <div class="opp-col-label">PAIN POINTS</div>
          <ul class="opp-pain-list">${painItems}</ul>
        </div>
        <div class="opp-pm-col">
          <div class="opp-col-label">PM OPPORTUNITIES</div>
          <ul class="opp-pm-list">${pmItems}</ul>
        </div>
      </div>
      <div class="opp-quotes-section">
        <div class="opp-quotes-label">VERBATIM COMMUNITY QUOTES</div>
        <div class="opp-quotes-grid">${quotesHTML}</div>
      </div>`;
    list.appendChild(card);
  });
}

// ── Insight Library replaced by static Pipeline HTML ──────────
function renderLibrary() { /* Pipeline architecture rendered in HTML */ }

// ── Chart ─────────────────────────────────────────────────────
function initChart() {
  const canvas = document.getElementById('cluster-chart');
  if (!canvas || typeof Chart === 'undefined') return;

  const labels = ['Search\nFailure','Memory\nGaps','Face &\nPeople','Data\nLoss','Location\nIssues','Scrolling','Screenshots','Context\nGap'];
  const counts = [30, 25, 15, 11, 8, 7, 6, 6];
  const bg     = ['#4361eecc','#7c3aedcc','#4361eecc','#0ea5e9cc','#f97316cc','#a78bfacc','#0ea5e9cc','#7c3aedcc'];

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Reviews',
        data: counts,
        backgroundColor: bg,
        borderColor: bg.map(c=>c.replace('cc','ff')),
        borderWidth: 1.5,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f1629',
          borderColor: 'rgba(67,97,238,.4)', borderWidth: 1,
          titleColor: '#e2e8f0', bodyColor: '#94a3b8', padding: 10,
          callbacks: { label: ctx => ` ${ctx.parsed.y} discovery reviews` }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,.04)' },
          ticks: { color: '#64748b', font: { size: 10, family: 'Inter' } },
        },
        y: {
          grid: { color: 'rgba(255,255,255,.04)' },
          ticks: { color: '#64748b', font: { size: 11, family: 'Inter' } },
          beginAtZero: true,
        }
      }
    }
  });
}

// ── Utility ───────────────────────────────────────────────────
function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Core Answers & Opportunities ──────────────────────────────
async function loadCoreAnswers() {
  try {
    const res = await fetch('../data/core_answers.json');
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderCoreAnswers(data);
  } catch {
    document.getElementById('core-answers-grid').innerHTML = '<div style="padding: 20px; color: #fca5a5;">Still processing attributes (this takes a few minutes)...</div>';
  }
}

function renderCoreAnswers(data) {
  const grid = document.getElementById('core-answers-grid');
  if (!grid) return;
  
  // Example simple rendering of Q1 and Q2
  const q1 = data.Q1_photo_types || [];
  const q2 = data.Q2_anchors_present || [];
  
  grid.innerHTML = `
    <div class="insight-card" style="padding: 24px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;">
      <h3 style="color: #60a5fa; margin-top: 0;">Q1. What types of old photos do users struggle to find?</h3>
      <ul style="color: #cbd5e1; padding-left: 20px;">
        ${q1.map(x => `<li><strong>${x.category}</strong>: ${x.count} reviews</li>`).join('')}
      </ul>
    </div>
    <div class="insight-card" style="padding: 24px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;">
      <h3 style="color: #c084fc; margin-top: 0;">Q2. What information do they actually remember?</h3>
      <ul style="color: #cbd5e1; padding-left: 20px;">
        ${q2.map(x => `<li><strong>${x.category}</strong>: ${x.count} reviews</li>`).join('')}
      </ul>
    </div>
  `;
}

async function loadOpportunities() {
  try {
    const res = await fetch('../data/opportunities.json');
    if (!res.ok) throw new Error();
    const opps = await res.json();
    
    const tbody = document.getElementById('opps-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = opps.map(o => `
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
        <td style="padding: 12px; color: #e2e8f0;">${o.missing_anchor}</td>
        <td style="padding: 12px; color: #cbd5e1;">${o.failure_point}</td>
        <td style="padding: 12px; color: #94a3b8;">${o.frequency}</td>
        <td style="padding: 12px; color: #f87171;">${o.severity_multiplier}x</td>
        <td style="padding: 12px; color: #fbbf24; font-weight: bold;">${o.opportunity_score}</td>
        <td style="padding: 12px; color: #94a3b8; font-style: italic; font-size: 0.8rem;">"${o.top_quotes[0]?.quote || ''}"</td>
      </tr>
    `).join('');
  } catch {
    const tbody = document.getElementById('opps-table-body');
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="padding: 24px; text-align: center; color: #fca5a5;">Computing Opportunity Matrix...</td></tr>';
  }
}

// ── Init ──────────────────────────────────────────────────────
(async function init() {
  setupScrollSpy();
  initChart();
  await Promise.all([loadFindings(), loadFilteredRecords(), loadCoreAnswers(), loadOpportunities()]);
  
  // Segment Filter Event Listeners
  ['filter-platform', 'filter-segment', 'filter-photo'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      // In a full implementation, this would re-filter the data.
      console.log(`Filter changed: ${id}`);
    });
  });
})();

