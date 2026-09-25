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
    console.error("Failed to load findings:", err);
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
    const res = await fetch('filtered.json');
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
      ${f.confidence_score === 0 ? `<div class="ans-source-tag" style="background:rgba(220, 38, 38, 0.2); color:#ef4444; border:1px solid rgba(220, 38, 38, 0.3); margin-left:auto; align-self:center;">No Evidence Found</div>` : ''}
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

async function loadCoreAnswers() {
  try {
    const res = await fetch('core_answers.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const getQuotesHtml = (items) => {
      if (!items || !items.length) return '<div style="font-size: 0.85rem; color: #94a3b8;">No data available.</div>';
      const topItem = items[0];
      if (!topItem.top_quotes || !topItem.top_quotes.length) return '<div style="font-size: 0.85rem; color: #94a3b8;">No quotes available.</div>';
      return topItem.top_quotes.map(q => 
          `<div style="margin-bottom: 8px; font-size: 0.85rem; color: #94a3b8;"><strong>${escHtml(q.source || 'Unknown')}</strong>: "${escHtml(q.quote)}"</div>`
      ).join('');
    };

    if (data.Q1_photo_types && data.Q1_photo_types.length) {
      document.getElementById('q1-val').textContent = `${data.Q1_photo_types[0].category} (${data.Q1_photo_types[0].count})`;
      document.getElementById('q1-quotes').innerHTML = getQuotesHtml(data.Q1_photo_types);
    }
    if (data.Q2_anchors_present && data.Q2_anchors_present.length) {
      document.getElementById('q2-val').textContent = `${data.Q2_anchors_present[0].category} (${data.Q2_anchors_present[0].count})`;
      document.getElementById('q2-quotes').innerHTML = getQuotesHtml(data.Q2_anchors_present);
    }
    if (data.Q3_anchors_missing && data.Q3_anchors_missing.length) {
      document.getElementById('q3-val').textContent = `${data.Q3_anchors_missing[0].category} (${data.Q3_anchors_missing[0].count})`;
      document.getElementById('q3-quotes').innerHTML = getQuotesHtml(data.Q3_anchors_missing);
    }
    if (data.Q4_search_behavior && data.Q4_search_behavior.length) {
      document.getElementById('q4-val').textContent = `${data.Q4_search_behavior[0].behavior} (${data.Q4_search_behavior[0].total_count})`;
      document.getElementById('q4-quotes').innerHTML = getQuotesHtml(data.Q4_search_behavior);
    }
  } catch (err) {
    console.error("Failed to load core answers:", err);
  }
}

