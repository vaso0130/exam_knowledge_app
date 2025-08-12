// AI & LSP Enhanced Markdown Editor Integration
// Lightweight skeleton per AGENTS.md – Monaco + (future) LSP + AI gateway

(function(){
  // Dynamic gateway base resolution:
  // Priority: explicit window.AI_GATEWAY_BASE -> <meta name="ai-gateway-base"> -> window.AI_GATEWAY_PORT -> default (null)
  let AI_GATEWAY_BASE = window.AI_GATEWAY_BASE || null;
  if(!AI_GATEWAY_BASE){
    const meta = document.querySelector('meta[name="ai-gateway-base"]');
    if(meta && meta.content.trim()){ AI_GATEWAY_BASE = meta.content.trim(); }
  }
  if(!AI_GATEWAY_BASE){
    const port = window.AI_GATEWAY_PORT || null; // e.g. set in template
    if(port){ AI_GATEWAY_BASE = location.protocol + '//' + location.hostname + ':' + port; }
  }
  // If still null, we will skip gateway probe and directly fallback to legacy Flask endpoints.
  window.AI_GATEWAY_BASE = AI_GATEWAY_BASE;

  let monacoEditor = null;
  let lspSocket = null;
  let lspEnabled = true;
  let lspReady = false; // didOpen sent
  let pendingChangeId = 0;
  let pendingChangeBuffer = null; // latest text before lspReady
  let opened = false;
  let useGateway = !!AI_GATEWAY_BASE; // only attempt if base provided
  const GATEWAY_TOKEN = window.AI_GATEWAY_TOKEN || null;
  let lspRequestId = 10;
  const pendingLsp = new Map();
  let lspInitialized = false; // initialize response received
  let didOpenSent = false; // didOpen actually sent
  // Ghost text state
  let ghostEnabled = false;
  let ghostDecorations = [];
  let ghostText = '';
  let ghostFullText = '';
  let ghostStyleEl = null;
  let ghostSchedule = null;
  let ghostIdInc = 1;
  let inlineCmdGuard = false;
  let ghostMode = 'supplement'; // legacy default for passive ghost; UI selector removed
  let ghostReqSeq = 0;
  // Ghost perf helpers
  let ghostCtl = null; // AbortController for in-flight preview
  const ghostCache = new Map(); // key -> { text, ts }
  const ghostCacheOrder = [];
  const GHOST_CACHE_MAX = 30;
  let ghostLastKey = '';
  let ghostLastAt = 0;
  let ghostLoadingDecos = [];

  // ---------------- Ghost Text helpers (inside closure) ----------------
  function scheduleGhost(){
    if(ghostSchedule) clearTimeout(ghostSchedule);
    // shorter debounce to feel responsive, with aggressive cancel+cache
    ghostSchedule = setTimeout(updateGhost, 350);
  }

  async function updateGhost(){
    if(!ghostEnabled || !window.monacoEditor) { clearGhost(); return; }
    const model = window.monacoEditor.getModel();
    if(!model) { clearGhost(); return; }
    const full = model.getValue();
    if(!full || !full.trim()) { clearGhost(); return; }
    // Build source snippet based on mode
    let source = '';
    const pos = window.monacoEditor.getPosition();
  if(ghostMode === 'supplement' || ghostMode === 'abbr-explain' || ghostMode === 'heading-opt' || ghostMode === 'qa'){
      const startLine = Math.max(1, pos.lineNumber - 10);
      const lines = [];
      for(let ln=startLine; ln<=pos.lineNumber; ln++){ lines.push(model.getLineContent(ln)); }
      source = lines.join('\n');
    } else if(ghostMode === 'format-note'){
      // Heavy mode: send a window around caret to reduce latency
      const start = Math.max(1, pos.lineNumber - 40);
      const end = Math.min(model.getLineCount(), pos.lineNumber + 20);
      const lines = [];
      for(let ln=start; ln<=end; ln++){ lines.push(model.getLineContent(ln)); }
      source = lines.join('\n');
    }
    // Build cache key and reuse if available
    const key = ghostMode + '|' + simpleHash(source.slice(0,800) + '§' + (document.getElementById('title')?.value||''));
    if(ghostCache.has(key)){
      const cached = ghostCache.get(key);
      ghostFullText = String(cached.text||'').trim();
      const previewCached = ghostFullText.replace(/\s+/g, ' ').trim().slice(0, 120);
      if(previewCached){
        ghostText = previewCached;
        applyGhostAtCursor(previewCached);
        ghostLastKey = key; ghostLastAt = Date.now();
        return;
      }
    }
    // Rate-limit identical key within short window
    if(key === ghostLastKey && (Date.now() - ghostLastAt) < 1200){ return; }
    ghostLastKey = key; ghostLastAt = Date.now();
    setGhostLoading(true);
    const previewData = await requestGhostSuggestion(ghostMode, source, full);
    setGhostLoading(false);
    if(!previewData || !previewData.text){ clearGhost(); return; }
    ghostFullText = String(previewData.text).trim();
    const preview = ghostFullText.replace(/\s+/g, ' ').trim().slice(0, 120);
    if(!preview){ clearGhost(); return; }
    ghostText = preview;
    // Save to cache (LRU)
    try{
      ghostCache.set(key, { text: ghostFullText, ts: Date.now() });
      ghostCacheOrder.push(key);
      if(ghostCacheOrder.length > GHOST_CACHE_MAX){
        const drop = ghostCacheOrder.shift();
        if(drop && drop !== key) ghostCache.delete(drop);
      }
    }catch(_e){}
    applyGhostAtCursor(preview);
  }

  function applyGhostAtCursor(text){
    if(!window.monacoEditor || !text) return;
    const ed = window.monacoEditor;
    const pos = ed.getPosition();
    // Build a unique css class with content
    const cls = 'ghost-after-' + (ghostIdInc++);
    const css = `.${cls} { color: rgba(0,0,0,.35); }
.${cls}::after { content: "${cssEscape(text)}"; white-space: pre; opacity:.45; }`;
    if(ghostStyleEl){ try { ghostStyleEl.remove(); } catch(_e){} }
    ghostStyleEl = document.createElement('style');
    ghostStyleEl.type = 'text/css';
    ghostStyleEl.appendChild(document.createTextNode(css));
    document.head.appendChild(ghostStyleEl);
    // Apply decoration at cursor (zero-width range)
    ghostDecorations = ed.deltaDecorations(ghostDecorations, [{
      range: new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column),
      options: { afterContentClassName: cls }
    }]);
  }

  function acceptGhost(){
  if(!window.monacoEditor || !(ghostFullText || ghostText)) return;
    const ed = window.monacoEditor;
    const pos = ed.getPosition();
  const insert = (ghostFullText || ghostText);
  ed.executeEdits('ghost-accept', [{ range: new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column), text: insert, forceMoveMarkers: true }]);
    clearGhost();
  }

  function clearGhost(){
    if(window.monacoEditor && ghostDecorations.length){
      try { window.monacoEditor.deltaDecorations(ghostDecorations, []); } catch(_e){}
    }
    ghostDecorations = [];
  ghostText = '';
  ghostFullText = '';
    if(ghostStyleEl){ try { ghostStyleEl.remove(); } catch(_e){} }
    ghostStyleEl = null;
  setGhostLoading(false);
  }

  function cssEscape(s){
    return (s||'').replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\A ').replace(/\r/g,'');
  }

  function log(...args){
    // eslint-disable-next-line no-console
    console.debug('[AI-EDITOR]', ...args);
  }

  async function requestGhostSuggestion(mode, snippet, fullText){
    const seq = ++ghostReqSeq;
    try{
      const headers = { 'Content-Type': 'application/json' };
      if(GATEWAY_TOKEN && useGateway){ headers['x-ai-gateway-token'] = GATEWAY_TOKEN; }
      const enhance = buildGhostPrompt(mode, snippet, fullText);
      const body = JSON.stringify({
        enhancement_request: enhance.request,
        current_content: enhance.content,
        title: document.getElementById('title')?.value || '',
        context: { source: 'ghost', ghost_mode: mode, use_simple_model: true, model_hint: 'gemini-2.0-flash-lite', preview: true, max_chars: 160 }
      });
      const url = useGateway ? (AI_GATEWAY_BASE + '/ai/enhance') : '/notes/detect-text';
      // Cancel previous in-flight preview
      try { if(ghostCtl){ ghostCtl.abort(); } } catch(_e){}
      ghostCtl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      const resp = await fetch(url,
        useGateway
          ? { method:'POST', headers, body, signal: ghostCtl ? ghostCtl.signal : undefined }
          : { method:'POST', headers:{ 'Content-Type':'application/json' }, body: JSON.stringify({ action:'generate_enhancement', enhancement_request: enhance.request, current_content: enhance.content, title: document.getElementById('title')?.value || '', context:{ source:'ghost', ghost_mode: mode, use_simple_model:true, model_hint:'gemini-2.0-flash-lite', preview:true, max_chars:160 } }), signal: ghostCtl ? ghostCtl.signal : undefined }
      );
      const data = await resp.json();
      // drop stale responses
      if(seq !== ghostReqSeq) return null;
      const text = data.generated_content || data.enhanced_content || '';
      return { text };
    }catch(e){ log('ghost fetch failed', e); return null; }
  }

  function buildGhostPrompt(mode, snippet, fullText){
    switch(mode){
      case 'supplement':
        return {
          request: '根據以下上下文延續撰寫 1 段補充，使用繁體中文，風格與現有內容一致；直接輸出可插入的 Markdown。請勿重複前文、勿加前言，回應最長 120 字：',
          content: (snippet || fullText).slice(0, 1200)
        };
      case 'qa':
        return {
          request: '從以下內容萃取 5–8 組問答對，使用繁體中文，格式為每組以「Q: …\nA: …」呈現；聚焦考點，避免贅述，不要回覆一般段落或解說文字：',
          content: (snippet || fullText).slice(0, 1600)
        };
      case 'heading-opt':
        return {
          request: '標題層級優化：僅輸出需要新增/修正的標題行與必要前後文，勿重寫全文；回應不超過 5 行：',
          content: (fullText || '').slice(0, 1600)
        };
      case 'abbr-explain':
        return {
          request: '縮寫詞解釋：只列出文中已出現的 AI/IT 縮寫，每行「縮寫（中文全稱）：一句中文解釋」；最多 6 行：',
          content: (snippet || fullText).slice(0, 1200)
        };
      case 'format-note':
        return {
          request: '格式化片段：將以下片段以清晰的 Markdown 標題與列表輕量整理，修正明顯的編號與標點，保持原意；輸出不超過 8 行：',
          content: (snippet || fullText).slice(0, 1600)
        };
      default:
        return { request: '延續撰寫', content: snippet || fullText };
    }
  }

  function setGhostLoading(on){
    if(!window.monacoEditor){ return; }
    try{
      if(!on){
        if(ghostLoadingDecos.length){
          try { window.monacoEditor.deltaDecorations(ghostLoadingDecos, []); } catch(_e){}
          ghostLoadingDecos = [];
        }
        return;
      }
      const ed = window.monacoEditor;
      const pos = ed.getPosition();
      // subtle animated dots (CSS animation kept minimal)
      const cls = 'ghost-loading-' + (ghostIdInc++);
      const css = `.${cls} { color: rgba(0,0,0,.25); }
.${cls}::after { content: '…'; animation: ghostPulse 1s infinite; opacity:.45; } 
@keyframes ghostPulse { 0%{opacity:.2} 50%{opacity:.6} 100%{opacity:.2} }`;
      const st = document.createElement('style'); st.type='text/css'; st.appendChild(document.createTextNode(css)); document.head.appendChild(st);
      ghostLoadingDecos = ed.deltaDecorations(ghostLoadingDecos, [{
        range: new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column),
        options: { afterContentClassName: cls }
      }]);
    }catch(_e){}
  }

  function simpleHash(str){
    // tiny DJB2
    let h = 5381, i = str.length;
    while(i){ h = (h * 33) ^ str.charCodeAt(--i); }
    return (h >>> 0).toString(16);
  }

  async function probeGateway(){
    if(!AI_GATEWAY_BASE){
      useGateway = false;
      window.useAIGateway = false;
      return;
    }
    try {
      const ctl = new AbortController();
      setTimeout(()=>ctl.abort(), 1500);
  const r = await fetch(AI_GATEWAY_BASE + '/health', { signal: ctl.signal, headers: GATEWAY_TOKEN? { 'x-ai-gateway-token': GATEWAY_TOKEN } : {} });
      if(!r.ok) throw new Error('bad');
      useGateway = true;
  window.useAIGateway = true;
    } catch(e){
      useGateway = false;
  window.useAIGateway = false;
      log('Gateway not reachable, fallback to Flask routes');
    }
  }

  function initMonaco(){
    const textarea = document.getElementById('content');
    if(!textarea) return;
    // Create container
    let container = document.getElementById('editor-root');
    if(!container){
      container = document.createElement('div');
      container.id = 'editor-root';
      container.style.width = '100%';
      container.style.height = '600px';
      container.style.border = '1px solid #ccc';
      textarea.parentNode.insertBefore(container, textarea);
    }
    textarea.style.display = 'none';

    function detectMonacoLocale(){
      // Prefer explicit override, then html lang, then navigator
      const explicit = window.MONACO_LOCALE;
      const htmlLang = (document.documentElement.getAttribute('lang')||'').toLowerCase();
      const nav = (navigator.language || navigator.userLanguage || '').toLowerCase();
      const pick = explicit || htmlLang || nav || 'zh-tw';
      // Normalize zh variants
      if(pick.startsWith('zh')){
        if(pick.includes('tw')||pick.includes('hk')||pick.includes('mo')) return 'zh-tw';
        return 'zh-cn';
      }
      return pick;
    }

    function bootMonaco(){
      const locale = detectMonacoLocale();
      // Expose for Monaco to pick up
      window.MonacoEnvironment = Object.assign({}, window.MonacoEnvironment||{}, { Locale: locale });
      require.config({
        'vs/nls': { availableLanguages: { '*': locale } },
        paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.0/min/vs' }
      });
      require([ 'vs/editor/editor.main' ], function(){
  monacoEditor = monaco.editor.create(container, {
        value: textarea.value || '',
        language: 'markdown',
        theme: 'vs',
        automaticLayout: true,
        minimap: { enabled: false },
        wordWrap: 'on',
        // Improve completion UX to align with "tab completion" expectation
        quickSuggestions: { other: true, comments: false, strings: true },
        suggestOnTriggerCharacters: true,
        tabCompletion: 'on',
        acceptSuggestionOnEnter: 'on',
        suggestSelection: 'first'
      });
      // expose globally for template handlers
      window.monacoEditor = monacoEditor;

      monacoEditor.onDidChangeModelContent(()=>{
        if(lspEnabled){ sendLspDidChange(monacoEditor.getValue()); }
        // sync back to hidden textarea and trigger input for live preview
        const ta = document.getElementById('content');
        if(ta){
          ta.value = monacoEditor.getValue();
          try { ta.dispatchEvent(new Event('input', { bubbles: true })); } catch(e){ /* noop */ }
        }
  // Detect inline commands like //outline, //摘要, //qa and execute once
  maybeConsumeInlineCommand();
        if(ghostEnabled){ scheduleGhost(); }
        try { if(window.__ai_scheduleOutline) window.__ai_scheduleOutline(); } catch(_e){}
      });

      monacoEditor.onDidChangeCursorPosition(()=>{ if(ghostEnabled){ scheduleGhost(); } });

      // Keyboard hook for Tab -> accept ghost, Esc -> clear
      monacoEditor.onKeyDown((e)=>{
        try {
          if(e.keyCode === monaco.KeyCode.Tab && ghostText){
            // if suggest widget visible, do not hijack (cover various classnames)
            const sw = document.querySelector('.suggest-widget.visible, .editor-widget.suggest-widget.visible, .monaco-editor .suggest-widget.visible');
            if(sw){ return; }
            e.preventDefault(); e.stopPropagation();
            acceptGhost();
            return;
          }
          if(e.keyCode === monaco.KeyCode.Escape && ghostText){ clearGhost(); }
        } catch(err){ /* noop */ }
      });

      // Register editor action to run slash command
      const slashActionId = monacoEditor.addAction({
        id: 'ai.slashCommand',
        label: 'Run Slash Command',
        run: (ed, args)=>{ try { runSlashCommand(args && args.name, args && args.args); } catch(e){ log('slash run failed', e);} }
      }).id || 'ai.slashCommand';

      // Completion provider merging LSP + AI + Slash
      monaco.languages.registerCompletionItemProvider('markdown', {
        triggerCharacters: ['/'],
        provideCompletionItems: function(model, position){
          const word = model.getWordUntilPosition(position);
          const range = {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: word.startColumn,
            endColumn: word.endColumn
          };

          // Slash commands when token starts with '/'
          const linePrefix = model.getLineContent(position.lineNumber).slice(0, position.column - 1);
          // Allow CJK: match any non-space characters after '/'
          const slashMatch = /(^|\s)\/([^\s]*)$/.exec(linePrefix);
      if(slashMatch){
            const q = (slashMatch[2]||'').toLowerCase();
            const all = [
              { key:'summary', label:'摘要（/summary /摘要）', aliases:['摘要','summary'], prompt:'請以條列重點摘要目前內容，限 5-8 點，保留關鍵術語與數據。' },
              { key:'outline', label:'大綱（/outline /大綱）', aliases:['大綱','outline'], prompt:'根據目前內容生成清晰的 Markdown 大綱（#、##、-），不要重寫細節。' },
              { key:'bullets', label:'條列（/bullets /條列）', aliases:['條列','bullets'], prompt:'將目前內容整理為條列要點並去重，保持語意完整。' },
              { key:'rewrite-formal', label:'重寫：正式（/rewrite-formal /重寫 /正式）', aliases:['重寫','正式','rewrite','rewrite-formal'], prompt:'在不改變事實的前提下，將內容改寫為更正式、客觀、清晰的表述。' },
              { key:'rewrite-brief', label:'重寫：精簡（/rewrite-brief /精簡）', aliases:['精簡','簡化','rewrite-brief'], prompt:'壓縮贅詞並保留訊息密度，將內容改寫為更精簡版本。' },
        { key:'qa', label:'問答（/qa /問答）', aliases:['問答','qa'], prompt:'從內容中萃取 5-8 組問答對（Q/A），聚焦考點。' },
        { key:'supplement', label:'內容補充（/supplement /內容補充）', aliases:['內容補充','補充','extend','supplement'], prompt:'根據目前內容或游標附近上下文，延續撰寫 1-3 段補充，保持風格一致；直接輸出可插入的 Markdown。' },
        { key:'heading-opt', label:'標題層級優化（/heading-opt /標題層級優化）', aliases:['標題層級優化','標題優化','heading','heading-opt'], prompt:'針對全篇的標題階層做修正，輸出需要新增/修正的標題片段與必要前後文，勿重寫全文。' },
        { key:'abbr-explain', label:'縮寫詞解釋（/abbr-explain /縮寫詞解釋）', aliases:['縮寫詞解釋','縮寫','abbr','abbr-explain'], prompt:'列出文中出現的 AI/IT 相關縮寫的全名與一句中文解釋，每行一則。' },
        { key:'format-note', label:'整體格式化（/format-note /整體格式化）', aliases:['整體格式化','格式化','format','format-note'], prompt:'將筆記格式化為清晰的 Markdown 結構，修正明顯編號與標點，保持原意，直接輸出完整結果。' }
            ].filter(it => {
              if(!q) return true;
              const lower = q.toLowerCase();
              return (it.key.includes(lower) || it.label.toLowerCase().includes(lower) || (it.aliases||[]).some(a => a.toLowerCase().includes(lower)));
            });
            const items = all.map(it => ({
              label: it.label,
              kind: monaco.languages.CompletionItemKind.Function,
              // Insert the slash command text as a visible confirmation for the user
              insertText: '/' + it.key + ' ',
              filterText: '/' + (it.aliases? it.aliases.join(' '): it.key),
              range,
              detail: 'Slash 指令',
              command: { id: slashActionId, title: 'Run', arguments: [{ name: it.key, args: { prompt: it.prompt } }] }
            }));
            return { suggestions: items };
          }

          return lspRequest('textDocument/completion', {
            textDocument: { uri: 'inmemory://model.md' },
            position: { line: position.lineNumber -1, character: position.column -1 }
          }).then(resp => {
            let lspItems = [];
            if(resp && resp.result){
              const raw = Array.isArray(resp.result)? resp.result : resp.result.items;
              if(Array.isArray(raw)){
                lspItems = raw.slice(0,30).map(it => ({
                  label: it.label,
                  kind: monaco.languages.CompletionItemKind.Text,
                  insertText: it.insertText || it.label || '',
                  detail: it.detail || 'LSP',
                  documentation: (it.documentation && (it.documentation.value||it.documentation)) || '',
                  range
                }));
              }
            }
            return { suggestions: [...lspItems] };
          });
        }
      });

  // Hover provider (pure LSP)
      monaco.languages.registerHoverProvider('markdown', {
        provideHover: function(model, position){
          return lspRequest('textDocument/hover', {
            textDocument: { uri: 'inmemory://model.md' },
            position: { line: position.lineNumber -1, character: position.column -1 }
          }).then(resp => {
            let contents = [];
            if(resp && resp.result){
              const r = resp.result;
              if(r.contents){
                const arr = Array.isArray(r.contents)? r.contents : [r.contents];
                contents = arr.map(c => ({ value: typeof c === 'string'? c : (c.value||'') }));
              }
            }
            if(!contents.length) return null;
            return { range: new monaco.Range(position.lineNumber,1, position.lineNumber, model.getLineMaxColumn(position.lineNumber)), contents };
          });
        }
      });

      if(lspEnabled){ connectLsp(); }
    });
    }

    // Ensure AMD loader exists
    if(typeof window.require === 'undefined'){
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.0/min/vs/loader.min.js';
      s.onload = bootMonaco;
      document.head.appendChild(s);
    } else {
      bootMonaco();
    }
  }

  // Execute slash commands via AI enhance
  function runSlashCommand(name, opts){
    if(!name){ return; }
    const map = {
      'summary': '請以條列重點摘要目前內容，限 5-8 點，保留關鍵術語與數據。',
      'outline': '根據目前內容生成清晰的 Markdown 大綱（#、##、-），不要重寫細節。',
      'bullets': '將目前內容整理為條列要點並去重，保持語意完整。',
      'rewrite-formal': '在不改變事實的前提下，將內容改寫為更正式、客觀、清晰的表述。',
      'rewrite-brief': '壓縮贅詞並保留訊息密度，將內容改寫為更精簡版本。',
  'qa': '從內容中萃取 5-8 組問答對（Q/A），每組以「Q: …\nA: …」呈現，聚焦考點。',
      'supplement': '根據目前內容或游標附近上下文，延續撰寫 1-3 段補充，保持風格一致；直接輸出可插入的 Markdown。',
      'heading-opt': '標題層級優化：針對全篇的標題階層做修正，輸出需要新增/修正的標題片段與必要前後文，勿重寫全文。',
      'abbr-explain': '縮寫詞解釋：列出文中出現的 AI/IT 相關縮寫的全名與一句中文解釋，每行一則。',
      'format-note': '整體筆記格式化：將以下筆記重新以清晰的 Markdown 標題與列表格式化，修正明顯的編號與標點，保持原意。'
    };
    const prompt = (opts && opts.prompt) || map[name] || '';
    // For non-rewrite commands, show ghost preview first; Tab to accept.
    const isRewrite = (name === 'rewrite-formal' || name === 'rewrite-brief');
    if(!isRewrite){
      previewWithPrompt(name, prompt);
      return;
    }
    // Rewrite commands keep immediate insert behavior
    if(typeof window.aiEditorEnhance === 'function'){
      window.aiEditorEnhance(prompt);
    }
  }

  async function previewWithPrompt(name, prompt){
    if(!window.monacoEditor) return;
    // Build a snippet based on caret vicinity for better preview
    const model = window.monacoEditor.getModel();
    const full = model.getValue();
    const pos = window.monacoEditor.getPosition();
    const startLine = Math.max(1, pos.lineNumber - 10);
    const nearby = [];
    for(let ln=startLine; ln<=pos.lineNumber; ln++){ nearby.push(model.getLineContent(ln)); }
    const snippet = nearby.join('\n');
    // Map slash to ghost mode to reuse requestGhostSuggestion
    const slashToMode = {
      'supplement': 'supplement',
      'heading-opt': 'heading-opt',
      'abbr-explain': 'abbr-explain',
      'format-note': 'format-note',
      'summary': 'supplement',
      'outline': 'heading-opt',
      'bullets': 'supplement',
      'qa': 'qa'
    };
    const mode = slashToMode[name] || 'supplement';
    try{
  ghostMode = mode;
      const resp = await requestGhostSuggestion(mode, snippet, full);
      if(!resp || !resp.text) return;
      ghostFullText = String(resp.text).trim();
      ghostText = ghostFullText.replace(/\s+/g,' ').slice(0,120);
      applyGhostAtCursor(ghostText);
      // auto-enable ghost so Tab works
      if(!ghostEnabled){ ghostEnabled = true; }
  const badge = document.getElementById('ghost_mode_badge');
  if(badge){ badge.textContent = ghostModeLabel(ghostMode); }
    }catch(e){ log('previewWithPrompt failed', e); }
  }

  function normalizeCmd(alias){
    const a = (alias||'').toLowerCase();
    if(['summary','摘要'].includes(a)) return 'summary';
    if(['outline','大綱'].includes(a)) return 'outline';
    if(['bullets','條列','列表'].includes(a)) return 'bullets';
    if(['rewrite-formal','重寫','正式','formal'].includes(a)) return 'rewrite-formal';
    if(['rewrite-brief','精簡','簡化','brief'].includes(a)) return 'rewrite-brief';
    if(['qa','問答'].includes(a)) return 'qa';
  if(['supplement','內容補充','補充','extend'].includes(a)) return 'supplement';
  if(['heading-opt','標題層級優化','標題優化','heading'].includes(a)) return 'heading-opt';
  if(['abbr-explain','縮寫詞解釋','縮寫','abbr'].includes(a)) return 'abbr-explain';
  if(['format-note','整體格式化','格式化','format'].includes(a)) return 'format-note';
    return null;
  }

  function maybeConsumeInlineCommand(){
    if(inlineCmdGuard || !monacoEditor) return;
    try{
      const model = monacoEditor.getModel();
      if(!model) return;
      const pos = monacoEditor.getPosition();
      const lineText = model.getLineContent(pos.lineNumber);
      const m = /\/\/([^\s/#]+)/.exec(lineText);
      if(!m) return;
      const raw = m[1];
      const cmd = normalizeCmd(raw);
      if(!cmd) return;
      const token = '//' + raw;
      const idx = lineText.indexOf(token);
      if(idx < 0) return;
      const startColumn = idx + 1; // 1-based
      const endColumn = idx + token.length + 1;
      inlineCmdGuard = true;
      monacoEditor.executeEdits('inline-cmd', [{
        range: new monaco.Range(pos.lineNumber, startColumn, pos.lineNumber, endColumn),
        text: '',
        forceMoveMarkers: true
      }]);
      // Defer command run to next tick to avoid re-entrancy on the same change
      setTimeout(()=>{ try { runSlashCommand(cmd); } finally { inlineCmdGuard = false; } }, 0);
    }catch(e){ inlineCmdGuard = false; }
  }

  function connectLsp(){
    try {
  if(!AI_GATEWAY_BASE){ return; }
  const base = new URL(AI_GATEWAY_BASE);
  const wsProto = base.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = wsProto + '//' + base.host + '/lsp/markdown' + (GATEWAY_TOKEN? ('?token=' + encodeURIComponent(GATEWAY_TOKEN)) : '');
      lspSocket = new WebSocket(wsUrl);
      lspSocket.onopen = ()=>{ 
        log('LSP socket open'); 
        // safety: reset counters so versioning starts fresh after reconnect
  pendingChangeId = 0;
  // reset flags for clean handshake
  opened = false; lspReady = false; lspInitialized = false; didOpenSent = false; pendingChangeBuffer = null;
  sendLspInitialize(); 
      };
      lspSocket.onmessage = (ev)=>{ handleLspMessage(ev.data); };
      lspSocket.onerror = (e)=>{ log('LSP error', e); };
      lspSocket.onclose = ()=>{ 
        log('LSP closed'); 
        // ensure next connect will resend initialize/didOpen
  opened = false; lspReady = false; lspInitialized = false; didOpenSent = false;
        // auto-reconnect with simple backoff
        setTimeout(()=>{ if(lspEnabled){ connectLsp(); } }, 1000);
      };
    } catch(e){ log('LSP connect failed', e); }
  }

  function handleLspMessage(raw){
    if(!raw) return;
    // Marksman over proxy sends raw JSON objects per frame
    let obj;
    try { obj = JSON.parse(raw); } catch(e){ return; }
    if(obj && obj.method === 'textDocument/publishDiagnostics'){
      applyDiagnostics(obj.params);
      return;
    }
    if(obj && Object.prototype.hasOwnProperty.call(obj,'id')){
      const resolver = pendingLsp.get(obj.id);
      if(resolver){ pendingLsp.delete(obj.id); resolver(obj); }
      // Initialize response (id=1) -> now send initialized + didOpen and enable changes
      if(obj.id === 1 && obj.result !== undefined){
        lspInitialized = true;
        // send initialized then didOpen
        sendLsp({ jsonrpc: '2.0', method: 'initialized', params: {} });
        sendLspDidOpen();
        didOpenSent = true;
        lspReady = true;
        if(pendingChangeBuffer != null){
          try { sendLspDidChange(pendingChangeBuffer); } finally { pendingChangeBuffer = null; }
        }
      }
    }
  }

  function applyDiagnostics(params){
    if(!monacoEditor || !params) return;
    const markers = (params.diagnostics||[]).map(di => ({
      severity: mapSeverity(di.severity),
      startLineNumber: di.range.start.line + 1,
      startColumn: di.range.start.character + 1,
      endLineNumber: di.range.end.line + 1,
      endColumn: di.range.end.character + 1,
      message: di.message,
      source: di.source || 'LSP'
    }));
    monaco.editor.setModelMarkers(monacoEditor.getModel(), 'lsp', markers);
  }

  function mapSeverity(s){
    switch(s){
      case 1: return monaco.MarkerSeverity.Error;
      case 2: return monaco.MarkerSeverity.Warning;
      case 3: return monaco.MarkerSeverity.Info;
      case 4: return monaco.MarkerSeverity.Hint;
      default: return monaco.MarkerSeverity.Info;
    }
  }

  function sendLsp(msg){
    if(lspSocket && lspSocket.readyState === 1){
      lspSocket.send(typeof msg === 'string'? msg : JSON.stringify(msg));
    }
  }

  function lspRequest(method, params){
    return new Promise(resolve => {
      const id = ++lspRequestId;
      pendingLsp.set(id, resolve);
      sendLsp({ jsonrpc:'2.0', id, method, params });
      setTimeout(()=>{
        if(pendingLsp.has(id)){
          pendingLsp.delete(id);
          resolve(null);
        }
      }, 2000);
    });
  }

  function sendLspInitialize(){
    if(opened) return;
    opened = true;
  lspInitialized = false; didOpenSent = false; lspReady = false;
  sendLsp({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { capabilities: {} } });
  }

  function sendLspDidOpen(){
    if(!monacoEditor) return;
    sendLsp({ jsonrpc: '2.0', method: 'textDocument/didOpen', params: { textDocument: { uri: 'inmemory://model.md', languageId: 'markdown', version: 1, text: monacoEditor.getValue() } } });
  }

  function sendLspDidChange(latestText){
    if(!monacoEditor) return;
  if(!lspReady || !didOpenSent){
      // buffer the latest text; will flush after didOpen
      pendingChangeBuffer = latestText != null ? latestText : monacoEditor.getValue();
      return;
    }
    pendingChangeId += 1;
    const text = latestText != null ? latestText : monacoEditor.getValue();
    sendLsp({ jsonrpc: '2.0', method: 'textDocument/didChange', params: { textDocument: { uri: 'inmemory://model.md', version: pendingChangeId }, contentChanges: [{ text }] } });
  }

  // AI Detection retired

  // Expose enhancement request
  async function requestEnhancement(input){
    if(!monacoEditor) return;
    let prompt = '';
    let extraCtx = null;
    let overrideSource = null;
    if(typeof input === 'string'){
      prompt = input;
    } else if(input && typeof input === 'object'){
      prompt = input.prompt || '';
      extraCtx = input.context || null;
      overrideSource = input.sourceText || null;
    }
    const current = monacoEditor.getValue();
    const sel = monacoEditor.getSelection();
    const isSelection = sel && (sel.startLineNumber !== sel.endLineNumber || sel.startColumn !== sel.endColumn);
    let selectedText = '';
    if(isSelection){
      try { selectedText = monacoEditor.getModel().getValueInRange(sel); } catch(_e){}
    }
    const sourceText = (overrideSource != null ? overrideSource : (selectedText || current));
    try {
      let resp;
      if(useGateway){
        const headers = { 'Content-Type': 'application/json' };
        if(GATEWAY_TOKEN){ headers['x-ai-gateway-token'] = GATEWAY_TOKEN; }
        const body = {
          method: 'POST', headers,
          body: JSON.stringify({ enhancement_request: prompt || '優化內容並補充關鍵背景', current_content: sourceText, title: document.getElementById('title')?.value || '', context: extraCtx || {} })
        };
        resp = await fetch(AI_GATEWAY_BASE + '/ai/enhance', body);
      } else {
        // Fallback to legacy Flask enhancement via detect-text action
        const body = {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'generate_enhancement', enhancement_request: prompt || '優化內容並補充關鍵背景', current_content: sourceText, title: document.getElementById('title')?.value || '', context: extraCtx || {} })
        };
        resp = await fetch('/notes/detect-text', body);
      }
      const data = await resp.json();
      const out = (data.enhanced_content || data.generated_content || '').toString();
      if(out){
        // Insert result at cursor with safe spacing (no full replace)
        const ed = monacoEditor;
        const sel = ed.getSelection();
        const isSelection = sel && (sel.startLineNumber !== sel.endLineNumber || sel.startColumn !== sel.endColumn);
        const pos = ed.getPosition();
        // add a leading newline if not at column 1 and not replacing from column 1
        const needsLead = !isSelection && pos.column > 1;
        let block = out.trimEnd();
        // ensure ending newline
        if(!/\n$/.test(block)) block += '\n';
        const textToInsert = (needsLead? '\n' : '') + block + '\n';
        const range = isSelection
          ? new monaco.Range(sel.startLineNumber, sel.startColumn, sel.endLineNumber, sel.endColumn)
          : new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column);
        ed.executeEdits('ai-enhance-insert', [{ range, text: textToInsert, forceMoveMarkers: true }]);
        // optional: reveal the inserted area
        try { ed.revealLineInCenter(pos.lineNumber + (textToInsert.match(/\n/g)||[]).length); } catch(_e){}
        ed.focus();
      }
    } catch(e){ log('Enhance failed', e); }
  }
  window.aiEditorEnhance = requestEnhancement;

  function wireToggles(){
    const lspToggle = document.getElementById('toggle_lsp_support');
    const modeToggle = (window.ensureModeToggle && window.ensureModeToggle()) || null;
    // Inject ghost toggle if missing
  if(!document.getElementById('toggle_ghost_text')){
      const ref = document.getElementById('toggle_lsp_support')?.closest('.form-check') || document.getElementById('smart_ai_mode')?.closest('.form-check');
      if(ref){
        const w = document.createElement('div');
        w.className = 'form-check form-switch ms-2';
    w.innerHTML = '<input class="form-check-input" type="checkbox" id="toggle_ghost_text">\
<label class="form-check-label" for="toggle_ghost_text"><small><i class="fas fa-magic me-1"></i>Ghost</small></label>\
<i class="fas fa-info-circle ms-1 text-muted" title="Ghost：AI 行內預視。Tab 接受、Esc 取消；有建議清單時 Tab 不會插入預視。"></i>';
        ref.parentNode.insertBefore(w, ref.nextSibling);
      }
    }
    const ghostToggle = document.getElementById('toggle_ghost_text');

  if(lspToggle){
      lspEnabled = lspToggle.checked;
      lspToggle.addEventListener('change', ()=>{
        lspEnabled = lspToggle.checked;
        if(lspEnabled && !lspSocket){ connectLsp(); }
      });
    }
    if(ghostToggle){
      ghostEnabled = ghostToggle.checked;
      ghostToggle.addEventListener('change', ()=>{
        ghostEnabled = ghostToggle.checked;
        if(!ghostEnabled){ clearGhost(); } else { scheduleGhost(); }
      });
    }

  // Ghost 模式下拉選單已移除（改為以斜線指令顯示預覽）
  ensureGhostBadge();

  if(modeToggle){
      modeToggle.addEventListener('click', (e)=>{
        const btn = e.target.closest('button[data-mode]');
        if(!btn) return;
        const mode = btn.getAttribute('data-mode');
    if(window.setEditorMode){ window.setEditorMode(mode); }
      });
    }
  }

  function ensureGhostBadge(){
    if(document.getElementById('ghost_mode_badge')) return;
    const badge = document.createElement('span');
    badge.id = 'ghost_mode_badge';
    badge.className = 'badge rounded-pill bg-secondary ms-2';
    badge.style.userSelect = 'none';
    badge.title = '目前 Ghost 預覽模式（由斜線指令觸發）';
    badge.textContent = ghostModeLabel(ghostMode);
    const ref = document.getElementById('toggle_lsp_support')?.closest('.form-check');
    if(ref && ref.parentNode){ ref.parentNode.insertBefore(badge, ref.nextSibling); }
  }

  function ghostModeLabel(mode){
    switch(mode){
      case 'supplement': return '內容補充';
      case 'heading-opt': return '標題層級優化';
      case 'abbr-explain': return '縮寫詞解釋';
  case 'qa': return '問答生成';
      case 'format-note': return '整體格式化';
      default: return 'Ghost';
    }
  }

  function syncOnSubmit(){
    const form = document.querySelector('form');
    if(!form) return;
    form.addEventListener('submit', ()=>{
      if(monacoEditor){
        const textarea = document.getElementById('content');
        textarea.value = monacoEditor.getValue();
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    // Inject LSP toggle if missing
    if(!document.getElementById('toggle_lsp_support')){
      const ref = document.getElementById('smart_ai_mode')?.closest('.form-check');
      if(ref){
        const wrapper = document.createElement('div');
        wrapper.className = 'form-check form-switch me-3';
        wrapper.innerHTML = '<input class="form-check-input" type="checkbox" id="toggle_lsp_support" checked><label class="form-check-label" for="toggle_lsp_support"><small><i class="fas fa-code me-1"></i>LSP語法輔助</small></label>';
        ref.parentNode.insertBefore(wrapper, ref);
      }
    }
    probeGateway().finally(()=>{
      wireToggles();
      syncOnSubmit();
  initMonaco();
  if(window.initOutlinePanel){ window.initOutlinePanel(); }
  if(window.setupSmartPaste){ window.setupSmartPaste(); }
  // Badge update for gateway / legacy
      const badge = document.getElementById('ai-gateway-status');
      if(badge){
        badge.classList.remove('d-none');
        badge.textContent = useGateway? 'Gateway' : 'Legacy Flask';
        badge.classList.add(useGateway? 'bg-success':'bg-secondary');
      }
    });


    // NOTE: 不劫持 generate-smart-content 按鈕
    // "AI生成筆記"按鈕應該使用正常的筆記生成流程 (smart_ai_generate)
    // 而不是 Ghost AI 的內容增強功能
    // Ghost AI 功能只通過斜線命令 (/) 觸發
    
    // Hook existing generate-smart-content button for enhancement via gateway if available
    // const genBtn = document.getElementById('generate-smart-content');
    // if(genBtn && useGateway){
    //   // Capture phase handler to override template fallback when Gateway is present
    //   genBtn.addEventListener('click', function(ev){
    //     ev.preventDefault(); ev.stopPropagation(); ev.stopImmediatePropagation();
    //     const prompt = document.getElementById('ai_prompt')?.value || '';
    //     genBtn.disabled = true;
    //     const original = genBtn.innerHTML;
    //     genBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>AI生成中...';
    //     aiEditorEnhance(prompt).finally(()=>{ genBtn.disabled=false; genBtn.innerHTML = original; });
    //     return false;
    //   }, true);
    // }

    // Visual difference for modes (Write vs Review)
    const styleTag = document.createElement('style');
    styleTag.textContent = '[data-ai-mode="review"] #editor-root{ border-color:#0d6efd !important; box-shadow:0 0 0 .2rem rgba(13,110,253,.25); }\n' +
      '[data-ai-mode="write"] #editor-root{ border-color:#ccc !important; box-shadow:none; }';
    document.head.appendChild(styleTag);
    // Default mode
    if(!document.body.getAttribute('data-ai-mode')){ document.body.setAttribute('data-ai-mode','write'); }
  });
})();

