/* ============================================
 * SECTION: Core Logic
 * PURPOSE: Logic render 3D diagram, 3 levels of zoom, and language toggle
 * ============================================ */

let currentLang = 'vi';
let activeModalStepId = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
  // Check local storage for language
  const savedLang = localStorage.getItem('app_lang');
  if (savedLang) {
    currentLang = savedLang;
    document.querySelector(`[data-lang="${savedLang}"]`).classList.add('active');
    if(savedLang === 'ko') document.querySelector('[data-lang="vi"]').classList.remove('active');
  }
  
  initLanguageToggle();
  renderDiagram();
  updateStaticTexts();
  
  // Close modal events
  document.getElementById('closeModal').addEventListener('click', closeModal);
  document.getElementById('detailModal').addEventListener('click', (e) => {
    if(e.target.id === 'detailModal') closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if(e.key === 'Escape' && activeModalStepId) closeModal();
  });
  
  // Window resize -> update connections
  window.addEventListener('resize', renderConnections);
});

/* ============================================
 * RENDER DIAGRAM (LEVEL 1 ZOOM)
 * ============================================ */
function renderDiagram() {
  const container = document.getElementById('diagramContainer');
  container.innerHTML = '';
  
  PIPELINE_DATA.forEach((module, index) => {
    // Render Node
    const node = createModuleNode(module, index);
    container.appendChild(node);
    
    // Render Connection Arrow (except last module)
    if (index < PIPELINE_DATA.length - 1) {
      const conn = createConnection(module);
      container.appendChild(conn);
    }
  });
  
  // Need to wait for DOM to be ready to draw SVG lines properly (though with vertical layout, simple CSS might suffice)
  // For vertical layout, connection lines are handled via CSS/HTML structure
}

function createModuleNode(module, index) {
  const el = document.createElement('div');
  el.className = `module-card theme-${module.theme}`;
  el.id = `module-${module.id}`;
  
  // Header
  const header = `
    <div class="m-header">
      <div class="m-badge">Module ${module.id}</div>
      <div class="m-title">${module.title.name}</div>
      <button class="btn-run"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> <span data-i18n="btnRun">${I18N[currentLang].btnRun}</span></button>
    </div>
  `;
  
  // Body (Inputs -> Arrow -> Outputs)
  let inputsHtml = module.inputs.map(i => `<div class="tag-input">${i.text}</div>`).join('');
  let outputsHtml = module.outputs.map(o => `<div class="tag-output">${o.text}</div>`).join('');
  
  const body = `
    <div class="m-body">
      <div class="m-col m-input">
        <div class="m-col-title" data-i18n="lblInput">${I18N[currentLang].lblInput}</div>
        ${inputsHtml}
        <button class="btn-field" data-i18n="btnField">${I18N[currentLang].btnField}</button>
      </div>
      <div class="m-arrow">→</div>
      <div class="m-col m-output">
        <div class="m-col-title" data-i18n="lblOutput">${I18N[currentLang].lblOutput}</div>
        ${outputsHtml}
        <button class="btn-field" data-i18n="btnField">${I18N[currentLang].btnField}</button>
      </div>
    </div>
  `;
  
  // Flowchart (Only for Module 2)
  let flowchartHtml = '';
  if (module.isLoop) {
    flowchartHtml = renderMiniFlowchart();
  }
  
  // Footer / Why Do This (Visible on Hover - ZOOM LEVEL 2)
  const footer = `
    <div class="m-footer">
      <div class="m-why-title"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg> <span data-i18n="lblWhyDoThis">${I18N[currentLang].lblWhyDoThis}</span></div>
      <div class="m-why-text id-why-${module.id}">${module.whyText[currentLang]}</div>
    </div>
  `;
  
  // Click hints
  const hints = `
    <div class="m-hint m-hint-hover" data-i18n="tooltipHover">${I18N[currentLang].tooltipHover}</div>
    <div class="m-hint m-hint-click" data-i18n="tooltipClick">${I18N[currentLang].tooltipClick}</div>
  `;
  
  el.innerHTML = header + body + flowchartHtml + footer + hints;
  
  // Interactions
  el.addEventListener('mouseenter', () => handleHover(module.id, true));
  el.addEventListener('mouseleave', () => handleHover(module.id, false));
  el.addEventListener('click', () => openDetailModal(module.id));
  
  return el;
}

