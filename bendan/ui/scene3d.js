  // ===== 🧊 3D 遊戲畫面（Three.js）— v8 起是唯一的畫面 =====
  // Python 每次重畫都放一份世界狀態 JSON 到 .bd-state；素材包（家具 OBJ、寵物 GLB）一開始就放在 .bd-assets。
  // 靜態場景（地板、牆、天花板、家具、燈）每一關只建一次；灰塵、物件、寵物、笨笨每次更新。
  // v8：牆壁加高、加天花板（俯瞰時自動「剖面」把牆降低、天花板隱形）；牆面就在格子邊界上，撞牆時笨笨真的貼上牆；
  //     受損兩階段（冒煙 → 爆炸）、掉進地洞、香蕉皮、地震……都有動畫和音效（音效跟 🔊 一起開關）。
  var T3 = null, loading3d = null, lastState = '';
  function check3d() {
    var s = q('.bd-state'), host = q('.bd-3dhost');
    if (!s || !host || s.textContent === lastState) return;
    if (T3) { lastState = s.textContent; T3.update(JSON.parse(lastState)); return; }
    var a = q('.bd-assets');
    if (!a || !a.textContent || loading3d) return;
    lastState = s.textContent;
    host.innerHTML = "<div class='bd-3dmsg'>🧊 正在佈置房間……（第一次要下載 three.js）</div>";
    var B = THREE_BASE;
    loading3d = Promise.all([import(B + '/+esm'), import(B + '/examples/jsm/loaders/GLTFLoader.js/+esm'),
      import(B + '/examples/jsm/loaders/OBJLoader.js/+esm'), import(B + '/examples/jsm/utils/SkeletonUtils.js/+esm'),
      import(B + '/examples/jsm/environments/RoomEnvironment.js/+esm')])
      .then(function (m) {
        return make3d({ THREE: m[0], GLTFLoader: m[1].GLTFLoader, OBJLoader: m[2].OBJLoader, clone: m[3].clone,
                        RoomEnvironment: m[4].RoomEnvironment }, host, JSON.parse(a.textContent));
      })
      .then(function (t) { T3 = t; T3.update(JSON.parse(lastState)); })
      .catch(function (err) {
        loading3d = null;
        host.innerHTML = "<div class='bd-3dmsg'>😵 3D 載入失敗：" + err.message +
          "<br>遊戲畫面需要網路下載 three.js（約 750 KB），請確認瀏覽器連得到 cdn.jsdelivr.net 後重新執行這一格。</div>";
      });
  }
  new MutationObserver(check3d).observe(root, { subtree: true, childList: true, characterData: true });
  check3d();

  // ---------- 🔈 音效（WebAudio 即時合成，不用下載音檔；跟 🔊 一起開關）----------
  var AC = null, noiseBuf = null, humNode = null;
  function soundOn() { return !!(bot.st && bot.st.tts); }
  function actx() {
    if (!AC) { var C = window.AudioContext || window.webkitAudioContext; if (!C) return null; AC = new C(); }
    if (AC.state === 'suspended') AC.resume();
    return AC;
  }
  root.addEventListener('pointerdown', actx, true); root.addEventListener('keydown', actx, true);
  function noise(a) {
    if (!noiseBuf) {
      noiseBuf = a.createBuffer(1, a.sampleRate * 1.5, a.sampleRate);
      var d = noiseBuf.getChannelData(0); for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    var s = a.createBufferSource(); s.buffer = noiseBuf; return s;
  }
  function env(a, g, t, peak, dur) {
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  }
  function tone(a, type, f0, f1, dur, vol, delay) {
    var t = a.currentTime + (delay || 0), o = a.createOscillator(), g = a.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
    env(a, g, t, vol, dur); o.connect(g).connect(a.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  function hiss(a, freq, q, dur, vol, delay, sweepTo) {
    var t = a.currentTime + (delay || 0), n = noise(a), f = a.createBiquadFilter(), g = a.createGain();
    f.type = 'bandpass'; f.frequency.setValueAtTime(freq, t); f.Q.value = q || 1;
    if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, t + dur);
    env(a, g, t, vol, dur); n.connect(f).connect(g).connect(a.destination); n.start(t); n.stop(t + dur + 0.05);
  }
  function sfx(kind) {
    if (!soundOn()) return;
    var a = actx(); if (!a || a.state !== 'running') return;
    if (kind === 'bump') { tone(a, 'sine', 140, 45, 0.22, 0.5); hiss(a, 500, 0.7, 0.12, 0.35); }
    else if (kind === 'smoke') { hiss(a, 3500, 0.8, 0.9, 0.18); for (var i = 0; i < 5; i++) hiss(a, 2000 + i * 600, 4, 0.04, 0.25, 0.1 + i * 0.13); }
    else if (kind === 'boom') { hiss(a, 1200, 0.5, 1.6, 0.9, 0, 70); tone(a, 'sine', 90, 28, 1.2, 0.9); tone(a, 'square', 60, 30, 0.3, 0.2); }
    else if (kind === 'fall') { tone(a, 'sine', 900, 160, 0.75, 0.25); [0.8, 1.0, 1.15].forEach(function (d) { tone(a, 'sine', 120, 50, 0.15, 0.45, d); }); }
    else if (kind === 'rescue') { tone(a, 'triangle', 400, 800, 0.18, 0.2); }
    else if (kind === 'repair') { [523, 659, 784, 1047].forEach(function (f, i) { tone(a, 'triangle', f, f, 0.16, 0.22, i * 0.09); }); }
    else if (kind === 'gulp') { tone(a, 'sine', 300, 1100, 0.2, 0.3); hiss(a, 1500, 2, 0.25, 0.2); }
    else if (kind === 'spin') { tone(a, 'sawtooth', 300, 900, 0.35, 0.08); tone(a, 'sawtooth', 900, 250, 0.4, 0.08, 0.35); }
    else if (kind === 'quake') { hiss(a, 90, 0.7, 2.0, 0.8); tone(a, 'sine', 45, 35, 2.0, 0.5); }
    else if (kind === 'clean') { tone(a, 'sine', 880, 1320, 0.12, 0.12); }
    else if (kind === 'coin') { tone(a, 'square', 988, 988, 0.08, 0.08); tone(a, 'square', 1319, 1319, 0.3, 0.08, 0.08); }
    else if (kind === 'clear') { [523, 659, 784, 1047, 784, 1047].forEach(function (f, i) { tone(a, 'triangle', f, f, i === 5 ? 0.5 : 0.14, 0.2, i * 0.12); }); }
    else if (kind === 'meow') { tone(a, 'triangle', 650, 950, 0.18, 0.18); tone(a, 'triangle', 950, 560, 0.3, 0.16, 0.18); }
  }
  function hum(on) {                                  // 吸塵模式的馬達聲
    var a = AC;
    if (!a || a.state !== 'running') return;
    on = on && soundOn();
    if (on && !humNode) {
      var n = noise(a), f = a.createBiquadFilter(), g = a.createGain();
      n.loop = true; f.type = 'bandpass'; f.frequency.value = 900; f.Q.value = 0.6; g.gain.value = 0.0001;
      n.connect(f).connect(g).connect(a.destination); n.start();
      g.gain.exponentialRampToValueAtTime(0.05, a.currentTime + 0.3);
      humNode = { n: n, g: g };
    } else if (!on && humNode) {
      var h = humNode; humNode = null;
      h.g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + 0.25); h.n.stop(a.currentTime + 0.3);
    }
  }

  // ---------- 場景設定 ----------
  // 家具：代號 → [疊起來的模型, 額外轉角]（Kenney 家具正面朝 +z；床要橫著靠牆）
  var FURN_MODELS = {
    sofa: [['loungeSofa']], tv: [['cabinetTelevision', 'televisionModern']], bookcase: [['bookcaseOpen']],
    armchair: [['loungeChair']], plant: [['pottedPlant']], lamp: [['lampRoundFloor']], speaker: [['speaker']],
    bed: [['bedSingle'], Math.PI / 2], wardrobe: [['bookcaseClosed']], nightstand: [['cabinetBedDrawerTable', 'plantSmall1']],
    fridge: [['kitchenFridge']], stove: [['kitchenStove']], sink: [['kitchenSink']],
    counter: [['kitchenCabinet', 'kitchenCoffeeMachine']], counter2: [['kitchenCabinetDrawer', 'kitchenMicrowave']],
    desk: [['desk', 'computerScreen']], shelf: [['bookcaseClosedWide']], bookcase2: [['bookcaseClosed']],
    toilet: [['toilet']], basin: [['bathroomSink']], washer: [['washer']], bathcab: [['bathroomCabinet', 'plantSmall2']],
    cabinet: [['kitchenCabinet']]
  };
  var FLOOR_STYLE = { '客廳': 'oak', '書房': 'walnut', '臥室': 'carpet', '廚房': 'tile', '浴室': 'smalltile' };
  var ROOM_PAINT = { '客廳': '#f2e8d7', '臥室': '#e4ddf1', '廚房': '#f4f4ef', '書房': '#dde8d6', '浴室': '#dcecf4' };
  var DIRS4 = [[0, -1], [1, 0], [0, 1], [-1, 0]];
  var WALL_H = 2.4, DOOR_H = 1.8, CUT_H = 0.3, R_BOT = 0.385, KS = 0.094;
  var FAIL_TXT = { exploded: '💥 笨笨爆炸了', owner_faint: '🤯 主人氣昏了', out_of_battery: '🪫 沒電了', time_up: '⏱️ 時間到' };

  async function make3d(L, host, assets) {
    var THREE = L.THREE;
    host.innerHTML = '';
    var renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);
    var CAMS = [['follow', '🎥 跟隨'], ['eye', '👀 笨笨視角'], ['top', '🗺️ 俯瞰'], ['cctv', '📹 監視器']];
    var bar = document.createElement('div'); bar.className = 'bd-3dbar';
    bar.innerHTML = CAMS.map(function (c) { return "<button class='bd-btn' data-cam='" + c[0] + "'>" + c[1] + '</button>'; }).join('');
    host.appendChild(bar);
    var over = document.createElement('div'); over.className = 'bd-3dover'; host.appendChild(over);
    var rec = document.createElement('div'); rec.className = 'bd-rec'; host.appendChild(rec);
    var hint = document.createElement('div'); hint.className = 'bd-3dhint'; host.appendChild(hint);

    var scene = new THREE.Scene();
    scene.background = new THREE.Color('#cfd9e2');
    scene.fog = new THREE.Fog('#cfd9e2', 18, 48);
    var pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new L.RoomEnvironment(), 0.04).texture;
    var camera = new THREE.PerspectiveCamera(62, 1.6, 0.03, 140);
    var hemi = new THREE.HemisphereLight(0xfff6ea, 0x8c7a66, 0.55); scene.add(hemi);
    var sun = new THREE.DirectionalLight(0xfff0d8, 1.3);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.03;
    scene.add(sun, sun.target);
    var ground = new THREE.Mesh(new THREE.PlaneGeometry(240, 240), new THREE.MeshStandardMaterial({ color: '#b9c7a3', roughness: 1 }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.03; ground.receiveShadow = true; scene.add(ground);

    // ---------- 程式產生的材質 ----------
    function rnd(seed) { var s = Math.floor(seed) % 2147483647; if (s <= 0) s += 2147483646; return function () { s = s * 16807 % 2147483647; return (s - 1) / 2147483646; }; }
    function canvasTex(draw, size, repeat, h) {
      var c = document.createElement('canvas'); c.width = size || 512; c.height = h || c.width; draw(c.getContext('2d'), c.width, c.height);
      var t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.anisotropy = 8; if (repeat) t.repeat.set(repeat, repeat); return t;
    }
    function shade(hex, k) {
      var c = new THREE.Color(hex); c.r = Math.min(1, c.r * k); c.g = Math.min(1, c.g * k); c.b = Math.min(1, c.b * k); return '#' + c.getHexString();
    }
    function planks(base, dark, seed) {
      return canvasTex(function (g, S) {
        var r = rnd(seed), rows = 6, h = S / rows;
        g.fillStyle = base; g.fillRect(0, 0, S, S);
        for (var i = 0; i < rows; i++) {
          var off = r() * S * 0.75;
          for (var k = -2; k < 2; k++) {
            var x0 = off + k * S * 0.75, tone = 0.88 + r() * 0.2;
            g.fillStyle = shade(base, tone); g.fillRect(x0, i * h, S * 0.75, h);
            g.strokeStyle = 'rgba(0,0,0,0.06)';
            for (var j = 0; j < 9; j++) { g.beginPath(); var yy = i * h + r() * h; g.moveTo(x0, yy); g.bezierCurveTo(x0 + S * 0.25, yy + (r() - 0.5) * 8, x0 + S * 0.5, yy + (r() - 0.5) * 8, x0 + S * 0.75, yy); g.stroke(); }
            g.fillStyle = dark; g.fillRect(x0, i * h, 2, h);
          }
          g.fillStyle = dark; g.fillRect(0, i * h, S, 2);
        }
      }, 512);
    }
    function tiles(a, b, n, grout, subway) {
      return canvasTex(function (g, S) {
        var c = S / n, r = rnd(n * 97);
        g.fillStyle = grout; g.fillRect(0, 0, S, S);
        var hh = subway ? c / 2 : c, nr = subway ? n * 2 : n;
        for (var j = 0; j < nr; j++) for (var i = -1; i < n; i++) {
          var off = subway && j % 2 ? c / 2 : 0;
          g.fillStyle = shade((i + j) % 2 ? a : b, 0.95 + r() * 0.08);
          g.fillRect(i * c + off + 2, j * hh + 2, c - 4, hh - 4);
        }
      }, 512);
    }
    function carpet(base) {
      return canvasTex(function (g, S) {
        var r = rnd(7); g.fillStyle = base; g.fillRect(0, 0, S, S);
        for (var i = 0; i < 9000; i++) { g.fillStyle = 'rgba(' + (r() < 0.5 ? '0,0,0' : '255,255,255') + ',' + (0.04 + r() * 0.05) + ')'; g.fillRect(r() * S, r() * S, 2, 2); }
      }, 256);
    }
    function plaster(seed) {
      return canvasTex(function (g, S) {
        var r = rnd(seed || 3); g.fillStyle = '#ffffff'; g.fillRect(0, 0, S, S);
        for (var i = 0; i < 5000; i++) { g.fillStyle = 'rgba(120,100,80,' + r() * 0.045 + ')'; g.fillRect(r() * S, r() * S, 3, 3); }
      }, 256);
    }
    function gradTex(stops, w, h, vertical) {
      return canvasTex(function (g, W, H) {
        var gr = vertical ? g.createLinearGradient(0, 0, 0, H) : g.createLinearGradient(0, 0, W, 0);
        stops.forEach(function (s) { gr.addColorStop(s[0], s[1]); }); g.fillStyle = gr; g.fillRect(0, 0, W, H);
      }, w || 64, null, h || 64);
    }
    var plasterTex = plaster(3);
    var FLOOR_MATS = {
      oak: new THREE.MeshStandardMaterial({ map: planks('#c89b6a', '#8a6440', 11), roughness: 0.5 }),
      walnut: new THREE.MeshStandardMaterial({ map: planks('#8b5e3c', '#5a3a22', 23), roughness: 0.45 }),
      carpet: new THREE.MeshStandardMaterial({ map: carpet('#b9aecb'), roughness: 1 }),
      tile: new THREE.MeshStandardMaterial({ map: tiles('#f2f2ee', '#dcdcd6', 4, '#b9b5ad'), roughness: 0.22 }),
      smalltile: new THREE.MeshStandardMaterial({ map: tiles('#cfe3ee', '#b8d2e0', 8, '#8fa9b8'), roughness: 0.18 })
    };
    var WALL_TEX = {
      '廚房': tiles('#fbfbf8', '#f1f0ea', 6, '#cfcabe', true),
      '浴室': tiles('#e3f0f6', '#d3e6ef', 8, '#a9c2cf')
    };
    var paintMats = {};
    function paint(room) {
      if (!paintMats[room]) {
        var tex = WALL_TEX[room];
        paintMats[room] = new THREE.MeshStandardMaterial(tex ? { map: tex, roughness: 0.3 } : { map: plasterTex, color: ROOM_PAINT[room] || ROOM_PAINT['客廳'], roughness: 0.92 });
      }
      return paintMats[room];
    }
    var extMat = new THREE.MeshStandardMaterial({ map: plasterTex, color: '#e6dccb', roughness: 0.95 });
    var cutMat = new THREE.MeshStandardMaterial({ color: '#4b4038', roughness: 0.9 });
    var trimMat = new THREE.MeshStandardMaterial({ color: '#fbf7ef', roughness: 0.5 });
    var woodTrim = new THREE.MeshStandardMaterial({ color: '#7b5a3c', roughness: 0.55 });
    var wainMat = new THREE.MeshStandardMaterial({ map: planks('#6f4a2f', '#4a2f1c', 31), roughness: 0.5 });
    var ceilMat = new THREE.MeshStandardMaterial({ map: plasterTex, color: '#fbfaf6', roughness: 1, emissive: '#efe9de', emissiveIntensity: 0.32 });
    var fogMat = new THREE.MeshBasicMaterial({ color: '#0d0f18' });
    var aoTex = gradTex([[0, 'rgba(0,0,0,0.42)'], [0.35, 'rgba(0,0,0,0.12)'], [1, 'rgba(0,0,0,0)']], 8, 64, true);
    aoTex.wrapS = aoTex.wrapT = THREE.ClampToEdgeWrapping;
    var aoMat = new THREE.MeshBasicMaterial({ map: aoTex, transparent: true, depthWrite: false });
    var skyTex = canvasTex(function (g, W, H) {
      var gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#7fb6e8'); gr.addColorStop(0.7, '#cfe6f7'); gr.addColorStop(1, '#e9f3e0');
      g.fillStyle = gr; g.fillRect(0, 0, W, H);
      g.fillStyle = 'rgba(255,255,255,0.85)';
      [[30, 30, 18], [52, 26, 14], [70, 34, 12], [100, 18, 10]].forEach(function (c) { g.beginPath(); g.arc(c[0], c[1], c[2], 0, 7); g.fill(); });
      g.fillStyle = '#8fb48a'; g.beginPath(); g.moveTo(0, H); g.quadraticCurveTo(W * 0.3, H * 0.62, W * 0.6, H * 0.85); g.quadraticCurveTo(W * 0.8, H * 0.7, W, H * 0.8); g.lineTo(W, H); g.fill();
    }, 128, null, 160);
    var glassMat = new THREE.MeshBasicMaterial({ map: skyTex, toneMapped: false });
    var curtainTex = canvasTex(function (g, W, H) { for (var i = 0; i < W; i += 8) { g.fillStyle = i % 16 ? '#d8c3a5' : '#c9b190'; g.fillRect(i, 0, 8, H); } }, 64);
    var curtainMat = new THREE.MeshStandardMaterial({ map: curtainTex, roughness: 1, side: THREE.DoubleSide });
    var ARTS = [0, 1, 2, 3].map(function (k) {
      return new THREE.MeshStandardMaterial({ roughness: 0.6, map: canvasTex(function (g, W, H) {
        var r = rnd(100 + k * 17), pal = [['#264653', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51'], ['#3d5a80', '#98c1d9', '#e0fbfc', '#ee6c4d'],
          ['#606c38', '#283618', '#fefae0', '#dda15e'], ['#ffcdb2', '#ffb4a2', '#e5989b', '#b5838d']][k];
        g.fillStyle = pal[2]; g.fillRect(0, 0, W, H);
        if (k === 2) {                                   // 風景畫
          g.fillStyle = '#a8dadc'; g.fillRect(0, 0, W, H * 0.55);
          g.fillStyle = pal[0]; g.beginPath(); g.moveTo(0, H * 0.6); g.lineTo(W * 0.35, H * 0.25); g.lineTo(W * 0.7, H * 0.6); g.fill();
          g.fillStyle = pal[1]; g.fillRect(0, H * 0.6, W, H * 0.4); g.fillStyle = '#ffd166'; g.beginPath(); g.arc(W * 0.78, H * 0.22, 9, 0, 7); g.fill();
        } else {
          for (var i = 0; i < 9; i++) {
            g.fillStyle = pal[Math.floor(r() * pal.length)];
            if (r() < 0.5) { g.beginPath(); g.arc(r() * W, r() * H, 6 + r() * 22, 0, 7); g.fill(); } else g.fillRect(r() * W, r() * H, 10 + r() * 40, 10 + r() * 40);
          }
        }
      }, 96, null, 128) });
    });

    // ---------- 合併幾何（地板、牆面各一個 mesh，畫起來快）----------
    function Quads() {
      var P = [], N = [], U = [], I = [], n = 0;
      return {
        quad: function (vs, nrm, uvs) {
          vs.forEach(function (v, i) { P.push(v[0], v[1], v[2]); N.push(nrm[0], nrm[1], nrm[2]); U.push(uvs[i][0], uvs[i][1]); });
          I.push(n, n + 1, n + 2, n, n + 2, n + 3); n += 4;
        },
        mesh: function (mat) {
          if (!n) return null;
          var g = new THREE.BufferGeometry();
          g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
          g.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2)); g.setIndex(I); g.computeBoundingSphere(); g.computeBoundingBox();
          var m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true; return m;
        }
      };
    }
    function hquad(Q, x, z, y, s) {           // 水平面（朝上）
      var x0 = x - s / 2, x1 = x + s / 2, z0 = z - s / 2, z1 = z + s / 2;
      Q.quad([[x0, y, z1], [x1, y, z1], [x1, y, z0], [x0, y, z0]], [0, 1, 0], [[x0 / 2, -z1 / 2], [x1 / 2, -z1 / 2], [x1 / 2, -z0 / 2], [x0 / 2, -z0 / 2]]);
    }
    function vquad(Q, cx, cz, nx, nz, y0, y1, uScale) {   // 垂直牆面：中心 (cx, cz)、法線 (nx, nz)、寬 1
      var tx = nz, tz = -nx, us = uScale || 1;
      var a = [cx - tx / 2, y0, cz - tz / 2], b = [cx + tx / 2, y0, cz + tz / 2], c = [cx + tx / 2, y1, cz + tz / 2], d = [cx - tx / 2, y1, cz - tz / 2];
      var u0 = (cx * tx + cz * tz - 0.5) * us, u1 = u0 + us;
      Q.quad([a, b, c, d], [nx, 0, nz], [[u0, y0 * us], [u1, y0 * us], [u1, y1 * us], [u0, y1 * us]]);
    }

    // ---------- 家具（Kenney OBJ）----------
    var objCache = {};
    function mtlColors(text) {
      var out = {}, cur = null;
      (text || '').split('\n').forEach(function (l) {
        var p = l.trim().split(/\s+/);
        if (p[0] === 'newmtl') cur = p[1];
        else if (p[0] === 'Kd' && cur) out[cur] = new THREE.Color(+p[1], +p[2], +p[3]);
      });
      return out;
    }
    function furniture(name) {
      if (!objCache[name]) {
        var a = assets.furniture[name]; if (!a) return null;
        var g = new L.OBJLoader().parse(a.obj), colors = mtlColors(a.mtl);
        g.traverse(function (o) {
          if (!o.isMesh) return;
          var ms = Array.isArray(o.material) ? o.material : [o.material];
          var nm = ms.map(function (m) {
            var col = colors[m.name] || new THREE.Color('#cccccc');
            var glass = /glass|screen/i.test(m.name), metal = /metal|chrome/i.test(m.name);
            return new THREE.MeshStandardMaterial({ color: col, roughness: glass ? 0.1 : (metal ? 0.3 : 0.7), metalness: metal ? 0.6 : 0 });
          });
          o.material = Array.isArray(o.material) ? nm : nm[0]; o.castShadow = o.receiveShadow = true;
        });
        g.scale.setScalar(KS);
        var box = new THREE.Box3().setFromObject(g), c = box.getCenter(new THREE.Vector3());
        var wrap = new THREE.Group(); g.position.set(-c.x, -box.min.y, -c.z); wrap.add(g);
        wrap.userData.size = box.getSize(new THREE.Vector3());
        objCache[name] = wrap;
      }
      var inst = objCache[name].clone(true);
      inst.traverse(function (o) { if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(function (m) { return m.clone(); }) : o.material.clone(); });
      inst.userData.size = objCache[name].userData.size;
      return inst;
    }
    // 一件家具：放大到填滿它佔的格子（寬 span 格、深約 0.9 格），背面貼牆、正面朝房間
    function placeFurniture(f) {
      var spec = FURN_MODELS[f[2]] || FURN_MODELS.cabinet, names = spec[0], turn = spec[1] || 0;
      var base = furniture(names[0]); if (!base) return null;
      var sz = base.userData.size, w = turn ? sz.z : sz.x, d = turn ? sz.x : sz.z;
      var s = Math.min(f[4] * 0.92 / w, 0.86 / d, 1.65 / sz.y, 2.6);
      var g = new THREE.Group(), inner = new THREE.Group(); g.add(inner);
      base.scale.setScalar(s); base.rotation.y = turn; inner.add(base);
      var yy = sz.y * s * 0.98;
      names.slice(1).forEach(function (n) { var t = furniture(n); if (!t) return; t.scale.setScalar(s * 0.9); t.position.y = yy; t.rotation.y = turn ? 0 : 0; inner.add(t); });
      var back = DIRS4[f[3]], fx = -back[0], fz = -back[1];
      var cx = f[0] + (f[4] === 2 ? f[5] / 2 : 0), cz = f[1] + (f[4] === 2 ? f[6] / 2 : 0);
      var depth = d * s;
      g.position.set(cx - fx * (0.5 - depth / 2 - 0.01), 0, cz - fz * (0.5 - depth / 2 - 0.01));
      g.rotation.y = Math.atan2(fx, fz);
      // 接地陰影（假的環境光遮蔽）
      var blob = new THREE.Mesh(new THREE.PlaneGeometry(f[4] * 0.98, 0.98), contactMat); blob.rotation.x = -Math.PI / 2;
      blob.position.set(f[0] + (f[4] === 2 ? f[5] / 2 : 0), 0.003, f[1] + (f[4] === 2 ? f[6] / 2 : 0));
      blob.rotation.z = -Math.atan2(fx, fz); staticGroup.add(blob);
      g.userData.furn = true;
      return g;
    }
    var contactTex = canvasTex(function (g, S) {
      var gr = g.createRadialGradient(S / 2, S / 2, S * 0.1, S / 2, S / 2, S * 0.5); gr.addColorStop(0, 'rgba(0,0,0,0.35)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(0, 0, S, S);
    }, 64);
    var contactMat = new THREE.MeshBasicMaterial({ map: contactTex, transparent: true, depthWrite: false });

    // ---------- 寵物（Quaternius GLB，有走路動畫）----------
    var petSrc = {}, gltf = new L.GLTFLoader();
    function b64buf(b64) { var bin = atob(b64), u = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u.buffer; }
    await Promise.all(['cat', 'dog'].map(function (k) {
      if (!assets.pets[k]) return null;
      return new Promise(function (ok) { gltf.parse(b64buf(assets.pets[k]), '', function (g) { petSrc[k] = g; ok(); }, function () { ok(); }); });
    }));
    function makePet(kind) {
      var src = petSrc[kind]; if (!src) return null;
      // 有骨架的模型要用「套上骨架後」的外框量大小（Box3.setFromObject 會量錯，貓會被縮到看不見）
      var model = L.clone(src.scene), box = new THREE.Box3(), tb = new THREE.Box3();
      model.updateMatrixWorld(true);
      model.traverse(function (o) { if (o.isSkinnedMesh) { o.skeleton.update(); o.computeBoundingBox(); box.union(tb.copy(o.boundingBox).applyMatrix4(o.matrixWorld)); } });
      if (box.isEmpty()) box.setFromObject(model);
      var size = box.getSize(new THREE.Vector3());
      var s = (kind === 'cat' ? 0.42 : 0.55) / Math.max(size.y, 0.001);
      model.scale.setScalar(s); model.position.y = -box.min.y * s;
      model.traverse(function (o) { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
      var g = new THREE.Group(); g.add(model);
      var blob = new THREE.Mesh(new THREE.PlaneGeometry(kind === 'cat' ? 0.55 : 0.75, kind === 'cat' ? 0.75 : 1.0), contactMat);
      blob.rotation.x = -Math.PI / 2; blob.position.y = 0.004; g.add(blob);
      var mixer = new THREE.AnimationMixer(model), acts = {};
      src.animations.forEach(function (c) { acts[c.name.split('|').pop().toLowerCase()] = mixer.clipAction(c); });
      var idle = acts.idle || acts.idle_eating || acts.eating || src.animations[0] && mixer.clipAction(src.animations[0]);
      var walk = acts.walk || acts.gallop || acts.run || idle;
      if (idle) idle.play();
      return { g: g, mixer: mixer, idle: idle, walk: walk, target: null, kind: kind, hop: 0 };
    }

    // ---------- 程式產生的小物件 ----------
    var M = function (c, r, extra) { return new THREE.MeshPhysicalMaterial(Object.assign({ color: c, roughness: r === undefined ? 0.5 : r }, extra || {})); };
    function mesh(geo, mat, y) { var m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; if (y !== undefined) m.position.y = y; return m; }
    function lego(seed) {
      var cols = ['#d62828', '#1d4ed8', '#f4c20d', '#16a34a'], g = new THREE.Group(), mat = M(cols[seed % 4], 0.25, { clearcoat: 0.6 });
      g.add(mesh(new THREE.BoxGeometry(0.18, 0.07, 0.09), mat, 0.035));
      for (var i = 0; i < 4; i++) { var st = mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.02, 12), mat, 0.08); st.position.x = -0.0675 + i * 0.045; g.add(st); }
      g.rotation.y = seed * 0.7; return g;
    }
    var sockTex = canvasTex(function (g, S) { for (var i = 0; i < 8; i++) { g.fillStyle = i % 2 ? '#f1f1f1' : '#2f6fd6'; g.fillRect(i * S / 8, 0, S / 8, S); } }, 128);
    function sock() {
      var curve = new THREE.CatmullRomCurve3([new THREE.Vector3(-0.18, 0.04, 0), new THREE.Vector3(0.05, 0.04, 0), new THREE.Vector3(0.12, 0.04, 0.1), new THREE.Vector3(0.14, 0.04, 0.2)]);
      var g = new THREE.Group(); g.add(mesh(new THREE.TubeGeometry(curve, 24, 0.045, 10), M('#ffffff', 0.9, { map: sockTex })));
      g.rotation.y = 0.6; return g;
    }
    function cable(seed) {
      var r = rnd(seed + 5), pts = [];
      for (var i = 0; i <= 6; i++) pts.push(new THREE.Vector3(-0.42 + i * 0.14, 0.015, (r() - 0.5) * 0.4));
      var g = new THREE.Group(); g.add(mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 60, 0.012, 8), M('#1b1b1b', 0.4)));
      var plug = mesh(new THREE.BoxGeometry(0.07, 0.04, 0.05), M('#f4f4f4', 0.3), 0.02); plug.position.x = 0.46; plug.position.z = pts[6].z; g.add(plug);
      return g;
    }
    function poop() {
      var g = new THREE.Group(), mat = M('#5b3a1e', 0.35, { clearcoat: 0.8 });
      [[0.1, 0.035, 0.03], [0.075, 0.03, 0.085], [0.05, 0.025, 0.13]].forEach(function (p) {
        var t = mesh(new THREE.TorusGeometry(p[0], p[1], 10, 24), mat, p[2]); t.rotation.x = Math.PI / 2; g.add(t);
      });
      g.add(mesh(new THREE.ConeGeometry(0.035, 0.07, 12), mat, 0.18)); return g;
    }
    function puddle() {
      var m = new THREE.Mesh(new THREE.CircleGeometry(0.38, 40), M('#8fc8ea', 0.03, { transparent: true, opacity: 0.6, clearcoat: 1, metalness: 0.1 }));
      m.rotation.x = -Math.PI / 2; m.scale.set(1, 0.7, 1); m.position.y = 0.006; m.receiveShadow = true; return m;
    }
    var holeTex = canvasTex(function (g, S) {
      var r = rnd(9), c = S / 2;
      g.fillStyle = 'rgba(0,0,0,0)'; g.clearRect(0, 0, S, S);
      g.strokeStyle = 'rgba(40,25,15,0.8)'; g.lineWidth = 3;
      for (var k = 0; k < 9; k++) { var a = r() * 6.28; g.beginPath(); g.moveTo(c + Math.cos(a) * S * 0.33, c + Math.sin(a) * S * 0.33); g.lineTo(c + Math.cos(a + 0.2) * S * 0.47, c + Math.sin(a + 0.2) * S * 0.47); g.stroke(); }
      g.beginPath();
      for (var i = 0; i <= 24; i++) { var t = i / 24 * 6.283, rr = S * (0.32 + r() * 0.06); g[i ? 'lineTo' : 'moveTo'](c + Math.cos(t) * rr, c + Math.sin(t) * rr); }
      var gr = g.createRadialGradient(c, c, 2, c, c, S * 0.38); gr.addColorStop(0, '#000'); gr.addColorStop(0.75, '#0b0705'); gr.addColorStop(1, '#3a2716');
      g.fillStyle = gr; g.fill(); g.strokeStyle = '#5c4027'; g.lineWidth = 4; g.stroke();
    }, 256);
    function hole(seed) {
      var g = new THREE.Group(), r = rnd(seed + 3);
      var d = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.0), new THREE.MeshBasicMaterial({ map: holeTex, transparent: true, depthWrite: false }));
      d.rotation.x = -Math.PI / 2; d.position.y = 0.005; g.add(d);
      for (var i = 0; i < 6; i++) {                     // 破掉的地板碎片
        var a = i / 6 * 6.28 + r(), ch = mesh(new THREE.BoxGeometry(0.1 + r() * 0.08, 0.025, 0.06 + r() * 0.05), M('#9c7a55', 0.8));
        ch.position.set(Math.cos(a) * 0.43, 0.012, Math.sin(a) * 0.43); ch.rotation.set(r() * 0.4, a, r() * 0.4); g.add(ch);
      }
      var cone = new THREE.Group(), om = M('#ff6b1a', 0.5);                // 三角錐
      cone.add(mesh(new THREE.BoxGeometry(0.2, 0.02, 0.2), om, 0.01));
      cone.add(mesh(new THREE.ConeGeometry(0.075, 0.3, 20), om, 0.17));
      var band = mesh(new THREE.CylinderGeometry(0.047, 0.058, 0.05, 20), M('#ffffff', 0.4), 0.17); cone.add(band);
      cone.position.set(0.4, 0, -0.4); g.add(cone);
      return g;
    }
    function banana() {
      var g = new THREE.Group(), yel = M('#f6d743', 0.45), brn = M('#6b4b1f', 0.7);
      for (var i = 0; i < 4; i++) {
        var p = new THREE.Group(), leaf = mesh(new THREE.SphereGeometry(0.09, 14, 8), yel); leaf.scale.set(0.5, 0.18, 1.5); leaf.position.z = 0.12; p.add(leaf);
        var tip = mesh(new THREE.SphereGeometry(0.02, 8, 6), brn); tip.position.z = 0.25; p.add(tip);
        p.rotation.y = i * Math.PI / 2 + 0.3; p.position.y = 0.02; p.rotation.x = -0.15; g.add(p);
      }
      g.add(mesh(new THREE.CylinderGeometry(0.03, 0.04, 0.08, 10), yel, 0.05));
      return g;
    }
    function toolbox() {
      var g = new THREE.Group(), body = new THREE.Group();
      body.add(mesh(new THREE.BoxGeometry(0.34, 0.15, 0.18), M('#d62828', 0.35, { clearcoat: 0.8 }), 0.075));
      body.add(mesh(new THREE.BoxGeometry(0.35, 0.02, 0.19), M('#9b1c1c', 0.4), 0.15));
      var h = mesh(new THREE.TorusGeometry(0.07, 0.012, 8, 20, Math.PI), M('#222', 0.3, { metalness: 0.6 }), 0.16); body.add(h);
      [-0.1, 0.1].forEach(function (x) { var l = mesh(new THREE.BoxGeometry(0.03, 0.04, 0.01), M('#d0d0d0', 0.2, { metalness: 0.9 }), 0.13); l.position.set(x, 0.13, 0.095); body.add(l); });
      var ring = new THREE.Mesh(new THREE.RingGeometry(0.28, 0.36, 40), new THREE.MeshBasicMaterial({ color: '#7CFC9A', transparent: true, opacity: 0.6, toneMapped: false, side: THREE.DoubleSide }));
      ring.rotation.x = -Math.PI / 2; ring.position.y = 0.01; g.add(ring, body);
      g.userData.anim = function (t) { body.position.y = 0.08 + Math.sin(t * 3) * 0.04; body.rotation.y = t * 1.5; ring.material.opacity = 0.35 + Math.sin(t * 4) * 0.25; };
      return g;
    }
    function roach() {
      var g = new THREE.Group(), shell = M('#4a2511', 0.25, { clearcoat: 1 }), legM = M('#2b1508', 0.6);
      var b = mesh(new THREE.SphereGeometry(0.06, 14, 10), shell, 0.035); b.scale.set(0.75, 0.45, 1.5); g.add(b);
      var hd = mesh(new THREE.SphereGeometry(0.028, 10, 8), legM, 0.03); hd.position.z = -0.095; g.add(hd);
      var legs = [];
      for (var i = 0; i < 6; i++) {
        var side = i < 3 ? 1 : -1, leg = mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.09, 4), legM);
        leg.position.set(side * 0.05, 0.02, -0.04 + (i % 3) * 0.045); leg.rotation.z = side * 1.1; g.add(leg); legs.push(leg);
      }
      [-1, 1].forEach(function (s) { var an = mesh(new THREE.CylinderGeometry(0.002, 0.002, 0.16, 4), legM); an.position.set(s * 0.025, 0.05, -0.17); an.rotation.set(1.2, 0, s * 0.35); g.add(an); });
      g.userData.anim = function (t) { legs.forEach(function (l, i) { l.rotation.x = Math.sin(t * 30 + i) * 0.5; }); };
      return g;
    }
    var dirtMat = M('#6b4f35', 0.95), crumbGeo = new THREE.DodecahedronGeometry(0.035, 0);
    var smudge = canvasTex(function (g, S) { var gr = g.createRadialGradient(S / 2, S / 2, 4, S / 2, S / 2, S / 2); gr.addColorStop(0, 'rgba(90,65,40,.55)'); gr.addColorStop(1, 'rgba(90,65,40,0)'); g.fillStyle = gr; g.fillRect(0, 0, S, S); }, 128);
    var smudgeMat = new THREE.MeshStandardMaterial({ map: smudge, transparent: true, depthWrite: false });
    function dirt(seed) {
      var r = rnd(seed + 1), g = new THREE.Group();
      var sm = new THREE.Mesh(new THREE.PlaneGeometry(0.75, 0.75), smudgeMat);
      sm.rotation.x = -Math.PI / 2; sm.position.y = 0.004; g.add(sm);
      for (var i = 0; i < 9; i++) { var c = mesh(crumbGeo, dirtMat); c.scale.setScalar(0.5 + r() * 0.9); c.position.set((r() - 0.5) * 0.45, 0.015, (r() - 0.5) * 0.45); c.rotation.set(r() * 3, r() * 3, 0); g.add(c); }
      return g;
    }
    function dock() {
      var g = new THREE.Group(), body = M('#e9ecef', 0.35, { clearcoat: 0.5 });
      g.add(mesh(new THREE.BoxGeometry(0.5, 0.025, 0.32), M('#cfd4d9', 0.6), 0.012));
      var back = mesh(new THREE.BoxGeometry(0.46, 0.2, 0.1), body, 0.11); back.position.z = 0.13; g.add(back);
      var led = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.015, 0.01), new THREE.MeshStandardMaterial({ color: '#22c55e', emissive: '#22c55e', emissiveIntensity: 2 }));
      led.position.set(0, 0.17, 0.077); g.add(led);
      [-0.08, 0.08].forEach(function (x) { var c = mesh(new THREE.BoxGeometry(0.05, 0.01, 0.08), M('#c0c4c8', 0.2, { metalness: 0.9 }), 0.03); c.position.set(x, 0.03, 0.02); g.add(c); });
      return g;
    }

    // ---------- 笨笨（掃地機器人）：本地座標 −z＝前方。body 裡的零件爆炸時會飛出去 ----------
    var robot = new THREE.Group(), body = new THREE.Group(); robot.add(body);
    var shellProfile = [new THREE.Vector2(0, 0.02), new THREE.Vector2(0.33, 0.02), new THREE.Vector2(0.36, 0.05), new THREE.Vector2(0.365, 0.1),
                        new THREE.Vector2(0.35, 0.135), new THREE.Vector2(0.32, 0.15), new THREE.Vector2(0, 0.15)];
    var shellMat = M('#24282f', 0.35, { clearcoat: 1, clearcoatRoughness: 0.2 });
    var shell = mesh(new THREE.LatheGeometry(shellProfile, 64), shellMat); body.add(shell);
    var lidMat = M('#98c1d9', 0.25, { clearcoat: 1, clearcoatRoughness: 0.1 });
    var lid = mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.012, 64), lidMat, 0.156); body.add(lid);
    var ringMat = new THREE.MeshStandardMaterial({ color: '#38bdf8', emissive: '#38bdf8', emissiveIntensity: 1.6 });
    var ring = new THREE.Mesh(new THREE.TorusGeometry(0.305, 0.006, 8, 96), ringMat); ring.rotation.x = Math.PI / 2; ring.position.y = 0.158; body.add(ring);
    var lidar = new THREE.Group(); lidar.position.set(0, 0.185, 0.14);
    lidar.add(mesh(new THREE.CylinderGeometry(0.065, 0.07, 0.05, 32), M('#1f2329', 0.3, { clearcoat: 1 })));
    var lens = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.014, 0.02), new THREE.MeshBasicMaterial({ color: '#ff3b3b', toneMapped: false })); lens.position.set(0, 0.005, -0.066); lidar.add(lens);
    var band = new THREE.Mesh(new THREE.CylinderGeometry(0.071, 0.071, 0.012, 32), M('#0f172a', 0.1, { metalness: 0.5 })); band.position.y = 0.005; lidar.add(band);
    body.add(lidar);
    var bumper = mesh(new THREE.TorusGeometry(0.362, 0.022, 10, 48, Math.PI * 0.9), M('#3a3f47', 0.6), 0.075);
    bumper.rotation.x = Math.PI / 2; bumper.rotation.z = Math.PI * 1.05; body.add(bumper);
    var arrowShape = new THREE.Shape(); arrowShape.moveTo(0, -0.2); arrowShape.lineTo(0.09, -0.06); arrowShape.lineTo(0.035, -0.06);
    arrowShape.lineTo(0.035, 0.0); arrowShape.lineTo(-0.035, 0.0); arrowShape.lineTo(-0.035, -0.06); arrowShape.lineTo(-0.09, -0.06); arrowShape.lineTo(0, -0.2);
    var arrow = new THREE.Mesh(new THREE.ShapeGeometry(arrowShape), new THREE.MeshStandardMaterial({ color: '#ffb703', emissive: '#a86b00', emissiveIntensity: 0.6 }));
    arrow.rotation.x = -Math.PI / 2; arrow.position.set(0, 0.164, -0.07); arrow.scale.setScalar(0.62); body.add(arrow);
    // LED 臉（表情跟著心情、受損狀態變）
    var faceCanvas = document.createElement('canvas'); faceCanvas.width = 128; faceCanvas.height = 64;
    var faceTex = new THREE.CanvasTexture(faceCanvas); faceTex.colorSpace = THREE.SRGBColorSpace;
    var face = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.13), new THREE.MeshBasicMaterial({ map: faceTex, toneMapped: false }));
    face.rotation.x = -Math.PI / 2; face.position.set(0, 0.1635, -0.005); body.add(face);
    var faceKey = '';
    function drawFace(key) {
      if (key === faceKey) return; faceKey = key;
      var g = faceCanvas.getContext('2d'), W = 128, H = 64, col = key === 'hurt' || key === 'dead' ? '#ff6b6b' : '#5ef2ff';
      g.fillStyle = '#0b1220'; g.fillRect(0, 0, W, H);
      g.fillStyle = col; g.strokeStyle = col; g.lineWidth = 7; g.lineCap = 'round';
      function eye(x, kind) {
        g.beginPath();
        if (kind === 'happy') { g.arc(x, 40, 14, Math.PI * 1.1, Math.PI * 1.9); g.stroke(); }
        else if (kind === 'x') { g.moveTo(x - 11, 20); g.lineTo(x + 11, 42); g.moveTo(x + 11, 20); g.lineTo(x - 11, 42); g.stroke(); }
        else if (kind === 'angry') { g.moveTo(x - 13, 22 + (x < 64 ? -4 : 4)); g.lineTo(x + 13, 22 + (x < 64 ? 4 : -4)); g.stroke(); g.fillRect(x - 9, 30, 18, 14); }
        else if (kind === 'sad') { g.fillRect(x - 9, 30, 18, 14); g.moveTo(x - 13, 24 + (x < 64 ? 4 : -4)); g.lineTo(x + 13, 24 + (x < 64 ? -4 : 4)); g.stroke(); }
        else if (kind === 'wide') { g.arc(x, 32, 13, 0, 7); g.fill(); g.fillStyle = '#0b1220'; g.beginPath(); g.arc(x, 32, 5, 0, 7); g.fill(); g.fillStyle = col; }
        else if (kind === 'cool') { g.fillRect(x - 15, 24, 30, 12); }
        else if (kind === 'dot') { g.arc(x, 34, 5, 0, 7); g.fill(); }
        else if (kind === 'swirl') { for (var a = 0; a < 12; a += 0.4) g.lineTo(x + Math.cos(a) * a * 1.1, 32 + Math.sin(a) * a * 1.1); g.lineWidth = 3; g.stroke(); g.lineWidth = 7; }
        else { g.roundRect ? g.roundRect(x - 10, 18, 20, 28, 8) : g.rect(x - 10, 18, 20, 28); g.fill(); }
      }
      var k = { happy: 'happy', angry: 'angry', sad: 'sad', scared: 'wide', cool: 'cool', think: 'dot', hurt: 'swirl', dead: 'x' }[key] || 'n';
      eye(40, k); eye(88, k);
      if (key === 'think') { g.beginPath(); g.arc(64, 34, 5, 0, 7); g.fill(); }
      if (key === 'love') { g.font = '30px sans-serif'; g.textAlign = 'center'; g.fillText('♥', 40, 44); g.fillText('♥', 88, 44); }
      faceTex.needsUpdate = true;
    }
    drawFace('n');
    var brushes = [];
    [-0.2, 0.2].forEach(function (x) {
      var b = new THREE.Group(); b.position.set(x, 0.012, -0.24);
      for (var i = 0; i < 3; i++) { var br = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.004, 0.008), M('#9ca3af', 0.8)); br.rotation.y = i * Math.PI / 3 * 2; b.add(br); }
      body.add(b); brushes.push(b);
    });
    [-1, 1].forEach(function (s) { var w = mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.04, 20), M('#111', 0.8), 0.06); w.rotation.z = Math.PI / 2; w.position.x = s * 0.28; body.add(w); });
    var headlight = new THREE.SpotLight(0xfff3d6, 0, 6, 0.6, 0.5, 1.2); headlight.position.set(0, 0.2, -0.2);
    headlight.target.position.set(0, 0, -2); robot.add(headlight, headlight.target);
    scene.add(robot);
    var PARTS = body.children.slice();
    var robotBlob = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.0), new THREE.MeshBasicMaterial({ map: contactTex, transparent: true, depthWrite: false, opacity: 0.9 }));
    robotBlob.rotation.x = -Math.PI / 2; robotBlob.position.y = 0.0035; robot.add(robotBlob);
    PARTS.forEach(function (p) { p.userData.home = { pos: p.position.clone(), quat: p.quaternion.clone() }; });
    function spriteTex(text) {
      return canvasTex(function (g, S) {
        g.fillStyle = '#222'; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.font = "bold 80px 'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji','PingFang TC',sans-serif"; g.fillText(text, S / 2, S / 2 + 4);
      }, 128);
    }
    var texCache = {};
    function sprite(text, scale) {
      texCache[text] = texCache[text] || spriteTex(text);
      var s = new THREE.Sprite(new THREE.SpriteMaterial({ map: texCache[text], depthWrite: false })); s.scale.set(scale, scale, 1); return s;
    }
    var head = sprite(' ', 0.36); head.position.y = 0.72; robot.add(head);
    var riderCat = null;

    // ---------- 粒子（煙、火花、灰塵）----------
    var softTex = canvasTex(function (g, S) {
      var gr = g.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.5, 'rgba(255,255,255,0.45)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(0, 0, S, S);
    }, 64);
    var parts = [];
    function emit(o) {          // o: pos, vel, color, size0, size1, life, alpha, add(=發光), grav, drag
      var m = new THREE.SpriteMaterial({ map: softTex, color: o.color || '#888', transparent: true, depthWrite: false, opacity: o.alpha || 0.6,
                                         blending: o.add ? THREE.AdditiveBlending : THREE.NormalBlending, toneMapped: !o.add });
      var s = new THREE.Sprite(m); s.position.copy(o.pos); s.scale.setScalar(o.size0 || 0.2);
      s.userData = { v: o.vel || new THREE.Vector3(), life: 0, max: o.life || 1.5, s0: o.size0 || 0.2, s1: o.size1 || 0.6, a: o.alpha || 0.6, g: o.grav || 0, drag: o.drag || 0 };
      scene.add(s); parts.push(s);
      if (parts.length > 420) { var old = parts.shift(); scene.remove(old); old.material.dispose(); }
    }
    function V(x, y, z) { return new THREE.Vector3(x, y, z); }
    function rr(a) { return (Math.random() - 0.5) * 2 * a; }
    function smokePuff(p, dark, big) {
      emit({ pos: p.clone().add(V(rr(0.08), 0, rr(0.08))), vel: V(rr(0.08), 0.35 + Math.random() * 0.25, rr(0.08)), color: dark ? '#2b2b2b' : '#6b6b6b',
             size0: big ? 0.3 : 0.12, size1: big ? 1.4 : 0.7, life: big ? 2.8 : 2.0, alpha: dark ? 0.7 : 0.5, drag: 0.4 });
    }
    function sparks(p, n, col, speed) {
      for (var i = 0; i < n; i++) emit({ pos: p.clone(), vel: V(rr(1), Math.random() * 1.2 + 0.3, rr(1)).multiplyScalar(speed || 1.6), color: col || '#ffd27a',
                                         size0: 0.05, size1: 0.01, life: 0.5 + Math.random() * 0.4, alpha: 1, add: true, grav: 4 });
    }
    function dust(p, n) {
      for (var i = 0; i < n; i++) emit({ pos: p.clone().add(V(rr(0.15), 0.03, rr(0.15))), vel: V(rr(0.5), Math.random() * 0.3, rr(0.5)), color: '#c8b8a0',
                                         size0: 0.08, size1: 0.35, life: 0.8, alpha: 0.5, drag: 1.5 });
    }

    // ---------- 狀態 ----------
    var staticGroup = new THREE.Group(), wallGroup = new THREE.Group(), decor = new THREE.Group(), ceilGroup = new THREE.Group();
    var dynGroup = new THREE.Group(), roomGroup = new THREE.Group(), fxGroup = new THREE.Group();
    wallGroup.add(decor); scene.add(staticGroup, wallGroup, ceilGroup, dynGroup, roomGroup, fxGroup);
    var staticKey = '', fogBoxes = {}, wallMeshes = [], furnGroups = [], lamps = [], fans = [], pets = { cat: [], dog: [], roach: [] };
    var dynObjs = {}, prevDirt = {}, roomBox = {}, roomAt = {}, house = { w: 1, h: 1 }, forbKey = '';
    var target = { x: 0, z: 0, f: 0 }, first = true, driving = false, vac = false, dmg = 0, wrecked = false, motion = Motion();
    var cam = 'follow', yaw = 0.6, dist = 0, cut = 1, center = new THREE.Vector3(), camPos = new THREE.Vector3(), camLook = new THREE.Vector3();
    var dark = false, thinking = false, gid = null, lastFx = 0, overState = '';
    var bump = { off: new THREE.Vector3(), from: new THREE.Vector3(), to: new THREE.Vector3(), t0: 0, dur: 1, pending: null, at: null, squash: 0 };
    var spin = { t0: 0, dur: 0, amt: 0 }, shake = { amp: 0, t0: 0, dur: 1 }, override = null, tweens = [], debris = [], quakeT = 0;
    var trail = null, collidables = [], raycaster = new THREE.Raycaster();

    function addTween(dur, fn, done) { tweens.push({ t0: performance.now(), dur: dur * 1000, fn: fn, done: done }); }
    function later(sec, fn) { addTween(sec, function () {}, fn); }
    function shakeCam(amp, dur) { if (amp >= shake.amp * Math.max(0, 1 - (performance.now() - shake.t0) / (shake.dur * 1000))) shake = { amp: amp, t0: performance.now(), dur: dur }; }

    function buildStatic(st) {
      [staticGroup, decor, ceilGroup].forEach(function (g) { while (g.children.length) g.remove(g.children[0]); });
      wallGroup.children.slice().forEach(function (c) { if (c !== decor) wallGroup.remove(c); });
      fogBoxes = {}; wallMeshes = []; furnGroups = []; lamps = []; fans = []; roomBox = {}; roomAt = {};
      house = { w: st.w, h: st.h };
      var tile = {}, wall = {};
      st.tiles.forEach(function (t) { tile[t[0] + ',' + t[1]] = t[4]; roomAt[t[0] + ',' + t[1]] = t[4]; });
      st.walls.forEach(function (w) { wall[w[0] + ',' + w[1]] = 1; });
      st.tiles.forEach(function (t) {
        var b = roomBox[t[4]] || (roomBox[t[4]] = { x0: t[0], x1: t[0], y0: t[1], y1: t[1], n: 0 });
        b.x0 = Math.min(b.x0, t[0]); b.x1 = Math.max(b.x1, t[0]); b.y0 = Math.min(b.y0, t[1]); b.y1 = Math.max(b.y1, t[1]); b.n++;
      });
      // 地板：每種材質合併成一個 mesh
      var floors = {};
      st.tiles.forEach(function (t) { var s = FLOOR_STYLE[t[4]] || 'oak'; hquad(floors[s] || (floors[s] = Quads()), t[0], t[1], 0, 1); });
      Object.keys(floors).forEach(function (s) { var m = floors[s].mesh(FLOOR_MATS[s]); m.castShadow = false; staticGroup.add(m); });
      // 牆：牆面就在格子邊界上（撞牆時笨笨真的貼上去）；朝房間的面用該房間的油漆／磁磚，頂面是深色剖面
      var faces = {}, ext = Quads(), top = Quads(), ao = Quads(), wain = Quads(), trims = [];
      function face(room) { return faces[room] || (faces[room] = Quads()); }
      var cols = {}, rows = {};
      st.walls.forEach(function (w) { cols[w[0]] = (cols[w[0]] || 0) + 1; rows[w[1]] = (rows[w[1]] || 0) + 1; });
      st.walls.forEach(function (w) {
        var x = w[0], y = w[1];
        hquad(top, x, y, WALL_H, 1);
        DIRS4.forEach(function (d) {
          var nk = (x + d[0]) + ',' + (y + d[1]);
          if (wall[nk]) return;
          var cx = x + d[0] / 2, cz = y + d[1] / 2, room = tile[nk];
          if (room === undefined) { vquad(ext, cx, cz, d[0], d[1], 0, WALL_H); return; }
          vquad(face(room), cx, cz, d[0], d[1], 0, WALL_H);
          if (room === '書房') vquad(wain, cx + d[0] * 0.012, cz + d[1] * 0.012, d[0], d[1], 0, 0.75);
          // 牆角的陰影（假 AO）：沿著牆在地板上畫一條漸層
          var ax = x + d[0] * 0.5 + d[0] * 0.22, az = y + d[1] * 0.5 + d[1] * 0.22, tx = d[1], tz = -d[0];
          var p0 = [ax - tx / 2 - d[0] * 0.22, 0.004, az - tz / 2 - d[1] * 0.22], p1 = [ax + tx / 2 - d[0] * 0.22, 0.004, az + tz / 2 - d[1] * 0.22];
          var p2 = [ax + tx / 2 + d[0] * 0.22, 0.004, az + tz / 2 + d[1] * 0.22], p3 = [ax - tx / 2 + d[0] * 0.22, 0.004, az - tz / 2 + d[1] * 0.22];
          var up = (p1[0] - p0[0]) * (p3[2] - p0[2]) - (p1[2] - p0[2]) * (p3[0] - p0[0]) < 0;     // 確保朝上
          ao.quad(up ? [p0, p1, p2, p3] : [p1, p0, p3, p2], [0, 1, 0], up ? [[0, 1], [1, 1], [1, 0], [0, 0]] : [[1, 1], [0, 1], [0, 0], [1, 0]]);
          // 踢腳板、天花板線板
          var tl = Math.atan2(d[0], d[1]);
          trims.push([cx + d[0] * 0.012, 0.045, cz + d[1] * 0.012, tl, 0], [cx + d[0] * 0.02, WALL_H - 0.04, cz + d[1] * 0.02, tl, 1]);
        });
      });
      Object.keys(faces).forEach(function (room) { var m = faces[room].mesh(paint(room)); wallGroup.add(m); wallMeshes.push(m); });
      // 踢腳板、天花板線板：幾百段同樣的長條 → 用 InstancedMesh 一次畫完
      [baseGeo, crownGeo].forEach(function (geo, kind) {
        var list = trims.filter(function (t) { return t[4] === kind; }), im = new THREE.InstancedMesh(geo, trimMat, list.length || 1), o3 = new THREE.Object3D();
        list.forEach(function (t, i) { o3.position.set(t[0], t[1], t[2]); o3.rotation.set(0, t[3], 0); o3.updateMatrix(); im.setMatrixAt(i, o3.matrix); });
        im.count = list.length; im.instanceMatrix.needsUpdate = true; im.receiveShadow = true; decor.add(im);
      });
      [[ext, extMat], [top, cutMat], [wain, wainMat]].forEach(function (p) { var m = p[0].mesh(p[1]); if (m) { wallGroup.add(m); if (p[1] !== cutMat) wallMeshes.push(m); } });
      var aoM = ao.mesh(aoMat); if (aoM) { aoM.castShadow = aoM.receiveShadow = false; aoM.renderOrder = 1; staticGroup.add(aoM); }
      // 門口：在牆線上的地板格 → 上面加門楣（看起來像牆上開的門）
      var lint = Quads(), lintFaces = {};
      st.tiles.forEach(function (t) {
        var x = t[0], y = t[1], inCol = cols[x] * 2 >= st.h, inRow = rows[y] * 2 >= st.w;
        if (!inCol && !inRow) return;
        lint.quad([[x - 0.5, DOOR_H, y - 0.5], [x + 0.5, DOOR_H, y - 0.5], [x + 0.5, DOOR_H, y + 0.5], [x - 0.5, DOOR_H, y + 0.5]], [0, -1, 0], [[0, 0], [1, 0], [1, 1], [0, 1]]);
        DIRS4.forEach(function (d) {
          var nk = (x + d[0]) + ',' + (y + d[1]);
          if (wall[nk] || tile[nk] === undefined) return;
          var nIn = inCol ? (cols[x + d[0]] || 0) * 2 >= st.h && d[0] === 0 : (rows[y + d[1]] || 0) * 2 >= st.w && d[1] === 0;
          if (nIn) return;                                   // 同一個門口的另一格
          var f = lintFaces[tile[nk]] || (lintFaces[tile[nk]] = Quads());
          vquad(f, x + d[0] / 2, y + d[1] / 2, d[0], d[1], DOOR_H, WALL_H);
        });
      });
      var lm = lint.mesh(woodTrim); if (lm) decor.add(lm);
      Object.keys(lintFaces).forEach(function (room) { var m = lintFaces[room].mesh(paint(room)); if (m) decor.add(m); });
      // 窗戶（外牆上，每隔幾格一扇）、掛畫
      var r = rnd(st.w * 131 + st.h * 17 + st.level.length), furnFace = {};
      (st.furniture || []).forEach(function (f) {
        [[f[0], f[1]], [f[0] + (f[4] === 2 ? f[5] : 0), f[1] + (f[4] === 2 ? f[6] : 0)]].forEach(function (c) {
          furnFace[(c[0] + DIRS4[f[3]][0]) + ',' + (c[1] + DIRS4[f[3]][1]) + ',' + ((f[3] + 2) % 4)] = 1;
        });
      });
      st.walls.forEach(function (w) {
        var x = w[0], y = w[1];
        DIRS4.forEach(function (d, i) {
          var nk = (x + d[0]) + ',' + (y + d[1]), room = tile[nk];
          if (room === undefined || wall[nk]) return;
          var outside = !tile[(x - d[0]) + ',' + (y - d[1])] && !wall[(x - d[0]) + ',' + (y - d[1])];
          var along = [[d[1], -d[0]], [-d[1], d[0]]], straight = along.every(function (a) { return wall[(x + a[0]) + ',' + (y + a[1])]; });
          if (!straight || furnFace[x + ',' + y + ',' + i]) return;
          var fx = x + d[0] * 0.5, fz = y + d[1] * 0.5, rot = Math.atan2(d[0], d[1]);
          if (outside && (x * 7 + y * 3) % 5 === 0) { decor.add(windowAt(fx, fz, rot, room === '浴室')); return; }
          if (r() < 0.14) decor.add(artAt(fx, fz, rot, Math.floor(r() * 4), 1.35 + r() * 0.25));
        });
      });
      // 天花板（從下面看得到、從上面看是透明的）＋吸頂燈＋客廳吊扇
      var ceil = Quads();
      st.tiles.forEach(function (t) { var x = t[0], y = t[1]; ceil.quad([[x - 0.5, WALL_H, y - 0.5], [x + 0.5, WALL_H, y - 0.5], [x + 0.5, WALL_H, y + 0.5], [x - 0.5, WALL_H, y + 0.5]], [0, -1, 0], [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]]); });
      var cm = ceil.mesh(ceilMat); cm.castShadow = false; ceilGroup.add(cm);
      var nLight = 0;
      Object.keys(roomBox).forEach(function (name) {
        var b = roomBox[name], spots = [], nx = Math.max(1, Math.round((b.x1 - b.x0 + 1) / 7)), ny = Math.max(1, Math.round((b.y1 - b.y0 + 1) / 7));
        for (var i = 0; i < nx; i++) for (var j = 0; j < ny; j++) {
          var lx = Math.round(b.x0 + (i + 0.5) * (b.x1 - b.x0 + 1) / nx - 0.5), ly = Math.round(b.y0 + (j + 0.5) * (b.y1 - b.y0 + 1) / ny - 0.5);
          if (tile[lx + ',' + ly] === name) spots.push([lx, ly]);
        }
        spots.forEach(function (s, k) {
          var withFan = name === '客廳' && k === 0;
          var lamp = lampAt(s[0], s[1], withFan, nLight < 9); if (lamp.userData.light) nLight++;
          ceilGroup.add(lamp); lamps.push(lamp);
        });
        // 每個房間中間一張地毯
        var cx = Math.round((b.x0 + b.x1) / 2), cy = Math.round((b.y0 + b.y1) / 2);
        if (tile[cx + ',' + cy] === name && b.n > 12) {
          var rug = furniture(name === '臥室' ? 'rugRound' : 'rugRectangle');
          if (rug) { rug.scale.multiplyScalar(1.6); rug.position.set(cx, 0.003, cy); rug.traverse(function (o) { if (o.isMesh) o.castShadow = false; }); staticGroup.add(rug); }
        }
      });
      // 家具（真的障礙物）
      (st.furniture || []).forEach(function (f) { var g = placeFurniture(f); if (g) { staticGroup.add(g); furnGroups.push(g); } });
      if (st.home) { var dk = dock(); dk.position.set(st.home[0], 0, st.home[1]); staticGroup.add(dk); }
      garden(st, r);
      // 停電：看不到的地方蓋黑色方塊
      st.tiles.forEach(function (t) { fogBox(t[0], t[1], 0.05, staticGroup); });
      st.walls.forEach(function (w) { fogBox(w[0], w[1], WALL_H + 0.05, wallGroup); });
      center.set((st.w - 1) / 2, 0, (st.h - 1) / 2);
      dist = Math.max(st.w, st.h) * 0.72;
      var span = Math.max(st.w, st.h) * 0.75;
      sun.position.set(center.x - 5, 16, center.z + 4); sun.target.position.copy(center);
      Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 1, far: 50 }); sun.shadow.camera.updateProjectionMatrix();
      // 地板上的「吸過的痕跡」（吸塵模式開著時，笨笨走過的地方會留下比較亮的條紋）
      var tc = document.createElement('canvas'); tc.width = st.w * 16; tc.height = st.h * 16;
      var tt = new THREE.CanvasTexture(tc); tt.colorSpace = THREE.SRGBColorSpace;
      var tm = new THREE.Mesh(new THREE.PlaneGeometry(st.w, st.h), new THREE.MeshBasicMaterial({ map: tt, transparent: true, depthWrite: false }));
      tm.rotation.x = -Math.PI / 2; tm.position.set(st.w / 2 - 0.5, 0.0025, st.h / 2 - 0.5); tm.renderOrder = 2; staticGroup.add(tm);
      trail = { c: tc, g: tc.getContext('2d'), t: tt, last: null, dirty: false, at: 0 };
      collidables = wallMeshes.concat(furnGroups);
      makeMotes(st);
    }
    var baseGeo = new THREE.BoxGeometry(1, 0.09, 0.024), crownGeo = new THREE.BoxGeometry(1, 0.08, 0.04);
    // 屋外的小花園（俯瞰時看得到）：樹、灌木、石板路
    var leafMats = ['#5f8f4e', '#6fa35a', '#4f7d43'].map(function (c) { return new THREE.MeshStandardMaterial({ color: c, roughness: 0.9, flatShading: true }); });
    var barkMat = new THREE.MeshStandardMaterial({ color: '#7a5636', roughness: 1 }), stoneMat = new THREE.MeshStandardMaterial({ color: '#cfc6b8', roughness: 0.95 });
    var motes = null;
    function makeMotes(st) {
      if (motes) scene.remove(motes.pts);
      var n = Math.min(260, st.tiles.length), pos = new Float32Array(n * 3), base = [];
      for (var i = 0; i < n; i++) {
        var t = st.tiles[Math.floor(Math.random() * st.tiles.length)];
        base.push([t[0] + rr(0.5), 0.3 + Math.random() * (WALL_H - 0.5), t[1] + rr(0.5), Math.random() * 6]);
      }
      var g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      var pts = new THREE.Points(g, new THREE.PointsMaterial({ color: '#fff6dc', size: 0.025, transparent: true, opacity: 0.55, depthWrite: false }));
      motes = { pts: pts, base: base, pos: pos }; scene.add(pts);
    }
    function garden(st, r) {
      var spots = [];
      for (var i = 0; i < 26; i++) {
        var side = i % 4, t = r(), x, z, off = 1.6 + r() * 2.8;
        if (side === 0) { x = -0.5 + t * st.w; z = -0.5 - off; } else if (side === 1) { x = st.w - 0.5 + off; z = -0.5 + t * st.h; }
        else if (side === 2) { x = -0.5 + t * st.w; z = st.h - 0.5 + off; } else { x = -0.5 - off; z = -0.5 + t * st.h; }
        spots.push([x, z]);
      }
      spots.forEach(function (s, i) {
        var g = new THREE.Group(), big = i % 3 === 0;
        if (big) {
          var trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.14, 1.2, 7), barkMat); trunk.position.y = 0.6; g.add(trunk);
          [[0, 1.6, 0.9], [0.3, 2.1, 0.65], [-0.25, 2.3, 0.55]].forEach(function (b, k) {
            var c = new THREE.Mesh(new THREE.IcosahedronGeometry(b[2], 0), leafMats[k % 3]); c.position.set(b[0], b[1], b[0] * 0.5); g.add(c);
          });
        } else {
          var bush = new THREE.Mesh(new THREE.IcosahedronGeometry(0.35 + r() * 0.25, 0), leafMats[i % 3]); bush.position.y = 0.25; bush.scale.y = 0.75; g.add(bush);
        }
        g.traverse(function (o) { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
        g.position.set(s[0], 0, s[1]); g.rotation.y = r() * 6; staticGroup.add(g);
      });
      if (st.home) for (var k = 0; k < 6; k++) {                 // 門前的石板路
        var st0 = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.3, 0.04, 8), stoneMat);
        st0.position.set(-1.0 - k * 0.75, 0.0, Math.min(st.h - 1, st.home[1] + 1) + (k % 2) * 0.2); st0.receiveShadow = true; staticGroup.add(st0);
      }
    }
    function fogBox(x, y, h, parent) {
      var f = new THREE.Mesh(new THREE.BoxGeometry(1.001, h, 1.001), fogMat); f.position.set(x, h / 2 - 0.01, y); f.visible = false;
      parent.add(f); fogBoxes[x + ',' + y] = f;
    }
    function windowAt(x, z, rot, small) {
      var g = new THREE.Group(), w = small ? 0.5 : 0.82, h = small ? 0.45 : 1.0, y0 = small ? 1.4 : 0.85;
      var glass = new THREE.Mesh(new THREE.PlaneGeometry(w, h), glassMat); glass.position.set(0, y0 + h / 2, 0.006); g.add(glass);
      [[w + 0.08, 0.05, 0, y0 - 0.0], [w + 0.08, 0.05, 0, y0 + h], [0.05, h, -w / 2 - 0.0, y0 + h / 2], [0.05, h, w / 2, y0 + h / 2], [0.03, h, 0, y0 + h / 2]].forEach(function (b) {
        var m = new THREE.Mesh(new THREE.BoxGeometry(b[0], b[1], 0.04), trimMat); m.position.set(b[2], b[3], 0.02); g.add(m);
      });
      var sill = new THREE.Mesh(new THREE.BoxGeometry(w + 0.16, 0.03, 0.1), trimMat); sill.position.set(0, y0 - 0.03, 0.05); g.add(sill);
      if (!small) [-1, 1].forEach(function (s) {
        var c = new THREE.Mesh(new THREE.PlaneGeometry(0.2, h + 0.35), curtainMat); c.position.set(s * (w / 2 + 0.12), y0 + h / 2 - 0.05, 0.05); g.add(c);
      });
      g.position.set(x, 0, z); g.rotation.y = rot; return g;
    }
    function artAt(x, z, rot, k, y) {
      var g = new THREE.Group(), w = 0.36 + (k % 2) * 0.12, h = 0.46;
      var fr = new THREE.Mesh(new THREE.BoxGeometry(w + 0.05, h + 0.05, 0.03), woodTrim); fr.position.set(0, y, 0.015); g.add(fr);
      var pic = new THREE.Mesh(new THREE.PlaneGeometry(w, h), ARTS[k]); pic.position.set(0, y, 0.032); g.add(pic);
      g.position.set(x, 0, z); g.rotation.y = rot; return g;
    }
    var lampOn = new THREE.MeshBasicMaterial({ color: '#fff4dc', toneMapped: false }), lampOff = new THREE.MeshStandardMaterial({ color: '#d9d4c8' });
    function lampAt(x, z, fan, withLight) {
      var g = new THREE.Group();
      var disc = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.06, 32), lampOn); disc.position.y = WALL_H - 0.04; g.add(disc);
      var rim = new THREE.Mesh(new THREE.TorusGeometry(0.31, 0.015, 8, 32), trimMat); rim.rotation.x = Math.PI / 2; rim.position.y = WALL_H - 0.07; g.add(rim);
      g.userData.disc = disc;
      if (fan) {
        var f = new THREE.Group(); f.position.y = WALL_H - 0.32;
        var rod = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.25, 8), woodTrim); rod.position.y = 0.15; f.add(rod);
        f.add(new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 0.08, 20), woodTrim));
        for (var i = 0; i < 4; i++) { var bl = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.012, 0.14), wainMat); bl.position.x = 0.38; var arm = new THREE.Group(); arm.rotation.y = i * Math.PI / 2; arm.add(bl); f.add(arm); }
        g.add(f); fans.push(f); disc.position.y = WALL_H - 0.04;
      }
      if (withLight) {
        var L1 = new THREE.PointLight(0xffe2b8, 7, 12, 1.6); L1.position.y = WALL_H - 0.35; g.add(L1); g.userData.light = L1;
      }
      g.position.set(x, 0, z); return g;
    }

    // ---------- 動態物件（有變才重建）----------
    function makeObj(e, x, y) {
      if (e === '🧱') return lego(x * 7 + y * 3);
      if (e === '🧦') return sock();
      if (e === '➰') return cable(x * 5 + y);
      if (e === '💩') return poop();
      if (e === '💧') return puddle();
      if (e === '🕳️') return hole(x * 13 + y);
      if (e === '🍌') return banana();
      if (e === '🧰') return toolbox();
      return null;
    }
    function syncDyn(want) {
      Object.keys(dynObjs).forEach(function (k) { if (!want[k]) { dynGroup.remove(dynObjs[k]); delete dynObjs[k]; } });
      Object.keys(want).forEach(function (k) {
        if (dynObjs[k]) return;
        var w = want[k], g = w.dirt ? dirt(w.x * 31 + w.y * 7) : makeObj(w.e, w.x, w.y);
        if (!g) return; g.position.set(w.x, 0, w.y); dynGroup.add(g); dynObjs[k] = g;
      });
    }
    function syncPets(kind, spots) {
      var list = pets[kind];
      while (list.length < spots.length) {
        var p = kind === 'roach' ? { g: roach(), roach: true } : makePet(kind); if (!p) return;
        list.push(p); scene.add(p.g);
        var s0 = spots[list.length - 1];
        if (kind === 'cat' && rideOff) { p.g.position.copy(robot.position); p.hop = 1; rideOff = false; } else p.g.position.set(s0[0], 0, s0[1]);
      }
      while (list.length > spots.length) { var old = list.pop(); scene.remove(old.g); }
      list.forEach(function (p, i) { p.target = new THREE.Vector3(spots[i][0], 0, spots[i][1]); });
    }
    var rideOff = false;

    function newGame() {      // 換關或重來：把笨笨組回去、清掉特效和痕跡
      PARTS.forEach(function (p) {
        if (p.parent !== body) body.add(p);
        p.position.copy(p.userData.home.pos); p.quaternion.copy(p.userData.home.quat);
      });
      debris.forEach(function (d) { if (d.extra) scene.remove(d.o); }); debris = [];
      while (fxGroup.children.length) fxGroup.remove(fxGroup.children[0]);
      parts.forEach(function (s) { scene.remove(s); s.material.dispose(); }); parts = [];
      shellMat.color.set('#24282f'); shellMat.emissive.set('#000000');
      wrecked = false; override = null; bump.off.set(0, 0, 0); bump.pending = null; robot.visible = true; body.position.set(0, 0, 0); body.rotation.set(0, 0, 0);
      if (trail) { trail.g.clearRect(0, 0, trail.c.width, trail.c.height); trail.t.needsUpdate = true; trail.last = null; }
      if (riderCat) { robot.remove(riderCat.g); riderCat = null; }
    }

    function update(st) {
      var key = [st.level, st.w, st.h, st.walls.length, st.tiles.length, (st.furniture || []).length].join('|');
      if (key !== staticKey) {
        staticKey = key; buildStatic(st);
        ['cat', 'dog', 'roach'].forEach(function (k) { pets[k].forEach(function (p) { scene.remove(p.g); }); pets[k] = []; });
        Object.keys(dynObjs).forEach(function (k) { dynGroup.remove(dynObjs[k]); }); dynObjs = {}; prevDirt = {}; first = true; forbKey = '';
      }
      if (st.gid !== gid) { gid = st.gid; newGame(); first = true; }
      dark = !!st.dark;
      var vis = {};
      st.tiles.forEach(function (t) { vis[t[0] + ',' + t[1]] = t[3]; });
      st.walls.forEach(function (w) { vis[w[0] + ',' + w[1]] = w[2]; });
      Object.keys(fogBoxes).forEach(function (k) { fogBoxes[k].visible = dark && !vis[k]; });
      // 灰塵、物件
      var want = {}, nowDirt = {}, cats = [], dogs = [], roaches = [];
      st.dirt.forEach(function (d) { want['d' + d[0] + ',' + d[1]] = { dirt: 1, x: d[0], y: d[1] }; nowDirt[d[0] + ',' + d[1]] = 1; });
      if (!first) Object.keys(prevDirt).forEach(function (k) { if (!nowDirt[k]) { var p = k.split(','); burst(+p[0], +p[1]); } });
      prevDirt = nowDirt;
      st.objects.forEach(function (o) {
        var e = o[2];
        if (e === '🐱') cats.push([o[0], o[1]]); else if (e === '🐶') dogs.push([o[0], o[1]]); else if (e === '🪳') roaches.push([o[0], o[1]]);
        else want[e + o[0] + ',' + o[1]] = { e: e, x: o[0], y: o[1] };
      });
      syncDyn(want);
      // 禁區：半透明紅色地板＋標示（禁區清單變了才重畫）
      var fk = st.rooms.filter(function (r) { return r[3]; }).map(function (r) { return r[0]; }).join(',') + (dark ? 'd' : '');
      if (fk !== forbKey) {
        forbKey = fk;
        while (roomGroup.children.length) roomGroup.remove(roomGroup.children[0]);
        var forb = {}, Q = Quads();
        st.rooms.forEach(function (rm) { if (rm[3]) forb[rm[0]] = rm; });
        st.tiles.forEach(function (t) { if (forb[t[4]] && !dark) hquad(Q, t[0], t[1], 0.008, 0.98); });
        var fm = Q.mesh(new THREE.MeshBasicMaterial({ color: '#ef4444', transparent: true, opacity: 0.22, depthWrite: false }));
        if (fm) { fm.castShadow = fm.receiveShadow = false; roomGroup.add(fm); }
        Object.keys(forb).forEach(function (n) { var rm = forb[n], s = sprite('🚫', 0.5); s.position.set(rm[1] - 0.5, 1.6, rm[2] - 0.5); roomGroup.add(s); });
      }
      // 笨笨
      var R = st.robot, moved = R.x !== target.x || R.y !== target.z || R.facing !== target.f;
      if (moved && !first && bump.to.lengthSq() > 0) { bump.from.copy(bump.off); bump.to.set(0, 0, 0); bump.t0 = performance.now(); bump.dur = 260; }
      target.x = R.x; target.z = R.y; target.f = R.facing;
      lidMat.color.set(R.lid); thinking = !!R.thinking;
      driving = !!R.driving; vac = !!R.vac; dmg = R.dmg || 0;
      ringMat.color.set(R.low ? '#ef4444' : '#38bdf8'); ringMat.emissive.set(R.low ? '#ef4444' : '#38bdf8');
      var emo = R.thinking ? '🤔' : (R.emotion || ' ');
      head.material.map = texCache[emo] || (texCache[emo] = spriteTex(emo)); head.material.needsUpdate = true;
      drawFace(wrecked || st.over === 'exploded' ? 'dead' : dmg ? 'hurt' : R.thinking ? 'think' : R.rider ? 'love' :
               ({ '😄': 'happy', '😠': 'angry', '🥺': 'sad', '😎': 'cool', '😱': 'scared' }[R.emotion] || 'n'));
      hemi.intensity = dark ? 0.06 : 0.55; sun.intensity = dark ? 0.08 : 1.3; headlight.intensity = dark ? 8 : 0;
      scene.environmentIntensity = dark ? 0.12 : 0.9;
      ceilMat.emissiveIntensity = dark ? 0.02 : 0.32;
      lamps.forEach(function (l) { if (l.userData.light) l.userData.light.intensity = dark ? 0 : 7; l.userData.disc.material = dark ? lampOff : lampOn; });
      // 搭便車的貓
      if (R.rider && !riderCat) {
        riderCat = makePet('cat');
        if (riderCat) { riderCat.g.position.set(0, 0.16, 0.02); riderCat.g.scale.setScalar(0.8); robot.add(riderCat.g); riderCat.hop = 1; }
      } else if (!R.rider && riderCat) { robot.remove(riderCat.g); riderCat = null; rideOff = true; }
      syncPets('cat', cats); syncPets('dog', dogs); syncPets('roach', roaches);
      rideOff = false;
      // 特效（只播新的）
      var fx = st.fx || [], maxId = fx.length ? fx[fx.length - 1][0] : 0;
      if (first || maxId < lastFx) lastFx = maxId;
      fx.forEach(function (f) { if (f[0] > lastFx) playFx(f); });
      lastFx = Math.max(lastFx, maxId);
      if (!override) motion.push(R.x, R.y, R.facing * Math.PI / 2, (st.tick || 0.5) * 1000, Date.now());
      var ov = st.over === 'clear' ? '🎉 CLEAR!' : (st.over ? (FAIL_TXT[st.over] || '💀 失敗') : '');
      if (ov !== overState) {
        overState = ov;
        if (ov) later(st.over === 'exploded' ? 1.2 : 0.3, function () { if (overState === ov) { over.textContent = ov; over.style.display = 'block'; } });
        else over.style.display = 'none';
        over.style.color = st.over === 'clear' ? '#2a9d8f' : '#d62828';
      }
      if (first) { motion.jump(R.x, R.y, R.facing * Math.PI / 2); robot.position.set(R.x, 0, R.y); robot.rotation.y = -R.facing * Math.PI / 2; first = false; }
    }

    // ---------- 特效 ----------
    function fwdOf(f) { return V(DIRS4[f][0], 0, DIRS4[f][1]); }
    function playFx(f) {
      var kind = f[1], x = f[2], y = f[3], dir = f[4], extra = f[5] || {};
      if (kind === 'bump') bump.pending = { x: x, y: y, f: dir };
      else if (kind === 'smoke') later(bump.pending ? 0.25 : 0, function () {
        var p = robot.position.clone().add(V(0, 0.25, 0));
        for (var i = 0; i < 10; i++) smokePuff(p, false, false);
        sparks(p, 14); flash(p, 0xffaa55, 6, 0.25); sfx('smoke');
      });
      else if (kind === 'boom') {
        var delay = override ? 1.0 : bump.pending ? 0.3 : 0;
        later(delay, function () { explode(override ? V(x, -0.2, y) : robot.position.clone()); });
      }
      else if (kind === 'fall') fall(x, y);
      else if (kind === 'rescue') { if (override) override.rescue = { x: x, y: y, f: dir }; }
      else if (kind === 'spin') { spin = { t0: performance.now(), dur: 900, amt: Math.PI * 4 }; sfx('spin'); }
      else if (kind === 'quake') { shakeCam(0.16, 1.8); quakeT = performance.now(); sfx('quake'); }
      else if (kind === 'repair') {
        sfx('repair');
        for (var i = 0; i < 24; i++) {
          var a = i / 24 * 6.28;
          emit({ pos: V(x + Math.cos(a) * 0.4, 0.05, y + Math.sin(a) * 0.4), vel: V(-Math.cos(a) * 0.2, 0.9, -Math.sin(a) * 0.2), color: '#7CFC9A', size0: 0.07, size1: 0.02, life: 1, alpha: 1, add: true });
        }
      }
      else if (kind === 'gulp') { sparks(V(x, 0.1, y), 16, '#fff2a8', 0.8); sfx('gulp'); }
      else if (kind === 'ride_on') { sfx('meow'); }
      else if (kind === 'coin') {
        sfx('coin');
        var coin = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.02, 24), new THREE.MeshStandardMaterial({ color: '#f5c542', metalness: 0.9, roughness: 0.25, emissive: '#5a4100' }));
        coin.rotation.x = Math.PI / 2; fxGroup.add(coin);
        addTween(1.1, function (k) { coin.position.set(x, 0.2 + Math.sin(Math.min(1, k * 1.6) * Math.PI / 2) * 0.7, y); coin.rotation.z = k * 18; coin.material.opacity = 1; coin.scale.setScalar(k > 0.8 ? (1 - k) * 5 : 1); },
                 function () { fxGroup.remove(coin); sparks(V(x, 0.9, y), 10, '#ffe17a', 0.6); });
      }
      else if (kind === 'clear') {
        sfx('clear'); spin = { t0: performance.now(), dur: 1400, amt: Math.PI * 4 };
        var cols = ['#e63946', '#f4a261', '#e9c46a', '#2a9d8f', '#457b9d', '#b5179e'];
        for (var c = 0; c < 90; c++) {
          var pc = new THREE.Mesh(confettiGeo, new THREE.MeshBasicMaterial({ color: cols[c % 6], side: THREE.DoubleSide }));
          pc.position.set(x + rr(0.3), 0.3, y + rr(0.3)); fxGroup.add(pc);
          debris.push({ o: pc, extra: true, v: V(rr(2.2), 3 + Math.random() * 2.5, rr(2.2)), w: V(rr(14), rr(14), rr(14)), r: 0.005, slow: true });
        }
      }
      else if (kind === 'ride_off') { sfx('meow'); }
    }
    var confettiGeo = new THREE.PlaneGeometry(0.06, 0.035);
    function flash(p, col, power, dur) {
      var l = new THREE.PointLight(col, 0, 6, 1.5); l.position.copy(p); fxGroup.add(l);
      addTween(dur, function (k) { l.intensity = power * (k < 0.15 ? k / 0.15 : 1 - (k - 0.15) / 0.85); }, function () { fxGroup.remove(l); });
    }
    function startBump(b) {
      // 從格子中心往前打一條射線，找到真的會碰到的東西（牆面、家具正面、寵物）→ 笨笨開過去貼上它
      var o = V(b.x, 0.09, b.y), d = fwdOf(b.f), hit = null;
      raycaster.set(o, d); raycaster.far = 2.2;
      var hits = raycaster.intersectObjects(collidables.concat(pets.cat.concat(pets.dog).map(function (p) { return p.g; })), true);
      if (hits.length) hit = hits[0].distance;
      var reach = hit === null ? 0.5 - R_BOT : Math.max(0, Math.min(hit - R_BOT - 0.004, 1.5));
      bump.from.copy(bump.off); bump.to.copy(d).multiplyScalar(reach); bump.t0 = performance.now();
      bump.dur = Math.max(90, reach / 2.4 * 1000); bump.at = { p: o.clone().addScaledVector(d, reach + R_BOT), d: d };
      later(bump.dur / 1000, function () {
        bump.squash = 1; shakeCam(0.07, 0.35); sfx('bump');
        var p = bump.at.p.clone(); p.y = 0.1; dust(p, 10); sparks(p, 5, '#ffe9b0', 0.6);
        bump.to.addScaledVector(bump.at.d, -0.02);            // 撞到後微微彈回
        bump.from.copy(bump.off); bump.t0 = performance.now(); bump.dur = 140;
      });
    }
    function burst(x, z) {
      sfx('clean');
      for (var i = 0; i < 18; i++) emit({ pos: V(x, 0.08, z), vel: V(rr(0.5), 0.6 + Math.random() * 0.6, rr(0.5)), color: '#fff3b0', size0: 0.06, size1: 0.01, life: 0.8, alpha: 1, add: true, grav: 1.5 });
      if (trail) { var g = trail.g; g.fillStyle = 'rgba(255,255,255,0.18)'; g.beginPath(); g.arc((x + 0.5) * 16, (z + 0.5) * 16, 7, 0, 7); g.fill(); trail.dirty = true; }
    }
    function explode(p) {
      if (wrecked) return;
      wrecked = true; sfx('boom'); shakeCam(0.32, 1.3); flash(p.clone().add(V(0, 0.5, 0)), 0xffa040, 60, 0.7);
      drawFace('dead');
      // 火球
      [['#fff1b8', 0.9, 0.35], ['#ffb347', 1.4, 0.55], ['#ff5a1f', 1.8, 0.75]].forEach(function (c, i) {
        var m = new THREE.Mesh(new THREE.SphereGeometry(0.5, 20, 14), new THREE.MeshBasicMaterial({ color: c[0], transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
        m.position.copy(p).add(V(0, 0.3, 0)); fxGroup.add(m);
        addTween(c[2], function (k) { m.scale.setScalar(0.2 + c[1] * Math.sqrt(k)); m.material.opacity = 1 - k; m.position.y = p.y + 0.3 + k * 0.4; }, function () { fxGroup.remove(m); });
      });
      // 衝擊波
      var ringM = new THREE.Mesh(new THREE.RingGeometry(0.85, 1, 48), new THREE.MeshBasicMaterial({ color: '#ffd8a8', transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
      ringM.rotation.x = -Math.PI / 2; ringM.position.set(p.x, 0.02, p.z); fxGroup.add(ringM);
      addTween(0.6, function (k) { ringM.scale.setScalar(0.2 + k * 3); ringM.material.opacity = 0.8 * (1 - k); }, function () { fxGroup.remove(ringM); });
      // 焦黑的痕跡
      var sc = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 2.0), new THREE.MeshBasicMaterial({ map: contactTex, transparent: true, depthWrite: false, color: '#000', opacity: 0.95 }));
      sc.rotation.x = -Math.PI / 2; sc.position.set(p.x, 0.006, p.z); fxGroup.add(sc);
      // 零件飛出去
      robot.updateMatrixWorld(true);
      PARTS.forEach(function (o, i) {
        if (o === shell) return;
        scene.attach(o);
        var a = Math.random() * 6.28;
        debris.push({ o: o, v: V(Math.cos(a) * (1 + Math.random() * 2), 3 + Math.random() * 3, Math.sin(a) * (1 + Math.random() * 2)), w: V(rr(9), rr(9), rr(9)), r: 0.06 });
      });
      for (var i = 0; i < 16; i++) {
        var ch = mesh(new THREE.BoxGeometry(0.04 + Math.random() * 0.06, 0.02 + Math.random() * 0.03, 0.04 + Math.random() * 0.05), M(i % 3 ? '#2a2d33' : '#98c1d9', 0.6));
        ch.position.copy(p).add(V(0, 0.15, 0)); scene.add(ch); var a2 = Math.random() * 6.28;
        debris.push({ o: ch, extra: true, v: V(Math.cos(a2) * (1.5 + Math.random() * 3), 2 + Math.random() * 4, Math.sin(a2) * (1.5 + Math.random() * 3)), w: V(rr(12), rr(12), rr(12)), r: 0.02 });
      }
      shellMat.color.set('#121212'); shellMat.emissive.set('#5a1a00');
      addTween(3, function (k) { shellMat.emissive.setRGB(0.35 * (1 - k), 0.1 * (1 - k), 0); });
      for (var j = 0; j < 26; j++) smokePuff(p.clone().add(V(0, 0.3, 0)), true, true);
      sparks(p.clone().add(V(0, 0.3, 0)), 50, '#ffcf70', 2.6);
      if (riderCat) { robot.remove(riderCat.g); riderCat = null; }
    }
    function fall(x, y) {
      sfx('fall');
      var start = robot.position.clone(), hole = V(x, 0, y), t0 = performance.now();
      override = { t0: t0, rescue: null, fn: function (now) {
        var t = (now - t0) / 1000;
        if (t < 0.3) { robot.position.lerpVectors(start, hole, t / 0.3); return false; }
        if (t < 1.1) {
          var k = (t - 0.3) / 0.8; robot.position.copy(hole); robot.position.y = -1.4 * k * k;
          body.rotation.x = -k * 1.1; body.rotation.z = Math.sin(k * 9) * 0.2;
          if (Math.random() < 0.3) dust(V(x, 0.05, y), 2);
          return false;
        }
        robot.visible = false; body.rotation.set(0, 0, 0);
        if (wrecked) { override.hide = true; return t > 1.3; }
        var rs = override.rescue; if (!rs) return t > 1.6;
        if (t < 1.5) return false;
        var k2 = Math.min(1, (t - 1.5) / 0.5);
        robot.visible = true; robot.position.set(rs.x, 1.6 * (1 - k2) * (1 - k2) + Math.abs(Math.sin(k2 * 6)) * 0.08 * (1 - k2), rs.y);
        robot.rotation.y = -rs.f * Math.PI / 2;
        if (k2 >= 1) { sfx('rescue'); dust(V(rs.x, 0.05, rs.y), 8); return true; }
        return false;
      } };
    }

    // 相機操作
    host.addEventListener('click', function (e) { var b = e.target.closest('[data-cam]'); if (b) setCam(b.getAttribute('data-cam')); });
    function setCam(c) {
      cam = c;
      bar.querySelectorAll('[data-cam]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-cam') === c); });
      host.classList.toggle('bd-cctv', c === 'cctv');
      hint.textContent = { follow: '相機跟在笨笨背後：畫面的左右＝笨笨的左右', eye: '笨笨的眼睛看出去', top: '俯瞰：拖曳轉視角、滾輪縮放（牆會自動降低）', cctv: '房間角落的監視器' }[c];
    }
    setCam('follow');
    var drag = null, cvs = renderer.domElement;
    cvs.addEventListener('pointerdown', function (e) { drag = e.clientX; });
    cvs.addEventListener('pointermove', function (e) {
      if (drag === null || Math.abs(e.clientX - drag) < 3) return;
      if (cam !== 'top') setCam('top'); yaw -= (e.clientX - drag) * 0.01; drag = e.clientX;
    });
    cvs.addEventListener('pointerup', function () { drag = null; });
    cvs.addEventListener('pointerleave', function () { drag = null; });
    cvs.addEventListener('wheel', function (e) { e.preventDefault(); if (cam !== 'top') setCam('top'); dist = Math.max(4, Math.min(40, dist * (1 + e.deltaY * 0.001))); }, { passive: false });

    var clock = new THREE.Clock(), fwd = new THREE.Vector3(), tmp = new THREE.Vector3(), pivot = new THREE.Vector3(), lastSmoke = 0, lastSpark = 0;
    function ease(k) { return k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; }
    function loop() {
      var win = cvs.ownerDocument.defaultView || window;     // 彈出視窗後要用新視窗的 rAF
      win.requestAnimationFrame(loop);
      var dt = Math.min(clock.getDelta(), 0.05), now = performance.now(), T = clock.elapsedTime;
      if (!cvs.isConnected || cvs.offsetParent === null) return;
      var W = host.clientWidth || 640, H = Math.round(W * 0.6);
      if (cvs.width !== Math.round(W * renderer.getPixelRatio())) { renderer.setSize(W, H); camera.aspect = W / H; camera.updateProjectionMatrix(); }
      // 計時動畫
      for (var i = tweens.length - 1; i >= 0; i--) {
        var tw = tweens[i], k = Math.min(1, (now - tw.t0) / tw.dur); tw.fn(k);
        if (k >= 1) { tweens.splice(i, 1); if (tw.done) tw.done(); }
      }
      // 笨笨的位置：連續移動（30 幀）＋撞擊位移；掉洞時由 override 接手
      if (override) {
        if (override.fn(now)) { robot.visible = !override.hide; override = null; motion.jump(target.x, target.z, target.f * Math.PI / 2); }
      } else {
        if (bump.pending && !motion.moving()) { startBump(bump.pending); bump.pending = null; }
        var bk = Math.min(1, (now - bump.t0) / bump.dur);
        bump.off.lerpVectors(bump.from, bump.to, ease(bk));
        var mp = motion.at(Date.now());
        if (mp) { robot.position.set(mp.x + bump.off.x, 0, mp.y + bump.off.z); robot.rotation.y = -mp.r; }
        if (spin.dur) { var sk = Math.min(1, (now - spin.t0) / spin.dur); robot.rotation.y += spin.amt * (1 - ease(sk)); if (sk >= 1) spin.dur = 0; }
      }
      bump.squash = Math.max(0, bump.squash - dt * 4);
      var busy = motion.moving() || driving;
      if (!wrecked) {
        body.scale.set(1 + bump.squash * 0.08, 1 - bump.squash * 0.12, 1 - bump.squash * 0.1);
        if (!override) body.position.y = busy ? Math.sin(T * 30) * 0.003 : 0;
        brushes.forEach(function (b, i) { b.rotation.y += (i ? -1 : 1) * dt * (vac ? 40 : busy ? 22 : 3); });
        lidar.rotation.y += dt * (busy ? 9 : 2);
        ringMat.emissiveIntensity = thinking ? 1 + Math.sin(T * 6) * 0.9 : dmg ? (Math.random() < 0.08 ? 0.1 : 1.6) : 1.6;
      }
      hum(vac && busy && !wrecked);
      // 冒煙（受損）／殘骸一直冒黑煙
      if ((dmg >= 1 || wrecked) && robot.visible !== false && now - lastSmoke > (wrecked ? 70 : 110)) {
        lastSmoke = now; smokePuff(wrecked ? robot.position.clone().add(V(0, 0.1, 0)) : robot.position.clone().add(V(0.05, 0.2, 0.08)), wrecked, wrecked);
      }
      if (dmg >= 1 && !wrecked && now - lastSpark > 900 + Math.random() * 900) { lastSpark = now; sparks(robot.position.clone().add(V(0, 0.18, 0)), 5); }
      // 粒子
      for (var j = parts.length - 1; j >= 0; j--) {
        var s = parts[j], u = s.userData; u.life += dt; var k2 = u.life / u.max;
        if (k2 >= 1) { scene.remove(s); s.material.dispose(); parts.splice(j, 1); continue; }
        u.v.y -= u.g * dt; if (u.drag) u.v.multiplyScalar(Math.max(0, 1 - u.drag * dt));
        s.position.addScaledVector(u.v, dt); if (s.position.y < 0.01 && u.g) { s.position.y = 0.01; u.v.y *= -0.3; }
        s.scale.setScalar(u.s0 + (u.s1 - u.s0) * k2); s.material.opacity = u.a * (1 - k2);
      }
      // 爆炸碎片（重力、落地彈跳）
      debris.forEach(function (d) {
        if (d.rest) return;
        d.v.y -= (d.slow ? 3 : 9.8) * dt; if (d.slow && d.v.y < -0.8) { d.v.y = -0.8; d.v.x *= 0.98; d.v.z *= 0.98; }
        d.o.position.addScaledVector(d.v, dt);
        d.o.rotation.x += d.w.x * dt; d.o.rotation.y += d.w.y * dt; d.o.rotation.z += d.w.z * dt;
        if (d.o.position.y < d.r) { d.o.position.y = d.r; d.v.y *= -0.35; d.v.x *= 0.6; d.v.z *= 0.6; d.w.multiplyScalar(0.6); if (Math.abs(d.v.y) < 0.4) d.rest = true; }
      });
      // 寵物、小強
      ['cat', 'dog', 'roach'].forEach(function (kd) {
        pets[kd].forEach(function (p) {
          if (!p.target) return;
          tmp.subVectors(p.target, p.g.position); tmp.y = 0; var d = tmp.length();
          if (d > 0.03) {
            p.g.position.addScaledVector(tmp, Math.min(1, dt * (p.roach ? 7 : 2.5)));
            p.g.rotation.y = Math.atan2(tmp.x, tmp.z) + (p.roach ? Math.PI : 0);
            if (p.walk && !p.walk.isRunning()) { if (p.idle) p.idle.stop(); p.walk.play(); }
          } else if (p.idle && !p.idle.isRunning()) { if (p.walk) p.walk.stop(); p.idle.play(); }
          if (p.hop) { p.hop = Math.max(0, p.hop - dt * 2.5); p.g.position.y = Math.sin(p.hop * Math.PI) * 0.35; }
          if (p.roach) { p.g.userData.anim(T); p.g.position.x += Math.sin(T * 40) * 0.002; }
          if (p.mixer) p.mixer.update(dt);
        });
      });
      if (riderCat) { riderCat.mixer.update(dt); if (riderCat.hop) { riderCat.hop = Math.max(0, riderCat.hop - dt * 2.5); riderCat.g.position.y = 0.16 + Math.sin(riderCat.hop * Math.PI) * 0.3; } }
      Object.keys(dynObjs).forEach(function (k3) { var o = dynObjs[k3]; if (o.userData.anim) o.userData.anim(T); });
      fans.forEach(function (f) { f.rotation.y += dt * (dark ? 0 : 4); });
      if (motes) {                                      // 空氣中慢慢飄的灰塵微粒（只在房間裡的相機看得到）
        motes.pts.visible = !dark && cam !== 'top';
        if (motes.pts.visible) {
          motes.base.forEach(function (b, i) {
            motes.pos[i * 3] = b[0] + Math.sin(T * 0.21 + b[3]) * 0.25; motes.pos[i * 3 + 1] = b[1] + Math.sin(T * 0.13 + b[3] * 2) * 0.15;
            motes.pos[i * 3 + 2] = b[2] + Math.cos(T * 0.17 + b[3]) * 0.25;
          });
          motes.pts.geometry.attributes.position.needsUpdate = true;
        }
      }
      // 地震：家具和燈跟著晃
      var qk = quakeT ? (now - quakeT) / 1800 : 1;
      furnGroups.forEach(function (g) { g.children[0].rotation.z = qk < 1 ? Math.sin(T * 25 + g.position.x) * 0.06 * (1 - qk) : 0; });
      // 剖面：俯瞰時牆降低、天花板和牆上的裝飾藏起來
      cut += ((cam === 'top' ? CUT_H / WALL_H : 1) - cut) * Math.min(1, dt * 6);
      wallGroup.scale.y = cut; decor.visible = cut > 0.9; ceilGroup.visible = cut > 0.95;
      // 吸過的痕跡
      if (trail && vac && !wrecked && !override) {
        var px = (robot.position.x + 0.5) * 16, pz = (robot.position.z + 0.5) * 16;
        if (trail.last) {
          var dx = px - trail.last[0], dz = pz - trail.last[1];
          if (dx * dx + dz * dz > 4) {
            var g = trail.g; g.save(); g.translate(px, pz); g.rotate(Math.atan2(dz, dx)); g.fillStyle = 'rgba(255,255,255,0.09)';
            g.fillRect(-Math.hypot(dx, dz) - 1, -5, Math.hypot(dx, dz) + 2, 10); g.restore(); trail.last = [px, pz]; trail.dirty = true;
          }
        } else trail.last = [px, pz];
      } else if (trail) trail.last = null;
      if (trail && trail.dirty && now - trail.at > 120) { trail.t.needsUpdate = true; trail.dirty = false; trail.at = now; }
      // 相機
      fwd.set(-Math.sin(robot.rotation.y), 0, -Math.cos(robot.rotation.y));
      var wantPos, wantLook, snap = false;
      var rp = robot.position.clone(); if (rp.y < 0) rp.y = 0;
      if (cam === 'follow') {   // 第三人稱：跟在笨笨背後；後面是牆就把相機拉近（不會穿牆）
        pivot.copy(rp).add(V(0, 0.85, 0));
        wantPos = rp.clone().addScaledVector(fwd, -1.9).add(V(0, 1.3, 0));
        tmp.subVectors(wantPos, pivot); var L0 = tmp.length(); tmp.normalize();
        raycaster.set(pivot, tmp); raycaster.far = L0;
        var hit = raycaster.intersectObjects(wallMeshes, false)[0], ratio = 1;
        if (hit) { var dd = Math.max(0.25, hit.distance - 0.22); ratio = dd / L0; wantPos = pivot.clone().addScaledVector(tmp, dd); wantPos.y += (1 - ratio) * 0.9; }
        // 相機被牆擋住拉近時，改看笨笨前面一點點（不然笨笨會跑到畫面外）
        wantLook = rp.clone().addScaledVector(fwd, 0.3 + 1.3 * ratio).add(V(0, 0.15 * ratio, 0));
      } else if (cam === 'eye') {
        wantPos = rp.clone().addScaledVector(fwd, 0.22).add(V(0, 0.3, 0));
        wantLook = rp.clone().addScaledVector(fwd, 3).add(V(0, 0.22, 0)); snap = true;
      } else if (cam === 'cctv') {
        var room = roomAt[target.x + ',' + target.z] || '客廳', b = roomBox[room] || { x0: 0, y0: 0, x1: house.w - 1, y1: house.h - 1 };
        var corners = [[b.x0, b.y0], [b.x1, b.y0], [b.x0, b.y1], [b.x1, b.y1]].filter(function (c) { return roomAt[c[0] + ',' + c[1]] === room; });
        var c0 = corners[0] || [b.x0, b.y0], ccx = (b.x0 + b.x1) / 2, ccz = (b.y0 + b.y1) / 2;
        wantPos = V(c0[0] + (c0[0] < ccx ? -0.4 : 0.4), WALL_H - 0.25, c0[1] + (c0[1] < ccz ? -0.4 : 0.4));
        wantLook = rp.clone().add(V(0, 0.1, 0)); snap = true;
        rec.textContent = '● REC   CAM-' + room + '   ' + new Date().toLocaleString('zh-TW', { hour12: false });
      } else {
        wantPos = center.clone().add(V(Math.sin(yaw) * dist * 0.62, dist * 0.8, Math.cos(yaw) * dist * 0.62));
        wantLook = center;
      }
      var kk = camPos.lengthSq() ? Math.min(1, dt * (snap ? 12 : 5)) : 1;
      camPos.lerp(wantPos, kk); camLook.lerp(wantLook, kk);
      if (cam !== 'top' && camPos.y > WALL_H - 0.12) camPos.y = WALL_H - 0.12;
      camera.position.copy(camPos);
      var sh = shake.amp * Math.max(0, 1 - (now - shake.t0) / (shake.dur * 1000));
      if (sh > 0.001) camera.position.add(V(rr(sh), rr(sh * 0.6), rr(sh)));
      camera.fov = cam === 'eye' ? 78 : cam === 'cctv' ? 70 : 62; camera.updateProjectionMatrix();
      camera.lookAt(camLook);
      // 擋在相機前面的家具變透明
      var cx0 = camPos.x, cz0 = camPos.z, sx = robot.position.x - cx0, sz = robot.position.z - cz0, sl = sx * sx + sz * sz || 1;
      furnGroups.forEach(function (o) {
        var t = Math.max(0, Math.min(1, ((o.position.x - cx0) * sx + (o.position.z - cz0) * sz) / sl));
        var ddx = o.position.x - (cx0 + sx * t), ddz = o.position.z - (cz0 + sz * t);
        var near = cam !== 'top' && cam !== 'cctv' ? Math.hypot(ddx, ddz) < 0.8 || Math.hypot(o.position.x - cx0, o.position.z - cz0) < 1.2 : false;
        if (o.userData.faded === near) return; o.userData.faded = near;
        o.traverse(function (m) {
          if (!m.isMesh) return;
          (Array.isArray(m.material) ? m.material : [m.material]).forEach(function (mt) { mt.transparent = near; mt.opacity = near ? 0.2 : 1; mt.depthWrite = !near; });
        });
      });
      renderer.render(scene, camera);
    }
    loop();
    // 除錯用：在瀏覽器 console 可以看場景狀況（root.__bendan3d.info()）
    root.__bendan3d = { scene: scene, camera: camera, setCam: setCam, info: function () {
      var n = 0; scene.traverse(function (o) { if (o.isMesh) n++; });
      return { cam: cam, cut: cut, meshes: n, furniture: furnGroups.length, lamps: lamps.length, walls: wallMeshes.length, parts: parts.length,
               robot: robot.position.toArray(), bump: bump.off.toArray(), dmg: dmg, wrecked: wrecked, cats: pets.cat.length, roaches: pets.roach.length, lastFx: lastFx };
    } };
    return { update: update };
  }
