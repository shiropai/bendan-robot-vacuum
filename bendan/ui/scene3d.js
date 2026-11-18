  // ===== 🧊 3D 視角（Three.js）=====
  // Python 每次重畫都放一份世界狀態 JSON 到 .bd-state；第一次切到 3D 時，素材包（家具 OBJ、寵物 GLB）放在 .bd-assets。
  // 靜態場景（地板、牆、家具）每一關只建一次；灰塵、物件、寵物、笨笨每次更新，笨笨和寵物用補間動畫移動。
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
        host.innerHTML = "<div class='bd-3dmsg'>😵 3D 載入失敗：" + err.message + "<br>（需要網路下載 three.js）按「🔄 視角」換回 2.5D。</div>";
      });
  }
  new MutationObserver(check3d).observe(root, { subtree: true, childList: true, characterData: true });
  check3d();

  // 每個房間的家具（靠牆擺；一個項目可以疊兩件，例如電視櫃＋電視）
  var ROOM_FURNITURE = {
    '客廳': [['loungeSofa'], ['cabinetTelevision', 'televisionModern'], ['bookcaseOpen'], ['pottedPlant'],
            ['lampRoundFloor'], ['loungeChair'], ['speaker'], ['plantSmall1']],
    '臥室': [['cabinetBedDrawerTable'], ['bookcaseClosed'], ['lampSquareFloor'], ['coatRackStanding'], ['plantSmall2']],
    '廚房': [['kitchenFridge'], ['kitchenStove'], ['kitchenSink'], ['kitchenCabinet', 'kitchenCoffeeMachine'],
            ['kitchenCabinetDrawer'], ['kitchenCabinet', 'kitchenMicrowave']],
    '書房': [['bookcaseClosedWide'], ['desk', 'computerScreen'], ['bookcaseOpen'], ['lampSquareFloor'], ['pottedPlant']],
    '浴室': [['bathroomSink'], ['toilet'], ['washer'], ['bathroomCabinet']]
  };
  var FLOOR_STYLE = { '客廳': 'oak', '書房': 'walnut', '臥室': 'carpet', '廚房': 'tile', '浴室': 'smalltile' };
  var DIRS4 = [[0, -1], [1, 0], [0, 1], [-1, 0]];
  var WALL_H = 0.95, KS = 0.094, FURN_YAW = Math.PI;   // Kenney 家具正面朝 +z → 轉半圈面向房間          // 牆高；Kenney 家具的縮放（模型以 10 為一格）

  async function make3d(L, host, assets) {
    var THREE = L.THREE;
    host.innerHTML = '';
    var renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);
    var bar = document.createElement('div'); bar.className = 'bd-3dbar';
    bar.innerHTML = "<button class='bd-btn' data-cam='follow'>🎥 跟隨</button><button class='bd-btn' data-cam='top'>🗺️ 俯瞰</button>";
    host.appendChild(bar);
    var over = document.createElement('div'); over.className = 'bd-3dover'; host.appendChild(over);

    var scene = new THREE.Scene();
    scene.background = new THREE.Color('#d9e2ea');
    scene.fog = new THREE.Fog('#d9e2ea', 14, 40);
    var pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new L.RoomEnvironment(), 0.04).texture;
    var camera = new THREE.PerspectiveCamera(60, 1.6, 0.05, 120);
    var hemi = new THREE.HemisphereLight(0xfff6ea, 0x8c7a66, 0.5); scene.add(hemi);
    var sun = new THREE.DirectionalLight(0xfff0d8, 1.7);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0005; sun.shadow.normalBias = 0.03;
    scene.add(sun, sun.target);
    var ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshStandardMaterial({ color: '#c9d3da', roughness: 1 }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.06; ground.receiveShadow = true; scene.add(ground);

    // ---------- 程式產生的材質 ----------
    function rnd(seed) { var s = seed % 2147483647; if (s <= 0) s += 2147483646; return function () { s = s * 16807 % 2147483647; return (s - 1) / 2147483646; }; }
    function canvasTex(draw, size, repeat) {
      var c = document.createElement('canvas'); c.width = c.height = size || 512; draw(c.getContext('2d'), c.width);
      var t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.anisotropy = 8; if (repeat) t.repeat.set(repeat, repeat); return t;
    }
    function planks(base, dark, seed) {
      return canvasTex(function (g, S) {
        var r = rnd(seed), rows = 6, h = S / rows;
        g.fillStyle = base; g.fillRect(0, 0, S, S);          // 先鋪底色（避免沒畫到的地方變黑）
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
    function tiles(a, b, n, grout) {
      return canvasTex(function (g, S) {
        var c = S / n, r = rnd(n * 97);
        g.fillStyle = grout; g.fillRect(0, 0, S, S);
        for (var i = 0; i < n; i++) for (var j = 0; j < n; j++) {
          g.fillStyle = shade((i + j) % 2 ? a : b, 0.96 + r() * 0.08); g.fillRect(i * c + 2, j * c + 2, c - 4, c - 4);
        }
      }, 512);
    }
    function carpet(base) {
      return canvasTex(function (g, S) {
        var r = rnd(7); g.fillStyle = base; g.fillRect(0, 0, S, S);
        for (var i = 0; i < 9000; i++) { g.fillStyle = 'rgba(' + (r() < 0.5 ? '0,0,0' : '255,255,255') + ',' + (0.04 + r() * 0.05) + ')'; g.fillRect(r() * S, r() * S, 2, 2); }
      }, 256);
    }
    function plaster() {
      return canvasTex(function (g, S) {
        var r = rnd(3); g.fillStyle = '#f3eee6'; g.fillRect(0, 0, S, S);
        for (var i = 0; i < 4000; i++) { g.fillStyle = 'rgba(120,100,80,' + r() * 0.04 + ')'; g.fillRect(r() * S, r() * S, 3, 3); }
      }, 256);
    }
    function shade(hex, k) {
      var c = new THREE.Color(hex); c.r = Math.min(1, c.r * k); c.g = Math.min(1, c.g * k); c.b = Math.min(1, c.b * k); return '#' + c.getHexString();
    }
    var FLOOR_MATS = {
      oak: new THREE.MeshStandardMaterial({ map: planks('#c89b6a', '#8a6440', 11), roughness: 0.55 }),
      walnut: new THREE.MeshStandardMaterial({ map: planks('#8b5e3c', '#5a3a22', 23), roughness: 0.5 }),
      carpet: new THREE.MeshStandardMaterial({ map: carpet('#b9aecb'), roughness: 1 }),
      tile: new THREE.MeshStandardMaterial({ map: tiles('#f2f2ee', '#dcdcd6', 4, '#b9b5ad'), roughness: 0.25 }),
      smalltile: new THREE.MeshStandardMaterial({ map: tiles('#cfe3ee', '#b8d2e0', 8, '#8fa9b8'), roughness: 0.2 })
    };
    var wallMat = new THREE.MeshStandardMaterial({ map: plaster(), roughness: 0.9 });
    var trimMat = new THREE.MeshStandardMaterial({ color: '#7b5a3c', roughness: 0.6 });
    var capMat = new THREE.MeshStandardMaterial({ color: '#e7dccb', roughness: 0.7 });
    var fogMat = new THREE.MeshBasicMaterial({ color: '#0d0f18' });

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
      var mixer = new THREE.AnimationMixer(model), acts = {};
      src.animations.forEach(function (c) { acts[c.name.split('|').pop().toLowerCase()] = mixer.clipAction(c); });
      var idle = acts.idle || acts.idle_eating || acts.eating || src.animations[0] && mixer.clipAction(src.animations[0]);
      var walk = acts.walk || acts.gallop || acts.run || idle;
      if (idle) idle.play();
      return { g: g, mixer: mixer, idle: idle, walk: walk, target: null, kind: kind };
    }

    // ---------- 程式產生的小物件 ----------
    var M = function (c, r, extra) { var m = new THREE.MeshPhysicalMaterial(Object.assign({ color: c, roughness: r === undefined ? 0.5 : r }, extra || {})); return m; };
    function mesh(geo, mat, y) { var m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; if (y !== undefined) m.position.y = y; return m; }
    function lego(seed) {
      var cols = ['#d62828', '#1d4ed8', '#f4c20d', '#16a34a'], g = new THREE.Group(), mat = M(cols[seed % 4], 0.25, { clearcoat: 0.6 });
      g.add(mesh(new THREE.BoxGeometry(0.18, 0.07, 0.09), mat, 0.035));
      for (var i = 0; i < 4; i++) { var st = mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.02, 12), mat, 0.08); st.position.x = -0.0675 + i * 0.045; g.add(st); }
      g.rotation.y = seed * 0.7; return g;
    }
    function sock() {
      var curve = new THREE.CatmullRomCurve3([new THREE.Vector3(-0.18, 0.04, 0), new THREE.Vector3(0.05, 0.04, 0), new THREE.Vector3(0.12, 0.04, 0.1), new THREE.Vector3(0.14, 0.04, 0.2)]);
      var t = canvasTex(function (g, S) { for (var i = 0; i < 8; i++) { g.fillStyle = i % 2 ? '#f1f1f1' : '#2f6fd6'; g.fillRect(i * S / 8, 0, S / 8, S); } }, 128);
      var g = new THREE.Group(); g.add(mesh(new THREE.TubeGeometry(curve, 24, 0.045, 10), M('#ffffff', 0.9, { map: t })));
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
      var tip = mesh(new THREE.ConeGeometry(0.035, 0.07, 12), mat, 0.18); g.add(tip); return g;
    }
    function puddle() {
      var m = new THREE.Mesh(new THREE.CircleGeometry(0.38, 40), M('#8fc8ea', 0.03, { transparent: true, opacity: 0.6, clearcoat: 1, metalness: 0.1 }));
      m.rotation.x = -Math.PI / 2; m.scale.set(1, 0.7, 1); m.position.y = 0.006; m.receiveShadow = true; return m;
    }
    var dirtMat = M('#6b4f35', 0.95), crumbGeo = new THREE.DodecahedronGeometry(0.035, 0);
    var smudge = canvasTex(function (g, S) { var gr = g.createRadialGradient(S / 2, S / 2, 4, S / 2, S / 2, S / 2); gr.addColorStop(0, 'rgba(90,65,40,.55)'); gr.addColorStop(1, 'rgba(90,65,40,0)'); g.fillStyle = gr; g.fillRect(0, 0, S, S); }, 128);
    function dirt(seed) {
      var r = rnd(seed + 1), g = new THREE.Group();
      var sm = new THREE.Mesh(new THREE.PlaneGeometry(0.75, 0.75), new THREE.MeshStandardMaterial({ map: smudge, transparent: true, depthWrite: false }));
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

    // ---------- 笨笨（掃地機器人）：本地座標 −z＝前方 ----------
    var robot = new THREE.Group();
    var shellProfile = [new THREE.Vector2(0, 0.02), new THREE.Vector2(0.33, 0.02), new THREE.Vector2(0.36, 0.05), new THREE.Vector2(0.365, 0.1),
                        new THREE.Vector2(0.35, 0.135), new THREE.Vector2(0.32, 0.15), new THREE.Vector2(0, 0.15)];
    robot.add(mesh(new THREE.LatheGeometry(shellProfile, 64), M('#24282f', 0.35, { clearcoat: 1, clearcoatRoughness: 0.2 })));
    var lidMat = M('#98c1d9', 0.25, { clearcoat: 1, clearcoatRoughness: 0.1 });
    robot.add(mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.012, 64), lidMat, 0.156));
    var ringMat = new THREE.MeshStandardMaterial({ color: '#38bdf8', emissive: '#38bdf8', emissiveIntensity: 1.6 });
    var ring = new THREE.Mesh(new THREE.TorusGeometry(0.305, 0.006, 8, 96), ringMat); ring.rotation.x = Math.PI / 2; ring.position.y = 0.158; robot.add(ring);
    var lidar = mesh(new THREE.CylinderGeometry(0.065, 0.07, 0.05, 32), M('#1f2329', 0.3, { clearcoat: 1 }), 0.185); lidar.position.z = 0.07; robot.add(lidar);
    var band = new THREE.Mesh(new THREE.CylinderGeometry(0.071, 0.071, 0.012, 32), M('#0f172a', 0.1, { metalness: 0.5 })); band.position.set(0, 0.19, 0.07); robot.add(band);
    var bumper = mesh(new THREE.TorusGeometry(0.362, 0.022, 10, 48, Math.PI * 0.9), M('#3a3f47', 0.6), 0.075);
    bumper.rotation.x = Math.PI / 2; bumper.rotation.z = Math.PI * 1.05; robot.add(bumper);
    var arrowShape = new THREE.Shape(); arrowShape.moveTo(0, -0.2); arrowShape.lineTo(0.09, -0.06); arrowShape.lineTo(0.035, -0.06);
    arrowShape.lineTo(0.035, 0.0); arrowShape.lineTo(-0.035, 0.0); arrowShape.lineTo(-0.035, -0.06); arrowShape.lineTo(-0.09, -0.06); arrowShape.lineTo(0, -0.2);
    var arrow = new THREE.Mesh(new THREE.ShapeGeometry(arrowShape), new THREE.MeshStandardMaterial({ color: '#ffb703', emissive: '#a86b00', emissiveIntensity: 0.6 }));
    arrow.rotation.x = -Math.PI / 2; arrow.position.y = 0.164; robot.add(arrow);
    var brushes = [];
    [-0.2, 0.2].forEach(function (x) {
      var b = new THREE.Group(); b.position.set(x, 0.012, -0.24);
      for (var i = 0; i < 3; i++) { var br = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.004, 0.008), M('#9ca3af', 0.8)); br.rotation.y = i * Math.PI / 3 * 2; br.position.y = 0; b.add(br); }
      robot.add(b); brushes.push(b);
    });
    var headlight = new THREE.SpotLight(0xfff3d6, 0, 5, 0.6, 0.5, 1.2); headlight.position.set(0, 0.2, -0.2);
    headlight.target.position.set(0, 0, -2); robot.add(headlight, headlight.target);
    scene.add(robot);
    function spriteTex(text, bg, fg) {
      return canvasTex(function (g, S) {
        if (bg) { g.fillStyle = bg; g.beginPath(); g.arc(S / 2, S / 2, S / 2 - 6, 0, 7); g.fill(); g.strokeStyle = '#fff'; g.lineWidth = 8; g.stroke(); }
        g.fillStyle = fg || '#222'; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.font = "bold 80px 'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji','PingFang TC',sans-serif"; g.fillText(text, S / 2, S / 2 + 4);
      }, 128);
    }
    var texCache = {};
    function sprite(text, scale, bg, fg) {
      var k = text + bg + fg; texCache[k] = texCache[k] || spriteTex(text, bg, fg);
      var s = new THREE.Sprite(new THREE.SpriteMaterial({ map: texCache[k], depthWrite: false })); s.scale.set(scale, scale, 1); return s;
    }
    var head = sprite(' ', 0.42); head.position.y = 0.75; robot.add(head);

    // ---------- 狀態 ----------
    var staticGroup = new THREE.Group(), dynGroup = new THREE.Group(), roomGroup = new THREE.Group();
    scene.add(staticGroup, dynGroup, roomGroup);
    var staticKey = '', fogBoxes = {}, occluders = [], pets = { cat: [], dog: [] }, prevDirt = {}, sparks = [];
    var target = { x: 0, z: 0, rot: 0 }, first = true, moving = 0, cam = 'follow', yaw = 0.6, dist = 0;
    var center = new THREE.Vector3(), camPos = new THREE.Vector3(), camLook = new THREE.Vector3(), dark = false, thinking = false;

    function buildStatic(st) {
      while (staticGroup.children.length) staticGroup.remove(staticGroup.children[0]);
      fogBoxes = {}; occluders = [];
      var floor = {}, roomOf = {};
      st.tiles.forEach(function (t) { floor[t[0] + ',' + t[1]] = 1; roomOf[t[0] + ',' + t[1]] = t[4]; });
      var tileGeo = new THREE.PlaneGeometry(1, 1);
      function floorTile(x, y, style) {
        var geo = tileGeo.clone(), uv = geo.attributes.uv;
        for (var i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) + x) / 2, (uv.getY(i) - y) / 2);   // 紋理跨格連續
        var m = new THREE.Mesh(geo, FLOOR_MATS[style] || FLOOR_MATS.oak); m.rotation.x = -Math.PI / 2; m.position.set(x, 0, y); m.receiveShadow = true;
        staticGroup.add(m);
      }
      function fogBox(x, y, h) {
        var f = new THREE.Mesh(new THREE.BoxGeometry(1.001, h, 1.001), fogMat); f.position.set(x, h / 2 - 0.01, y); f.visible = false;
        staticGroup.add(f); fogBoxes[x + ',' + y] = f;
      }
      st.tiles.forEach(function (t) { floorTile(t[0], t[1], FLOOR_STYLE[t[4]] || 'oak'); fogBox(t[0], t[1], 0.04); });
      var r = rnd(st.w * 131 + st.h * 17 + st.level.length);
      st.walls.forEach(function (w) {
        var x = w[0], y = w[1], open = [];
        DIRS4.forEach(function (d, i) { if (floor[(x + d[0]) + ',' + (y + d[1])]) open.push(i); });
        if (!open.length) return;
        if (open.length === 1) {               // 靠牆：薄牆在外側，家具靠著它、面向房間
          var d = DIRS4[open[0]], room = roomOf[(x + d[0]) + ',' + (y + d[1])];
          floorTile(x, y, FLOOR_STYLE[room] || 'oak');
          var slab = new THREE.Mesh(new THREE.BoxGeometry(1, WALL_H, 0.12), wallMat.clone());
          var trim = new THREE.Mesh(new THREE.BoxGeometry(1, 0.07, 0.03), trimMat);
          var holder = new THREE.Group(); holder.position.set(x, 0, y); holder.rotation.y = Math.atan2(-d[0], -d[1]);     // 本地 +z＝牆（遠離房間）
          slab.position.set(0, WALL_H / 2, 0.44); trim.position.set(0, 0.035, 0.365); slab.castShadow = slab.receiveShadow = true;
          holder.add(slab, trim);
          var list = ROOM_FURNITURE[room] || ROOM_FURNITURE['客廳'];
          if (r() < 0.62) {
            var pick = list[Math.floor(r() * list.length)], yy = 0;
            pick.forEach(function (name, k) {
              var f = furniture(name); if (!f) return;
              var sz = f.userData.size; f.rotation.y = FURN_YAW; f.position.set(0, yy, 0.38 - sz.z / 2 - 0.01);
              if (k === 0) yy = sz.y * 0.98; holder.add(f);
            });
          }
          staticGroup.add(holder); occluders.push(holder); fogBox(x, y, WALL_H + 0.05);
        } else if (open.length === 2 && (open[0] + 2) % 4 === open[1] % 4 || open.length === 2 && open[0] % 2 === open[1] % 2) {
          // 兩邊都是房間的隔間牆：做成薄牆（像真的室內隔間），底下鋪地板
          var dA = DIRS4[open[0]], roomA = roomOf[(x + dA[0]) + ',' + (y + dA[1])];
          floorTile(x, y, FLOOR_STYLE[roomA] || 'oak');
          var thin = new THREE.Mesh(new THREE.BoxGeometry(1.0, WALL_H, 0.2), wallMat.clone());
          var tcap = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.03, 0.22), capMat);
          var tg = new THREE.Group(); tg.position.set(x, 0, y); tg.rotation.y = dA[0] ? Math.PI / 2 : 0;
          thin.position.y = WALL_H / 2; tcap.position.y = WALL_H + 0.015; thin.castShadow = thin.receiveShadow = true;
          [-1, 1].forEach(function (side) { var tr = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.07, 0.02), trimMat); tr.position.set(0, 0.035, side * 0.11); tg.add(tr); });
          tg.add(thin, tcap); staticGroup.add(tg); occluders.push(tg); fogBox(x, y, WALL_H + 0.05);
        } else {                               // 轉角／T 字：整塊（上面加淺色收邊）
          var b = new THREE.Mesh(new THREE.BoxGeometry(0.98, WALL_H, 0.98), wallMat.clone());
          b.position.set(0, WALL_H / 2, 0); b.castShadow = b.receiveShadow = true;
          var cap = new THREE.Mesh(new THREE.BoxGeometry(1, 0.03, 1), capMat); cap.position.set(0, WALL_H + 0.02, 0);
          var grp = new THREE.Group(); grp.position.set(x, 0, y); grp.add(b, cap); staticGroup.add(grp); occluders.push(grp); fogBox(x, y, WALL_H + 0.1);
        }
      });
      // 每個房間中間鋪一張地毯（裝飾）
      var seenRoom = {};
      st.rooms.forEach(function (rm) {
        if (seenRoom[rm[0]]) return; seenRoom[rm[0]] = 1;
        var rug = furniture(rm[0] === '臥室' ? 'rugRound' : 'rugRectangle'); if (!rug) return;
        rug.position.set(rm[1] - 0.5, 0.003, rm[2] - 0.5); rug.traverse(function (o) { if (o.isMesh) o.castShadow = false; });
        staticGroup.add(rug);
      });
      if (st.home) { var dk = dock(); dk.position.set(st.home[0], 0, st.home[1]); staticGroup.add(dk); }
      center.set((st.w - 1) / 2, 0, (st.h - 1) / 2);
      dist = Math.max(st.w, st.h) * 0.72;
      var span = Math.max(st.w, st.h) * 0.75;
      sun.position.set(center.x - 6, 12, center.z + 4); sun.target.position.copy(center);
      Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 1, far: 40 }); sun.shadow.camera.updateProjectionMatrix();
    }

    function syncPets(kind, spots) {
      var list = pets[kind];
      while (list.length < spots.length) { var p = makePet(kind); if (!p) return; list.push(p); dynGroup.parent.add(p.g); p.g.position.set(spots[list.length - 1][0], 0, spots[list.length - 1][1]); }
      while (list.length > spots.length) { var old = list.pop(); old.g.parent.remove(old.g); }
      list.forEach(function (p, i) { p.target = new THREE.Vector3(spots[i][0], 0, spots[i][1]); });
    }

    function update(st) {
      var key = [st.level, st.w, st.h, st.walls.length, st.tiles.length].join('|');
      if (key !== staticKey) { staticKey = key; buildStatic(st); pets.cat.concat(pets.dog).forEach(function (p) { p.g.parent.remove(p.g); }); pets = { cat: [], dog: [] }; prevDirt = {}; first = true; }
      dark = !!st.dark;
      // 停電：看不到的地方蓋黑色方塊
      var vis = {};
      st.tiles.forEach(function (t) { vis[t[0] + ',' + t[1]] = t[3]; });
      st.walls.forEach(function (w) { vis[w[0] + ',' + w[1]] = w[2]; });
      Object.keys(fogBoxes).forEach(function (k) { fogBoxes[k].visible = dark && !vis[k]; });
      // 動態物件
      while (dynGroup.children.length) dynGroup.remove(dynGroup.children[0]);
      var nowDirt = {};
      st.dirt.forEach(function (d) { var g = dirt(d[0] * 31 + d[1] * 7); g.position.set(d[0], 0, d[1]); dynGroup.add(g); nowDirt[d[0] + ',' + d[1]] = 1; });
      Object.keys(prevDirt).forEach(function (k) { if (!nowDirt[k]) { var p = k.split(','); burst(+p[0], +p[1]); } });
      prevDirt = nowDirt;
      var cats = [], dogs = [];
      st.objects.forEach(function (o, i) {
        var x = o[0], y = o[1], e = o[2], g = null;
        if (e === '🐱') { cats.push([x, y]); return; }
        if (e === '🐶') { dogs.push([x, y]); return; }
        if (e === '🧱') g = lego(x * 7 + y * 3);
        else if (e === '🧦') g = sock();
        else if (e === '➰') g = cable(x * 5 + y);
        else if (e === '💩') g = poop();
        else if (e === '💧') g = puddle();
        if (g) { g.position.set(x, 0, y); dynGroup.add(g); }
      });
      syncPets('cat', cats); syncPets('dog', dogs);
      st.aids.forEach(function (a) {
        var num = /^[0-9]+$/.test(a[2]);
        var bg = num ? '#ffb703' : (a[2] === '左' ? '#3a86ff' : a[2] === '右' ? '#2a9d8f' : '#8d99ae');
        var s = sprite(a[2], 0.3, bg, num ? '#3b2a00' : '#fff'); s.position.set(a[0], 0.16, a[1]); dynGroup.add(s);
      });
      // 禁區：半透明紅色地板＋標示
      while (roomGroup.children.length) roomGroup.remove(roomGroup.children[0]);
      var forb = {};
      st.rooms.forEach(function (rm) { if (rm[3]) forb[rm[0]] = rm; });
      var redMat = new THREE.MeshBasicMaterial({ color: '#ef4444', transparent: true, opacity: 0.22, depthWrite: false });
      st.tiles.forEach(function (t) {
        if (!forb[t[4]] || (dark && !t[3])) return;
        var p = new THREE.Mesh(new THREE.PlaneGeometry(0.98, 0.98), redMat); p.rotation.x = -Math.PI / 2; p.position.set(t[0], 0.008, t[1]); roomGroup.add(p);
      });
      Object.keys(forb).forEach(function (n) { var rm = forb[n], s = sprite('🚫', 0.5); s.position.set(rm[1] - 0.5, 1.25, rm[2] - 0.5); roomGroup.add(s); });
      // 笨笨
      var R = st.robot, want = -R.facing * Math.PI / 2;
      moving = Math.max(moving, Math.abs(R.x - target.x) + Math.abs(R.y - target.z) + Math.abs(want - target.rot) > 0.01 ? 1 : 0);
      target.x = R.x; target.z = R.y; target.rot += Math.atan2(Math.sin(want - target.rot), Math.cos(want - target.rot));
      lidMat.color.set(R.lid); thinking = !!R.thinking;
      ringMat.color.set(R.low ? '#ef4444' : '#38bdf8'); ringMat.emissive.set(R.low ? '#ef4444' : '#38bdf8');
      head.material.map = texCache['h' + (R.thinking ? '🤔' : R.emotion)] || (texCache['h' + (R.thinking ? '🤔' : R.emotion)] = spriteTex(R.thinking ? '🤔' : (R.emotion || ' ')));
      head.material.needsUpdate = true;
      hemi.intensity = dark ? 0.08 : 0.5; sun.intensity = dark ? 0.12 : 1.7; headlight.intensity = dark ? 6 : 0;
      scene.environmentIntensity = dark ? 0.15 : 1;
      over.textContent = st.over === 'clear' ? '🎉 CLEAR!' : (st.over ? '💀 失敗' : '');
      over.style.display = st.over ? 'block' : 'none'; over.style.color = st.over === 'clear' ? '#2a9d8f' : '#d62828';
      if (first) { robot.position.set(target.x, 0, target.z); robot.rotation.y = target.rot; first = false; }
    }

    // 吸乾淨的閃光
    var sparkGeo = new THREE.SphereGeometry(0.02, 6, 4), sparkMat = new THREE.MeshBasicMaterial({ color: '#fff7c2' });
    function burst(x, z) {
      for (var i = 0; i < 18; i++) {
        var s = new THREE.Mesh(sparkGeo, sparkMat); s.position.set(x, 0.1, z);
        s.userData.v = new THREE.Vector3((Math.random() - 0.5) * 0.04, 0.03 + Math.random() * 0.03, (Math.random() - 0.5) * 0.04); s.userData.life = 1;
        scene.add(s); sparks.push(s);
      }
    }

    // 相機操作
    host.addEventListener('click', function (e) { var b = e.target.closest('[data-cam]'); if (b) cam = b.getAttribute('data-cam'); });
    var drag = null, cvs = renderer.domElement;
    cvs.addEventListener('pointerdown', function (e) { drag = e.clientX; });
    cvs.addEventListener('pointermove', function (e) {
      if (drag === null || Math.abs(e.clientX - drag) < 3) return;
      cam = 'top'; yaw -= (e.clientX - drag) * 0.01; drag = e.clientX;
    });
    cvs.addEventListener('pointerup', function () { drag = null; });
    cvs.addEventListener('pointerleave', function () { drag = null; });
    cvs.addEventListener('wheel', function (e) { e.preventDefault(); cam = 'top'; dist = Math.max(4, Math.min(40, dist * (1 + e.deltaY * 0.001))); }, { passive: false });

    var clock = new THREE.Clock(), fwd = new THREE.Vector3(), tmp = new THREE.Vector3();
    function loop() {
      var win = cvs.ownerDocument.defaultView || window;     // 彈出視窗後要用新視窗的 rAF
      win.requestAnimationFrame(loop);
      var dt = Math.min(clock.getDelta(), 0.05);
      if (!cvs.isConnected || cvs.offsetParent === null) return;
      var W = host.clientWidth || 640, H = Math.round(W * 0.6);
      if (cvs.width !== Math.round(W * renderer.getPixelRatio())) { renderer.setSize(W, H); camera.aspect = W / H; camera.updateProjectionMatrix(); }
      var dx = target.x - robot.position.x, dz = target.z - robot.position.z, dr = target.rot - robot.rotation.y;
      robot.position.x += dx * Math.min(1, dt * 8); robot.position.z += dz * Math.min(1, dt * 8); robot.rotation.y += dr * Math.min(1, dt * 9);
      var busy = Math.abs(dx) + Math.abs(dz) + Math.abs(dr) > 0.02;
      brushes.forEach(function (b, i) { b.rotation.y += (i ? -1 : 1) * dt * (busy ? 22 : 3); });
      robot.position.y = busy ? Math.sin(clock.elapsedTime * 30) * 0.003 : 0;
      ringMat.emissiveIntensity = thinking ? 1 + Math.sin(clock.elapsedTime * 6) * 0.9 : 1.6;
      ['cat', 'dog'].forEach(function (k) {
        pets[k].forEach(function (p) {
          if (!p.target) return;
          tmp.subVectors(p.target, p.g.position); var d = tmp.length();
          if (d > 0.03) {
            p.g.position.addScaledVector(tmp, Math.min(1, dt * 2.5));
            p.g.rotation.y = Math.atan2(tmp.x, tmp.z);
            if (p.walk && !p.walk.isRunning()) { if (p.idle) p.idle.stop(); p.walk.play(); }
          } else if (p.idle && !p.idle.isRunning()) { if (p.walk) p.walk.stop(); p.idle.play(); }
          p.mixer.update(dt);
        });
      });
      for (var i = sparks.length - 1; i >= 0; i--) {
        var s = sparks[i]; s.position.add(s.userData.v); s.userData.v.y -= 0.0015; s.userData.life -= dt * 1.4;
        s.scale.setScalar(Math.max(0.01, s.userData.life)); if (s.userData.life <= 0) { scene.remove(s); sparks.splice(i, 1); }
      }
      fwd.set(-Math.sin(robot.rotation.y), 0, -Math.cos(robot.rotation.y));
      var wantPos, wantLook;
      if (cam === 'follow') {   // 第三人稱：跟在笨笨背後，畫面的左右＝笨笨的左右
        wantPos = robot.position.clone().addScaledVector(fwd, -1.7).add(new THREE.Vector3(0, 1.35, 0));
        wantLook = robot.position.clone().addScaledVector(fwd, 1.6).add(new THREE.Vector3(0, 0.15, 0));
      } else {
        wantPos = center.clone().add(new THREE.Vector3(Math.sin(yaw) * dist * 0.62, dist * 0.8, Math.cos(yaw) * dist * 0.62));
        wantLook = center;
      }
      var k = camPos.lengthSq() ? Math.min(1, dt * 5) : 1;
      camPos.lerp(wantPos, k); camLook.lerp(wantLook, k);
      camera.position.copy(camPos); camera.lookAt(camLook);
      // 擋在相機和笨笨中間的牆／家具變透明
      occluders.forEach(function (o) {
        var near = cam === 'follow' && o.position.distanceTo(camPos.clone().setY(0)) < 1.25;
        o.traverse(function (m) {
          if (!m.isMesh) return;
          var mats = Array.isArray(m.material) ? m.material : [m.material];
          mats.forEach(function (mt) { if (mt === trimMat || mt === capMat) return; mt.transparent = near; mt.opacity = near ? 0.18 : 1; mt.depthWrite = !near; });
        });
      });
      renderer.render(scene, camera);
    }
    loop();
    // 除錯用：在瀏覽器 console 可以看場景狀況（root.__bendan3d.info()）
    root.__bendan3d = { scene: scene, camera: camera, info: function () {
      var n = 0; staticGroup.traverse(function (o) { if (o.isMesh) n++; });
      return { cats: pets.cat.length, dogs: pets.dog.length, petSrc: Object.keys(petSrc), furniture: Object.keys(objCache),
               staticMeshes: n, robot: robot.position.toArray(), catPos: pets.cat.map(function (p) { return p.g.position.toArray().concat([p.g.children[0].scale.x]); }) };
    } };
    return { update: update };
  }