// ----------------- UI helpers: Mode, Outline, Smart Paste -----------------
(function(){
  let outlineTimer = null;
  function ensureModeToggle(){
    // Inject a simple mode toggle (Write / Review)
    if(document.getElementById('ai-mode-toggle')) return document.getElementById('ai-mode-toggle');
    const ref = document.getElementById('toggle_lsp_support')?.closest('.form-check') || document.getElementById('smart_ai_mode')?.closest('.form-check');
    if(!ref || !ref.parentNode) return null;
    const group = document.createElement('div');
    group.className = 'btn-group btn-group-sm ms-2';
    group.id = 'ai-mode-toggle';
    group.innerHTML = '<button type="button" class="btn btn-outline-secondary active" data-mode="write">Write</button>\
<button type="button" class="btn btn-outline-secondary" data-mode="review">Review</button>';
    ref.parentNode.insertBefore(group, ref.nextSibling);
    return group;
  }

  function setMode(mode){
    const wrap = document.getElementById('ai-mode-toggle');
    if(wrap){
      wrap.querySelectorAll('button').forEach(b=> b.classList.toggle('active', b.getAttribute('data-mode')===mode));
    }
    if(mode==='review'){
  // Review mode visual only (AI檢測已退休)
    }
    document.body.setAttribute('data-ai-mode', mode);
  }

  function initOutlinePanel(){
    const root = document.createElement('div');
    root.id = 'outline-panel';
    root.style.position = 'fixed';
    root.style.right = '12px';
    root.style.top = '120px';
    root.style.width = '280px';
    root.style.maxHeight = '60%';
    root.style.overflow = 'auto';
    root.style.zIndex = '1030';
    root.className = 'card shadow-sm d-none';
    root.innerHTML = '<div class="card-header py-2"><i class="fas fa-list me-1"></i> 大綱 Outline <button type="button" id="outline-close" class="btn btn-sm btn-light float-end">×</button></div><div id="outline-body" class="list-group list-group-flush"></div>';
    document.body.appendChild(root);
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.id = 'outline-toggle';
    toggleBtn.className = 'btn btn-outline-secondary btn-sm';
    toggleBtn.style.position = 'fixed';
    toggleBtn.style.right = '12px';
    toggleBtn.style.top = '80px';
    toggleBtn.style.zIndex = '1030';
    toggleBtn.innerHTML = '<i class="fas fa-list"></i>';
    document.body.appendChild(toggleBtn);

    toggleBtn.addEventListener('click', ()=> root.classList.toggle('d-none'));
    root.querySelector('#outline-close').addEventListener('click', ()=> root.classList.add('d-none'));

    // Update outline when editor content changes (debounced)
    if(window.monacoEditor){
      window.monacoEditor.onDidChangeModelContent(()=> scheduleOutline());
    } else {
      document.addEventListener('keyup', (e)=>{ if(e.target && e.target.id==='content'){ scheduleOutline(); } });
    }
    scheduleOutline();
  }

  function scheduleOutline(){
    if(outlineTimer) clearTimeout(outlineTimer);
    outlineTimer = setTimeout(updateOutline, 500);
  }

  function parseHeadings(text){
    const lines = text.split(/\n/);
    const items = [];
    for(let i=0;i<lines.length;i++){
      const m = /^(#{1,6})\s+(.*)$/.exec(lines[i]);
      if(m){ items.push({ line: i+1, level: m[1].length, title: m[2].trim() }); }
    }
    return items;
  }

  function updateOutline(){
    const body = document.getElementById('outline-body');
    if(!body || !window.monacoEditor) return;
    const text = window.monacoEditor.getValue();
    const items = parseHeadings(text);
    body.innerHTML = '';
    if(!items.length){
      body.innerHTML = '<div class="list-group-item small text-muted">（沒有偵測到標題）</div>';
      return;
    }
    items.forEach(it=>{
      const a = document.createElement('a');
      a.href = '#';
      a.className = 'list-group-item list-group-item-action';
      a.style.paddingLeft = (8 + (it.level-1)*12)+'px';
      a.textContent = (new Array(it.level).fill('•').join('') + ' ' + it.title);
      a.addEventListener('click', (ev)=>{
        ev.preventDefault();
        if(window.monacoEditor){
          window.monacoEditor.revealLineInCenter(it.line);
          window.monacoEditor.setPosition({ lineNumber: it.line, column: 1 });
          window.monacoEditor.focus();
        }
      });
      body.appendChild(a);
    });
  }

  function setupSmartPaste(){
    const container = document.getElementById('editor-root');
    if(!container) return;
    container.addEventListener('paste', function(e){
      if(!window.monacoEditor) return;
      const cd = e.clipboardData || window.clipboardData;
      if(!cd) return;
      const html = cd.getData('text/html');
      const text = cd.getData('text/plain');
      if(!html){ return; }
      try {
        const cleaned = htmlToMarkdownish(html) || text;
        if(cleaned){
          e.preventDefault();
          insertAtCursor(cleaned);
          if(cleaned.length > 800){
            if(window.showAlert){ window.showAlert('info', '偵測到大段貼上，是否需要提煉重點？（可使用 /summary）'); }
          }
        }
      } catch(err){ /* noop */ }
    });
  }

  function insertAtCursor(s){
    const ed = window.monacoEditor; if(!ed) return;
    const pos = ed.getPosition();
    ed.executeEdits('smart-paste', [{ range: new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column), text: s, forceMoveMarkers: true }]);
  }

  function htmlToMarkdownish(html){
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    // Remove style/script
    doc.querySelectorAll('script,style,noscript').forEach(n=>n.remove());
    // Links
    doc.querySelectorAll('a[href]').forEach(a=>{ a.textContent = `[${a.textContent}](${a.getAttribute('href')})`; a.replaceWith(a.ownerDocument.createTextNode(a.textContent)); });
    // Headers
    for(let i=6;i>=1;i--){ doc.querySelectorAll('h'+i).forEach(h=>{ const prefix = '#'.repeat(i)+' '; const t=h.textContent.trim(); const p=doc.createElement('p'); p.textContent=prefix+t; h.replaceWith(p); }); }
    // Code blocks
    doc.querySelectorAll('pre,code').forEach(el=>{ const t = el.textContent; const p = doc.createElement('p'); p.textContent = '\n```\n'+t+'\n```\n'; el.replaceWith(p); });
    // Lists
    doc.querySelectorAll('li').forEach(li=>{ const t=li.textContent.trim(); const p=doc.createElement('p'); p.textContent='- '+t; li.replaceWith(p); });
    // Images as alt(url)
    doc.querySelectorAll('img').forEach(img=>{ const alt = img.getAttribute('alt')||''; const src = img.getAttribute('src')||''; const p=doc.createElement('p'); p.textContent = `![${alt}](${src})`; img.replaceWith(p); });
    const out = doc.body.innerText
      .replace(/\u00a0/g,' ')
      .replace(/\n{3,}/g,'\n\n')
      .trim();
    return out;
  }

  // expose for tests
  window.__ai_setMode = setMode;
  window.setEditorMode = setMode;
  window.__ai_scheduleOutline = scheduleOutline;
  window.__ai_updateOutline = updateOutline;
  window.__ai_htmlToMarkdownish = htmlToMarkdownish;
  window.ensureModeToggle = ensureModeToggle;
  window.initOutlinePanel = initOutlinePanel;
  window.setupSmartPaste = setupSmartPaste;
})();
