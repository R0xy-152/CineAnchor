"""Build new viewer.html with left sidebar + guided right panel."""
with open('static/viewer.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract JS module code (kept unchanged)
js_start = content.index('<script type="module">')
js_code = content[js_start:]

# New CSS
new_css = '''  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden; background: #111; }
    #canvas { display: block; }

    /* === Left Sidebar === */
    #left-sidebar {
      position: fixed; left: 0; top: 0; width: 300px; height: 100vh;
      background: rgba(18,18,28,0.96); border-right: 1px solid rgba(255,255,255,0.08);
      z-index: 20; overflow-y: auto; padding: 16px; color: #ccc; font-size: 12px;
      scrollbar-width: thin; transition: transform 0.3s ease;
    }
    #left-sidebar.collapsed { transform: translateX(-100%); }
    #sidebar-toggle {
      position: fixed; left: 0; top: 50%; transform: translateY(-50%);
      width: 22px; height: 60px; background: rgba(124,58,237,0.85); color: #fff;
      border-radius: 0 8px 8px 0; z-index: 19; cursor: pointer;
      display: none; align-items: center; justify-content: center; font-size: 12px;
    }
    #left-sidebar.collapsed ~ #sidebar-toggle { display: flex; }
    .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
    .sidebar-header h2 { font-size: 16px; font-weight: 700; color: #fff; }
    .sidebar-header h2 span { color: #7c3aed; }
    .btn-collapse {
      width: 28px; height: 28px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.06); color: #888; font-size: 14px; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
    }
    .btn-collapse:hover { background: rgba(255,255,255,0.12); color: #fff; }
    .sidebar-section { margin-bottom: 14px; padding-bottom: 14px; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .sidebar-section:last-child { border-bottom: none; }
    .sidebar-section h3 { font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }

    /* Form controls */
    textarea, input[type="text"], select {
      width: 100%; padding: 8px 10px; border-radius: 6px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.05); color: #ddd; font-size: 12px; outline: none;
    }
    textarea { resize: vertical; min-height: 44px; }
    select { cursor: pointer; }
    button {
      padding: 8px 12px; border-radius: 6px; border: none;
      font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s;
    }
    button:active { transform: scale(0.97); }
    .btn-primary { background: #7c3aed; color: #fff; width: 100%; padding: 10px; }
    .btn-primary:hover { background: #6d28d9; }
    .btn-primary:disabled { background: #4c1d95; opacity: 0.5; cursor: not-allowed; }
    .btn-success { background: #16a34a; color: #fff; width: 100%; padding: 10px; }
    .btn-success:hover { background: #15803d; }
    .btn-success:disabled { background: #166534; opacity: 0.5; cursor: not-allowed; }
    .btn-outline {
      background: rgba(255,255,255,0.05); color: #aaa; border: 1px solid rgba(255,255,255,0.1);
      width: 100%; padding: 9px;
    }
    .btn-outline:hover { background: rgba(255,255,255,0.1); color: #ddd; }
    .btn-sm { font-size: 10px; padding: 5px 10px; }

    /* Scene chips */
    .chip-row { display: flex; gap: 3px; flex-wrap: wrap; margin-top: 4px; }
    .chip {
      padding: 4px 8px; border-radius: 12px; font-size: 10px; font-weight: 500;
      border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04);
      color: #999; cursor: pointer; transition: all 0.15s;
    }
    .chip:hover { background: rgba(124,58,237,0.2); border-color: #7c3aed; color: #fff; }

    /* Camera mode */
    .mode-row { display: flex; gap: 4px; }
    .mode-btn {
      flex: 1; padding: 6px 0; border-radius: 5px; font-size: 11px; text-align: center;
      border: 1px solid rgba(255,255,255,0.12); background: rgba(255,255,255,0.04);
      color: #888; cursor: pointer; transition: all 0.15s;
    }
    .mode-btn.active { background: #4f46e5; color: #fff; border-color: #4f46e5; }
    .mode-btn:hover:not(.active) { background: rgba(255,255,255,0.08); }

    /* Camera presets */
    .preset-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3px; margin-top: 6px; }
    .preset-btn {
      padding: 5px 4px; border-radius: 5px; font-size: 10px; font-weight: 500;
      border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.03);
      color: #999; cursor: pointer; text-align: center; transition: all 0.15s;
    }
    .preset-btn:hover { background: rgba(124,58,237,0.2); border-color: #7c3aed; color: #fff; }
    .preset-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    #preset-desc { font-size: 10px; color: #666; margin-top: 4px; min-height: 14px; }

    /* KF list */
    #kf-list { max-height: 100px; overflow-y: auto; margin-top: 4px; scrollbar-width: thin; }
    .kf-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 3px 6px; margin: 1px 0; background: rgba(255,255,255,0.03);
      border-radius: 4px; font-size: 10px; cursor: pointer;
    }
    .kf-item:hover { background: rgba(255,255,255,0.06); }
    .kf-item .del { color: #f87171; cursor: pointer; padding: 1px 3px; }
    #kf-count { font-size: 10px; color: #888; margin-left: 4px; }
    .hints { font-size: 10px; color: #555; line-height: 1.7; margin-top: 8px; }
    .hints strong { color: #888; }

    /* === Right Panel === */
    #panel {
      position: fixed; top: 16px; right: 16px; width: 260px;
      background: rgba(20,20,30,0.94); border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px; padding: 18px; color: #ccc; backdrop-filter: blur(16px);
      z-index: 10; font-size: 12px;
    }
    .workflow-progress { display: flex; align-items: center; gap: 0; margin-bottom: 16px; }
    .wf-step { display: flex; flex-direction: column; align-items: center; flex: 1; }
    .wf-dot {
      width: 20px; height: 20px; border-radius: 50%; background: rgba(255,255,255,0.08);
      color: #555; font-size: 10px; font-weight: 700; display: flex;
      align-items: center; justify-content: center; transition: all 0.3s;
    }
    .wf-dot.done { background: #16a34a; color: #fff; }
    .wf-dot.active { background: #7c3aed; color: #fff; box-shadow: 0 0 8px rgba(124,58,237,0.4); }
    .wf-line { flex: 1; height: 1px; background: rgba(255,255,255,0.08); margin: 0 2px; }
    .wf-line.done { background: #16a34a; }
    .wf-label { font-size: 9px; color: #555; margin-top: 3px; text-align: center; }
    .wf-label.active { color: #a78bfa; }
    .guide-box {
      background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
      border-radius: 10px; padding: 14px; margin-bottom: 10px;
    }
    .guide-box h4 { font-size: 13px; color: #fff; margin-bottom: 4px; }
    .guide-box p { font-size: 11px; color: #666; margin-bottom: 10px; line-height: 1.5; }
    .guide-box p .highlight { color: #a78bfa; }
    #status-bar { font-size: 10px; color: #555; margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); line-height: 1.8; }
    #status-bar .ok { color: #4ade80; }
    #status-bar .err { color: #f87171; }
    #status-bar .warn { color: #fbbf24; }
    .divider { border-top: 1px solid rgba(255,255,255,0.06); margin: 8px 0; }
    #gen-progress { margin-top: 4px; display: none; }
    #gen-progress .bar-bg { width: 100%; height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden; }
    #gen-progress .bar-fill { height: 100%; width: 0%; background: #7c3aed; border-radius: 2px; transition: width 0.3s; }
    #gen-progress .elapsed { font-size: 10px; color: #555; text-align: center; margin-top: 2px; }
    #depth-progress, #preview-progress { font-size: 10px; color: #666; margin-top: 2px; display: none; }

    /* HUD + Timeline + Modals */
    #pose-hud { position: fixed; bottom: 90px; left: 16px; background: rgba(20,20,30,0.85); border-radius: 8px; padding: 8px 12px; color: #666; font-size: 10px; font-family: 'SF Mono','Fira Code',monospace; z-index: 10; }
    #pose-hud span { color: #ccc; }
    #instructions { position: fixed; bottom: 90px; right: 280px; color: #444; font-size: 10px; text-align: right; z-index: 10; line-height: 1.6; }
    #toast { position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); background: rgba(0,0,0,0.88); color: #fff; padding: 12px 24px; border-radius: 8px; font-size: 14px; z-index: 100; pointer-events: none; opacity: 0; transition: opacity 0.2s; }
    #toast.show { opacity: 1; }
    #timeline-wrap { position: fixed; bottom: 0; left: 0; right: 276px; height: 82px; background: rgba(20,20,30,0.94); border-top: 1px solid rgba(255,255,255,0.08); z-index: 10; display: flex; flex-direction: column; padding: 4px 8px; }
    #timeline-controls { display: flex; align-items: center; gap: 6px; height: 24px; }
    #timeline-controls button { background: rgba(255,255,255,0.08); border: none; color: #aaa; border-radius: 4px; padding: 2px 8px; font-size: 11px; cursor: pointer; }
    #timeline { flex: 1; position: relative; cursor: pointer; min-height: 50px; }
    #timeline canvas { width: 100%; height: 100%; }
    .tl-kf { position: absolute; top: 50%; width: 10px; height: 10px; background: #7c3aed; border: 2px solid #fff; border-radius: 50%; transform: translate(-50%,-50%); cursor: pointer; z-index: 2; }
    .tl-kf:hover { background: #a78bfa; }
    .tl-cursor { position: absolute; top: 0; width: 2px; height: 100%; background: #4ade80; z-index: 1; }
    #demo-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 50; display: none; align-items: center; justify-content: center; }
    #demo-modal { background: rgba(20,20,30,0.97); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 32px; max-width: 420px; color: #ccc; text-align: center; }
    #demo-modal h2 { font-size: 20px; color: #fff; margin-bottom: 8px; }
    .demo-subtitle { font-size: 13px; color: #888; margin-bottom: 20px; }
    .demo-steps { display: flex; flex-direction: column; gap: 10px; text-align: left; margin-bottom: 20px; }
    .demo-step { display: flex; align-items: center; gap: 8px; font-size: 13px; }
    .step-num { width: 20px; height: 20px; border-radius: 50%; background: #7c3aed; color: #fff; font-size: 11px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
    #depth-video-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 50; display: none; align-items: center; justify-content: center; }
    #depth-preview-corner { position: fixed; bottom: 90px; right: 280px; width: 256px; height: 160px; background: #000; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; overflow: hidden; z-index: 8; }
    #depth-preview-corner .label { position: absolute; top: 2px; left: 4px; font-size: 9px; color: #4ade80; font-family: monospace; z-index: 2; }
    #depth-overlay { position: fixed; inset: 0; z-index: 5; pointer-events: none; display: none; background: rgba(0,0,0,0.4); }
    #depth-overlay canvas { width: 100%; height: 100%; }
  </style>'''

# New HTML body
new_html = '''</head>
<body>

<canvas id="canvas"></canvas>

<!-- ════════════ LEFT SIDEBAR ════════════ -->
<div id="left-sidebar">
  <div class="sidebar-header">
    <h2><span>Cine</span>Anchor</h2>
    <button class="btn-collapse" onclick="toggleSidebar()" title="Fold sidebar">X</button>
  </div>

  <div class="sidebar-section">
    <h3>1. Create Scene</h3>
    <textarea id="prompt-input" placeholder="Describe your 3D scene...">a cozy japanese zen garden with a wooden bridge over a pond, cherry blossom trees</textarea>
    <div class="chip-row">
      <span class="chip" onclick="switchScene('zen garden')">Zen Garden</span>
      <span class="chip" onclick="switchScene('scifi corridor')">Scifi</span>
      <span class="chip" onclick="switchScene('floating islands')">Floating</span>
      <span class="chip" onclick="switchScene('desert ruins')">Desert</span>
      <span class="chip" onclick="switchScene('forest glade')">Forest</span>
    </div>
    <button class="btn-primary" id="btn-generate" onclick="generateScene()" style="margin-top:8px">Generate 3D Scene</button>
    <div id="gen-progress">
      <div class="bar-bg"><div class="bar-fill" id="gen-bar"></div></div>
      <div class="elapsed" id="gen-elapsed"></div>
    </div>
  </div>

  <div class="sidebar-section">
    <h3>2. Camera Mode</h3>
    <div class="mode-row">
      <div class="mode-btn active" id="btn-orbit" onclick="setMode('orbit')">Orbit</div>
      <div class="mode-btn" id="btn-drone" onclick="setMode('drone')">Drone</div>
      <div class="mode-btn" id="btn-fps" onclick="setMode('fps')">FPS</div>
    </div>
  </div>

  <div class="sidebar-section">
    <h3>3. Camera Path</h3>
    <div class="preset-grid" id="preset-grid">
      <button class="preset-btn" data-preset="nolan_orbit" onclick="applyPreset(this)">Nolan Orbit</button>
      <button class="preset-btn" data-preset="anime_closeup" onclick="applyPreset(this)">Anime Close-up</button>
      <button class="preset-btn" data-preset="dolly_reveal" onclick="applyPreset(this)">Dolly Reveal</button>
      <button class="preset-btn" data-preset="drone_ascend" onclick="applyPreset(this)">Drone Ascend</button>
      <button class="preset-btn" data-preset="hero_tracking" onclick="applyPreset(this)">Hero Tracking</button>
      <button class="preset-btn" data-preset="suspense_pan" onclick="applyPreset(this)">Suspense Pan</button>
      <button class="preset-btn" data-preset="god_eye" onclick="applyPreset(this)">God's Eye</button>
      <button class="preset-btn" data-preset="whip_pan" onclick="applyPreset(this)">Whip Pan</button>
    </div>
    <div id="preset-desc"></div>

    <div class="divider"></div>

    <div style="display:flex;gap:4px">
      <button class="btn-outline" onclick="captureKeyframe()" style="flex:1">Capture (R)</button>
      <button class="btn-outline" onclick="undoKeyframe()" style="flex:1">Undo</button>
    </div>
    <div id="kf-list" style="margin-top:4px"></div>
    <span id="kf-count">0 keyframes</span>

    <input type="text" id="path-name" placeholder="Path name" style="margin-top:6px">
    <div style="display:flex;gap:4px;margin-top:4px">
      <button class="btn-outline" onclick="savePath()" style="flex:1">Save</button>
      <select id="path-select" onchange="loadPath(this.value)" style="flex:1"><option value="">-- Load --</option></select>
    </div>
  </div>

  <div class="hints">
    <strong>Orbit:</strong> Drag rotate | Scroll zoom | Right-drag pan<br>
    <strong>Fly:</strong> WASD move | Space/Ctrl up/down<br>
    <strong>Keys:</strong> R capture | P preview | Tab mode
  </div>
</div>

<div id="sidebar-toggle" onclick="toggleSidebar()">></div>

<!-- ════════════ RIGHT PANEL ════════════ -->
<div id="panel">
  <div class="workflow-progress">
    <div class="wf-step">
      <div class="wf-dot active" id="wf-dot-1">1</div>
      <div class="wf-label active" id="wf-label-1">Scene</div>
    </div>
    <div class="wf-line" id="wf-line-1"></div>
    <div class="wf-step">
      <div class="wf-dot" id="wf-dot-2">2</div>
      <div class="wf-label" id="wf-label-2">Camera</div>
    </div>
    <div class="wf-line" id="wf-line-2"></div>
    <div class="wf-step">
      <div class="wf-dot" id="wf-dot-3">3</div>
      <div class="wf-label" id="wf-label-3">Depth</div>
    </div>
    <div class="wf-line" id="wf-line-3"></div>
    <div class="wf-step">
      <div class="wf-dot" id="wf-dot-4">4</div>
      <div class="wf-label" id="wf-label-4">Preview</div>
    </div>
  </div>

  <div class="guide-box" id="guide-box">
    <h4 id="guide-title">Welcome to CineAnchor</h4>
    <p id="guide-desc">Type a prompt in the left panel and click <span class="highlight">Generate 3D Scene</span> to start.</p>
  </div>

  <div id="guide-actions">
    <button class="btn-success" onclick="renderPreviewVideo()" style="margin-top:4px">Render Preview</button>
    <button class="btn-outline" onclick="renderDepthMaps()" style="margin-top:4px">Render Depth Maps</button>
    <button class="btn-outline" onclick="showDemoResult()" style="margin-top:4px">Watch AI Demo</button>
    <div id="depth-progress"></div>
    <div id="preview-progress"></div>
  </div>

  <div id="status-bar">
    <div id="api-status">API: detecting...</div>
    <div id="scene-status"></div>
  </div>
</div>

<!-- HUD + Instructions -->
<div id="pose-hud">
  <span id="hud-mode">Orbit</span><br>
  <span id="hud-pos"></span><br>
  <span id="hud-quat"></span>
</div>

<div id="instructions">
  <div id="instr-orbit">Drag rotate | Scroll zoom | Right-drag pan<br>R capture | P preview | Space play | Tab mode</div>
  <div id="instr-fly" style="display:none">WASD fly | Space/Ctrl up/down | Mouse look<br>R capture | P preview | Tab mode</div>
</div>

<div id="toast"></div>

<!-- Timeline -->
<div id="timeline-wrap">
  <div id="timeline-controls">
    <button onclick="tlTogglePlay()" id="btn-tl-play">Play</button>
    <button onclick="tlStop()">Stop</button>
    <span id="tl-time" style="font-size:10px;color:#666">0:00 / 0:00</span>
  </div>
  <div id="timeline"></div>
</div>

<!-- Demo overlay -->
<div id="demo-overlay">
  <div id="demo-modal">
    <h2>Welcome to CineAnchor</h2>
    <p class="demo-subtitle">Scene auto-loaded. 4 steps to AI-directed cinematography:</p>
    <div class="demo-steps">
      <div class="demo-step"><span class="step-num">1</span> Explore the 3D scene</div>
      <div class="demo-step"><span class="step-num">2</span> Switch camera modes</div>
      <div class="demo-step"><span class="step-num">3</span> Apply camera presets or record manually</div>
      <div class="demo-step"><span class="step-num">4</span> Render depth maps and preview</div>
    </div>
    <button onclick="closeDemoOverlay()" class="btn-primary" style="margin-top:16px;width:auto;padding:10px 32px">Get Started</button>
  </div>
</div>

<!-- Depth video modal -->
<div id="depth-video-modal">
  <div style="background:rgba(20,20,30,0.96);border-radius:12px;padding:24px;max-width:680px;text-align:center">
    <h3 style="color:#fff;margin-bottom:4px">Preview</h3>
    <p style="color:#888;font-size:11px;margin-bottom:8px" id="depth-video-info"></p>
    <div style="width:512px;height:320px;background:#000;border-radius:8px;margin:0 auto;overflow:hidden;position:relative">
      <canvas id="depth-video-canvas" width="512" height="320" style="width:100%;height:100%"></canvas>
      <div id="depth-video-fps" style="position:absolute;bottom:4px;right:8px;color:#4ade80;font-size:10px;font-family:monospace"></div>
    </div>
    <div style="display:flex;gap:8px;justify-content:center;margin-top:8px">
      <button class="btn-primary" onclick="toggleDepthVideo()" id="btn-depth-play" style="width:auto;padding:6px 20px">Play</button>
      <button class="btn-outline" onclick="closeDepthVideo()" style="width:auto;padding:6px 20px">Close</button>
    </div>

    <div style="margin-top:16px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08)">
      <h4 style="color:#4ade80;font-size:13px;margin-bottom:6px">AI Render Demos</h4>
      <p style="color:#666;font-size:10px;margin-bottom:8px">ControlNet-Depth + AnimateDiff</p>
      <div style="display:flex;gap:4px;justify-content:center;margin-bottom:10px;flex-wrap:wrap">
        <span class="chip" onclick="switchDemoVideo('zen_garden')">Zen</span>
        <span class="chip" onclick="switchDemoVideo('scifi_corridor')">Scifi</span>
        <span class="chip" onclick="switchDemoVideo('floating_islands')">Floating</span>
        <span class="chip" onclick="switchDemoVideo('desert_ruins')">Desert</span>
        <span class="chip" onclick="switchDemoVideo('forest_glade')">Forest</span>
      </div>
      <video id="demo-video-player" controls loop muted
             style="width:100%;max-width:512px;height:auto;border-radius:8px;background:#000">
        <source src="/static/demo_output.mp4" type="video/mp4">
      </video>
    </div>
  </div>
</div>

<div id="depth-preview-corner"><span class="label">DEPTH</span><canvas id="depth-canvas-corner"></canvas></div>
<div id="depth-overlay"><canvas id="depth-canvas-overlay"></canvas></div>

'''

# Build final file
result = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>CineAnchor - AI 3D Viewer</title>\n'
result += new_css + '\n'
result += new_html + '\n'
result += js_code

with open('static/viewer.html', 'w', encoding='utf-8') as f:
    f.write(result)
print('Written', len(result), 'bytes to static/viewer.html')