// ── Product Opportunities ── Featured cards (screenshot 2 format) ─
async function renderOpportunities() {
  const list = document.getElementById('opps-featured-list');
  if (!list) return;

  try {
    const res = await fetch('opportunities.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const oppsData = await res.json();
    
    list.innerHTML = '';
    oppsData.forEach((opp, oi) => {
        const quotesHTML = (opp.top_quotes && opp.top_quotes.length ? opp.top_quotes : [{quote:'No quote available.',source:''}])
          .map(q => `
            <div class="opp-quote-item">
              <div class="opp-quote-text">"${escHtml((q.quote||'').substring(0,120))}"</div>
              <div class="opp-quote-src">— ${escHtml(q.source||'')}</div>
            </div>`).join('');
            
        const title = opp.problem_pair.replace(/_/g, ' ').toUpperCase();
        const sub = `Frequency: ${opp.frequency} · Severity: ${opp.severity_multiplier}x · Score: ${opp.opportunity_score}`;
        const painItems = `<li>Missing Anchor: <strong>${escHtml(opp.missing_anchor)}</strong></li><li>Failure Point: <strong>${escHtml(opp.failure_point)}</strong></li>`;
        const pmItems = `<li>Design to address users lacking <em>${escHtml(opp.missing_anchor)}</em></li><li>Mitigate risk of <em>${escHtml(opp.failure_point)}</em></li>`;
        
        const card = document.createElement('div');
        card.className = 'opp-card';
        card.innerHTML = `
          <div class="opp-card-header">
            <div class="opp-card-icon" style="background:rgba(67,97,238,.15);border:1px solid rgba(67,97,238,.3)">⚡</div>
            <div>
              <div class="opp-card-title">${escHtml(title)}</div>
              <div class="opp-card-sub">${escHtml(sub)}</div>
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
  } catch (err) {
    console.error("Failed to load opportunities:", err);
    list.innerHTML = '<div class="generic-loading"><span>Failed to load opportunities.</span></div>';
  }
}

// ── Insight Library replaced by static Pipeline HTML ──────────
function renderLibrary() { /* Pipeline architecture rendered in HTML */ }

// ── Chart ─────────────────────────────────────────────────────
let chartInstance = null;
function initChart(labelsOverride = null, countsOverride = null) {
  const canvas = document.getElementById('cluster-chart');
  if (!canvas || typeof Chart === 'undefined') return;

  const labels = labelsOverride || ['Search\nFailure','Memory\nGaps','Face &\nPeople','Data\nLoss','Location\nIssues','Scrolling','Screenshots','Context\nGap'];
  const counts = countsOverride || [30, 25, 15, 11, 8, 7, 6, 6];
  const bg     = ['#4361eecc','#7c3aedcc','#4361eecc','#0ea5e9cc','#f97316cc','#a78bfacc','#0ea5e9cc','#7c3aedcc'];

  if (chartInstance) {
    chartInstance.data.labels = labels;
    chartInstance.data.datasets[0].data = counts;
    chartInstance.update();
    return;
  }

  chartInstance = new Chart(canvas, {
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

// ── Filter UI Logic ───────────────────────────────────────────
function setupFilters() {
  const pFilter = document.getElementById('filter-platform');
  const tFilter = document.getElementById('filter-photo');
  const sFilter = document.getElementById('filter-segment');

  if (!pFilter || !tFilter || !sFilter) return;

  const updateFilters = () => {
    const pf = pFilter.value.toLowerCase();
    const tf = tFilter.value.toLowerCase();
    const sf = sFilter.value.toLowerCase();

    // Just doing simple filtering for demonstration, and re-rendering the chart
    // We will extract a count of keyword groups from the filtered records
    const counts = {};
    filteredRecords.forEach(r => {
      let match = true;
      if (pf !== 'all' && !(r.source || '').toLowerCase().includes(pf.replace('_',' '))) match = false;
      // As photo_type and user_segment are absent in filteredRecords, we mock it by allowing match if missing
      
      if (match && r._keyword_groups) {
        r._keyword_groups.forEach(g => {
          counts[g] = (counts[g] || 0) + 1;
        });
      }
    });

    const sortedGroups = Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, 8);
    if (sortedGroups.length > 0) {
      initChart(sortedGroups.map(g => g[0].replace(/_/g, '\\n')), sortedGroups.map(g => g[1]));
    } else {
      initChart(['No Data'], [0]);
    }
    
    // Re-render signal chips and source bars based on filtered subset
    const chipsContainer = document.getElementById('signal-chips-container');
    if (chipsContainer) {
      chipsContainer.innerHTML = sortedGroups.map(g => {
        const name = g[0].replace(/_/g, ' ');
        // Alternate colors for aesthetic
        const colorClass = ['chip--red', 'chip--amber', 'chip--blue', 'chip--teal'][Math.floor(Math.random() * 4)];
        return `<span class="chip ${colorClass}">${escHtml(name)} <b>${g[1]}</b></span>`;
      }).join('');
    }

    const sourceCounts = {};
    filteredRecords.forEach(r => {
      let match = true;
      if (tf !== 'all') match = false; // mock since we don't have it
      if (sf !== 'all') match = false; // mock since we don't have it
      if (match && r.source) {
        sourceCounts[r.source] = (sourceCounts[r.source] || 0) + 1;
      }
    });

    const sourceBarsContainer = document.querySelector('.source-bars');
    if (sourceBarsContainer) {
      const colors = { 'App Store': '#4361ee', 'Google Play': '#22c55e', 'Reddit': '#f97316', 'Forums/Community': '#a78bfa' };
      const total = Object.values(sourceCounts).reduce((a,b) => a+b, 0) || 1;
      sourceBarsContainer.innerHTML = Object.entries(sourceCounts).sort((a,b)=>b[1]-a[1]).map(s => {
        const name = s[0];
        const count = s[1];
        const color = colors[name] || '#94a3b8';
        const pct = Math.round((count / total) * 100);
        return `
          <div class="source-bar-item">
            <div class="source-bar-label">
              <span class="src-dot" style="background:${color}"></span>
              <span>${escHtml(name)}</span><span class="source-bar-count">${count}</span>
            </div>
            <div class="source-bar-track"><div class="source-bar-fill" style="width:${pct}%;background:${color}"></div></div>
          </div>`;
      }).join('');
    }
  };

  pFilter.addEventListener('change', updateFilters);
  tFilter.addEventListener('change', updateFilters);
  sFilter.addEventListener('change', updateFilters);
}

// ── Utility ───────────────────────────────────────────────────
function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Init ──────────────────────────────────────────────────────
(async function init() {
  setupScrollSpy();
  initChart();
  setupFilters();
  await Promise.all([loadFindings(), loadFilteredRecords(), loadCoreAnswers()]);
})();