function createConnection(module) {
  const el = document.createElement('div');
  el.className = 'connection-wrapper';
  
  const labelText = module.connectionLabel ? module.connectionLabel[currentLang] : '';
  const labelHtml = labelText ? `<div class="connection-label id-conn-${module.id}">${labelText}</div>` : '';
  
  el.innerHTML = `
    <div class="connection-line">
      <div class="particle"></div>
    </div>
    ${labelHtml}
    <div class="connection-arrow">↓</div>
  `;
  
  return el;
}

function renderMiniFlowchart() {
  const t = I18N[currentLang];
  
  return `
    <div class="mini-flowchart">
      <div class="flow-header">
        <span class="loop-text id-flowLoop">${t.flowLoop}</span>
      </div>
      
      <!-- Round 2.1 -->
      <div class="flow-row">
        <span class="f-num">2.1</span>
        <div class="f-box f-search">Search 2.1<br><small>100 URLs</small></div>
        <div class="f-arr">→</div>
        <div class="f-box f-scoring">Scoring<br><small class="id-flowScoring">${t.flowLegendScoring}</small></div>
        <div class="f-arr">→</div>
        <div class="f-diamond">≥10 URLs<br>>35 pts?</div>
        <div class="f-arr f-arr-yes">→</div>
        <div class="f-box f-success">✓ 10 URLs →</div>
      </div>
      
      <!-- No arrow -->
      <div class="flow-no-arrow id-flowNo">NO</div>
      
      <!-- Round 2.2 -->
      <div class="flow-row">
        <span class="f-num">2.2</span>
        <div class="f-box f-search">Search 2.2<br><small>100 URLs</small></div>
        <div class="f-arr">→</div>
        <div class="f-box f-dedup">Dedup<br><small>vs 2.1 hits</small></div>
        <div class="f-arr">→</div>
        <div class="f-box f-scoring">Scoring<br><small class="id-flowScoring">${t.flowLegendScoring}</small></div>
        <div class="f-arr">→</div>
        <div class="f-diamond">≥10 total<br>>35 pts?</div>
        <div class="f-arr f-arr-yes">→</div>
        <div class="f-box f-success">✓ 10 URLs →</div>
      </div>
      
      <!-- No arrow -->
      <div class="flow-no-arrow id-flowNo">NO</div>
      
      <!-- Round 2.3 -->
      <div class="flow-row">
        <span class="f-num">2.3</span>
        <div class="f-box f-search">Search 2.3<br><small>100 URLs</small></div>
        <div class="f-arr">→</div>
        <div class="f-box f-dedup">Dedup<br><small>vs prev.</small></div>
        <div class="f-arr">→</div>
        <div class="f-box f-scoring">Scoring<br><small class="id-flowScoring">${t.flowLegendScoring}</small></div>
        <div class="f-arr">→</div>
        <div class="f-arr-line"></div>
        <div class="f-arr f-arr-yes">→</div>
        <div class="f-box f-success">→ <span class="id-flowBest">${t.flowBestAvailable}</span></div>
      </div>
      
      <div class="flow-legend">
        <span class="l-item"><span class="l-dot l-search"></span> Search</span>
        <span class="l-item"><span class="l-dot l-dedup"></span> Dedup</span>
        <span class="l-item"><span class="l-dot l-scoring"></span> Scoring</span>
      </div>
    </div>
  `;
}

/* ============================================
 * INTERACTIONS (ZOOM LEVEL 2 & 3)
 * ============================================ */
function handleHover(moduleId, isHovering) {
  const container = document.getElementById('diagramContainer');
  if (isHovering) {
    container.classList.add('is-hovering');
    document.getElementById(`module-${moduleId}`).classList.add('hovered');
  } else {
    container.classList.remove('is-hovering');
    document.getElementById(`module-${moduleId}`).classList.remove('hovered');
  }
}

function openDetailModal(moduleId) {
  activeModalStepId = moduleId;
  const module = PIPELINE_DATA.find(m => m.id === moduleId);
  if (!module) return;
  
  const modal = document.getElementById('detailModal');
  const content = document.getElementById('modalContent');
  const t = I18N[currentLang];
  
  // Build Modal Content
  let glossaryHtml = '';
  if (module.details.glossary && module.details.glossary.length > 0) {
    glossaryHtml = module.details.glossary.map(g => `
      <div class="glossary-item">
        <strong>${g.term}</strong>
        <p>${g[currentLang]}</p>
      </div>
    `).join('');
  }
  
  content.innerHTML = `
    <div class="modal-header theme-${module.theme}">
      <div class="m-badge">Module ${module.id}</div>
      <h2>${module.title.name}</h2>
    </div>
    
    <div class="modal-body">
      
      <div class="detail-section">
        <h3 class="section-title"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg> ${t.lblWhyDoThis}</h3>
        <p class="why-text-large">${module.whyText[currentLang]}</p>
      </div>
      
      <div class="detail-section">
        <h3 class="section-title"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg> ${t.modalTabs.example}</h3>
        <div class="example-box">
          ${module.details.example[currentLang]}
        </div>
      </div>
      
      ${glossaryHtml ? `
        <div class="detail-section">
          <h3 class="section-title"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg> ${t.modalTabs.glossary}</h3>
          <div class="glossary-grid">
            ${glossaryHtml}
          </div>
        </div>
      ` : ''}
      
    </div>
  `;
  
  modal.classList.add('show');
}

function closeModal() {
  activeModalStepId = null;
  document.getElementById('detailModal').classList.remove('show');
}

/* ============================================
 * I18N LOGIC
 * ============================================ */
function initLanguageToggle() {
  const btns = document.querySelectorAll('.lang-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      btns.forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const lang = e.target.dataset.lang;
      
      if (lang !== currentLang) {
        currentLang = lang;
        localStorage.setItem('app_lang', lang);
        updateStaticTexts();
        updateDynamicTexts();
      }
    });
  });
}

function updateStaticTexts() {
  const t = I18N[currentLang];
  
  // Update elements with data-i18n attribute
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (t[key]) el.innerHTML = t[key];
  });
  
  // Special classes for flowchart
  document.querySelectorAll('.id-flowLoop').forEach(el => el.innerHTML = t.flowLoop);
  document.querySelectorAll('.id-flowNo').forEach(el => el.innerHTML = t.flowNo);
  document.querySelectorAll('.id-flowScoring').forEach(el => el.innerHTML = t.flowLegendScoring);
  document.querySelectorAll('.id-flowBest').forEach(el => el.innerHTML = t.flowBestAvailable);
}

function updateDynamicTexts() {
  // Update module specific texts that are already rendered
  PIPELINE_DATA.forEach(module => {
    // Why text
    const whyEl = document.querySelector(`.id-why-${module.id}`);
    if (whyEl) whyEl.innerHTML = module.whyText[currentLang];
    
    // Connection label
    const connEl = document.querySelector(`.id-conn-${module.id}`);
    if (connEl && module.connectionLabel) {
      connEl.innerHTML = module.connectionLabel[currentLang];
    }
  });
  
  // If modal is open, re-render it
  if (activeModalStepId) {
    openDetailModal(activeModalStepId);
  }
}

// Dummy renderConnections for window resize (not strictly needed for CSS vertical layout, but good practice)
function renderConnections() {
  // Logic would go here if using SVG paths between absolute positioned nodes
}
