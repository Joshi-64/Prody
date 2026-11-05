/*
 * TreeScene — live ambient tree scenes for a dashboard.
 *
 *   const scene = TreeScene.mount(document.getElementById('hero'), {
 *     scene: 'pine',                // 'pine', 'cherry' or 'picnic'
 *     assets: './assets/',          // folder holding the scene's image files
 *     fit: 'cover',                 // 'cover' (fill, crop) or 'contain' (show all)
 *     focus: [0.5, 0.42],           // which part of the picture stays in view when cropping
 *     onPress: () => {},            // called when the tree is pressed / tapped
 *   });
 *   scene.press();                  // trigger the press effect from code
 *   scene.destroy();
 *
 * Idle motion never repeats: the canopy moves in a soft breeze with the odd
 * gust, clouds drift, and leaves or petals fall now and then. The cherry
 * scene also has a shimmering pond and steam curling off the water.
 * Pressing the tree squashes it (spring), it springs back with a small
 * wobble, the canopy rustles and leaves/petals shake loose.
 * Pauses when hidden or off-screen; honours prefers-reduced-motion
 * (still picture, press still responds). No dependencies. WebGL 1.
 */
(function (global) {
  'use strict';

  var IMG_W = 720, IMG_H = 1280;
  var ART_V = '?v=4';   // bump when scene art / maps / plates change (web_v1 = v2)

  var SCENES = {
    picnic: {
      files: { img: 'tree-scene.webp', plate: 'tree-plate.webp', maps: 'tree-maps.png', fallback: 'tree-fallback.jpg' },
      label: 'A large tree on a meadow at sunset',
      anchor: [365, 900], squashH: 430, split: 700, low: 'tufts', steam: false,
      fill: [0.80, 0.70, 0.84], cloudAmp: 7,
      particle: 'leaf', rim: [470, 668], ground: [872, 942],
      ambient: { first: [4, 10], gap: [8, 20], max: 2 }, burst: [2, 4]
    },
    cherry: {
      files: { img: 'cherry-scene.webp', plate: 'cherry-plate.webp', maps: 'cherry-maps.png', fallback: 'cherry-fallback.jpg' },
      label: 'A cherry blossom tree beside a steaming pond at sunset',
      anchor: [380, 942], squashH: 520, split: 900, low: 'water', steam: true,
      fill: [0.86, 0.72, 0.84], cloudAmp: 8,
      particle: 'petal', rim: [430, 712], ground: [880, 1240],
      ambient: { first: [0.4, 1.4], gap: [1.0, 2.8], max: 7 }, burst: [8, 12]
    },
    pine: {
      files: { img: 'pine-scene.webp', plate: 'pine-plate.webp', maps: 'pine-maps.png', fallback: 'pine-fallback.jpg',
               cones: ['pine-cone.webp'] },   // modelled to match the cones lying in the artwork
      label: 'A tall pine tree on a hillside with a log cabin at sunset',
      anchor: [378, 1112], squashH: 640, split: 650, low: 'tufts', steam: true, steamCol: [0.93, 0.90, 0.94],
      fill: [0.82, 0.70, 0.84], cloudAmp: 8,
      particle: 'needle', rim: [560, 846], ground: [1085, 1210],
      ambient: { first: [5, 10], gap: [9, 20], max: 3 }, burst: [4, 6],   // COO Nov-4: sparse needle sprigs + press cone
      pressExtra: 'cone', coneGround: [1120, 1175]
    }
  };

  var VERT = 'attribute vec2 aPos;void main(){gl_Position=vec4(aPos,0.0,1.0);}';

  var FRAG = [
    'precision highp float;',
    'uniform sampler2D uImg,uPlate,uMaps;',
    'uniform vec2 uRes,uOff,uSpan,uAnchor,uSquash;',
    'uniform float uT,uGust,uShake,uMotion,uCloud,uPlateMix,uSplit,uLowMode,uSteam,uSquashH;',
    'uniform vec3 uFill,uSteamCol;',
    'const vec2 PX=vec2(1.0/720.0,1.0/1280.0);',
    'float hash(vec3 p){p=fract(p*0.3183099+0.1);p*=17.0;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}',
    'float vnoise(vec3 x){vec3 i=floor(x);vec3 f=fract(x);f=f*f*(3.0-2.0*f);',
    ' return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),',
    '            mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}',
    'const float W=0.10471976;',
    'float stm(vec2 px,float t){return vnoise(vec3(px.x/22.0+1.6*sin(px.y/65.0+6.0*W*t),px.y/34.0+t*0.85,t*0.22))*0.65+vnoise(vec3(px.x/10.0,px.y/15.0+t*1.5,t*0.4))*0.35;}',
    'void main(){',
    ' vec2 s=gl_FragCoord.xy/uRes; s.y=1.0-s.y;',
    ' vec2 p=uOff+s*uSpan;',
    ' if(p.x<0.0||p.x>1.0||p.y<0.0||p.y>1.0){gl_FragColor=vec4(uFill,1.0);return;}',
    ' vec2 px=p/PX;',
    // ---- background: drifting clouds above the split; tufts or water below it
    ' vec4 mp=texture2D(uMaps,p);',
    ' float sky=step(p.y,uSplit);',
    ' vec2 bp=p;',
    ' bp.x-=uCloud*mp.b*sky*PX.x;',
    ' float lw=mp.b*(1.0-sky)*uMotion;',
    ' float tuft=lw*(1.0-uLowMode), water=lw*uLowMode;',
    ' bp.x-=tuft*PX.x*4.0*(0.9*uGust+1.3*uGust*sin(20.0*W*uT-p.x*16.0+1.2*sin(6.0*W*uT)));',
    ' bp+=water*PX*2.0*vec2(0.9*sin(px.y/6.5+16.0*W*uT+0.8*sin(px.x/23.0-9.0*W*uT)), 0.5*sin(px.x/11.0-12.0*W*uT));',
    // original pixels everywhere; the rebuilt plate only right behind the tree, and only where it moves
    // (weighted by the local sway below), so pinned roots / trunk base / still edges never show the plate's soft ghost band
    ' float hole=mp.r;',
    ' for(int i=0;i<8;i++){float an=float(i)*0.785398; hole=max(hole,texture2D(uMaps,p+vec2(cos(an),sin(an))*26.0*PX).r);}',
    ' vec3 bg=texture2D(uImg,bp).rgb; vec3 pl=texture2D(uPlate,bp).rgb;',
    // pond: faint travelling glints
    ' float gli=pow(max(0.0,sin(px.y/5.0-11.0*W*uT+3.0*vnoise(vec3(px*0.045+vec2(3.0*cos(W*uT),0.0),3.0*sin(W*uT))))),14.0);',
    ' bg+=water*gli*0.07*vec3(1.0,0.97,0.95);',
    // steam: wisps rising and curling inside the plume zone
    ' float sm=mp.g*(1.0-mp.r)*(1.0-sky)*uSteam*uMotion;',
    ' if(sm>0.001){',
    '  float n=mix(stm(px,uT),stm(px,uT-60.0),uT/60.0);',
    '  float wisp=smoothstep(0.48,0.82,n)*sm;',
    '  bg=mix(bg,uSteamCol,wisp*0.32);',
    ' }',
    // ---- tree layer: undo squash (pivot at trunk base; roots stay planted)
    ' vec2 rel=p-uAnchor;',
    ' float h=clamp(-rel.y*1280.0/uSquashH,0.0,1.0); h=h*h*(3.0-2.0*h);',
    ' vec2 q=uAnchor+vec2(rel.x/mix(1.0,uSquash.x,h), rel.y/uSquash.y);',
    ' vec4 mq=texture2D(uMaps,q);',
    ' float w=mq.g*step(0.004,mq.r);',
    ' float g=uGust;',
    ' vec3 nq=vec3(q*vec2(6.0,9.5)+vec2(4.0*cos(W*uT),0.0),4.0*sin(W*uT));',
    ' float n1=vnoise(nq)-0.5, n2=vnoise(nq+vec3(17.1,3.7,9.2))-0.5;',
    ' float sway=sin(11.0*W*uT+q.y*4.0-q.x*1.5)*0.6+sin(18.0*W*uT+q.x*5.0)*0.25;',
    ' vec2 d;',
    ' d.x=uMotion*w*6.0*(1.6*g + 1.5*sway*g + 2.4*n1*(0.35+g)) + w*uShake*3.2*sin(uT*17.0+q.y*11.0);',
    ' d.y=uMotion*w*6.0*(0.5*sway*g + 1.5*n2*(0.35+g))          + w*uShake*1.8*cos(uT*13.0+q.x*9.0);',
    ' vec2 src=q-d*PX;',
    ' bg=mix(bg,pl,hole*uPlateMix*smoothstep(0.05,0.6,length(d)));',
    ' vec3 tc=texture2D(uImg,src).rgb;',
    ' float a=texture2D(uMaps,src).r;',
    ' if(src.x<0.0||src.x>1.0||src.y<0.0||src.y>1.0) a=0.0;',
    ' gl_FragColor=vec4(mix(bg,tc,a),1.0);',
    '}'
  ].join('\n');

  function loadImage(url) {
    return new Promise(function (res, rej) {
      var im = new Image();
      im.decoding = 'async';
      im.onload = function () { res(im); };
      im.onerror = function () { rej(new Error('Could not load ' + url)); };
      im.src = url;
    });
  }

  // smooth, effectively non-repeating 1-D noise (incommensurate sines)
  function drift(t, seed) {
    return (Math.sin(t * 0.131 + seed) + Math.sin(t * 0.0723 + seed * 2.1) * 0.8 +
            Math.sin(t * 0.0377 + seed * 3.7) * 0.6 + Math.sin(t * 0.211 + seed * 5.3) * 0.3) / 2.7;
  }
  var LOOP = 60, LW = 2 * Math.PI / LOOP;
  function driftL(t, seed, k) {
    return (Math.sin(k[0] * LW * t + seed) + Math.sin(k[1] * LW * t + seed * 2.1) * 0.8 +
            Math.sin(k[2] * LW * t + seed * 3.7) * 0.6 + Math.sin(k[3] * LW * t + seed * 5.3) * 0.3) / 2.7;
  }
  function seeded(n) { var a = (n * 2654435761) >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var x = Math.imul(a ^ (a >>> 15), 1 | a); x ^= x + Math.imul(x ^ (x >>> 7), 61 | x); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; }; }
  var rnd = Math.random;
  function rand(a, b) { return a + rnd() * (b - a); }
  // fixed schedules inside one 60 s loop: [time, strength] gusts; leaf / petal drop times
  var GUSTS = [[2.0, 0.62], [10.5, 0.74], [18.0, 0.55], [26.5, 0.8], [35.0, 0.6], [43.0, 0.72], [51.5, 0.66]];
  var LEAVES = [1.5, 5.8, 9.6, 14.1, 18.4, 22.0, 26.7, 30.9, 34.6, 39.2, 43.5, 47.1, 51.8, 55.9];
  var PETALS = []; LEAVES.forEach(function (t) { PETALS.push(t, (t + 1.3) % LOOP, (t + 2.6) % LOOP); });
  PETALS.sort(function (a, b) { return a - b; });
  var NEEDLES = [4.0, 15.5, 27.0, 38.5, 50.0];
  function crossed(a, b, e) { return b >= a ? (e > a && e <= b) : (e > a || e <= b); }

  function Spring() { this.x = 0; this.v = 0; this.target = 0; this.f = 4; this.z = 0.5; }
  Spring.prototype.step = function (dt) {
    var w = 2 * Math.PI * this.f, k = w * w, c = 2 * this.z * w;
    var n = Math.max(1, Math.ceil(dt / 0.004)), h = dt / n;
    for (var i = 0; i < n; i++) { this.v += (-k * (this.x - this.target) - c * this.v) * h; this.x += this.v * h; }
  };

  // ---------- particle art ----------
  function leafSprites() {
    var shades = [
      [[196, 198, 138], [150, 160, 98], [104, 120, 66]],
      [[176, 182, 120], [132, 146, 86], [88, 106, 56]],
      [[158, 168, 106], [116, 132, 74], [78, 96, 50]]
    ];
    return shades.map(function (sh) {
      var S = 128, c = document.createElement('canvas'); c.width = c.height = S;
      var x = c.getContext('2d');
      x.translate(S / 2, S / 2 + 6);
      var lobes = [[0, -30, 17], [-24, -16, 15], [24, -16, 15], [-20, 10, 13], [20, 10, 13]];
      x.beginPath();
      x.arc(0, -4, 22, 0, Math.PI * 2);
      lobes.forEach(function (l) { x.moveTo(l[0] + l[2], l[1]); x.arc(l[0], l[1], l[2], 0, Math.PI * 2); });
      x.save(); x.clip();
      var gr = x.createRadialGradient(-6, -14, 4, 0, -4, 44);
      gr.addColorStop(0, 'rgb(' + sh[0] + ')'); gr.addColorStop(0.55, 'rgb(' + sh[1] + ')'); gr.addColorStop(1, 'rgb(' + sh[2] + ')');
      x.fillStyle = gr; x.fillRect(-64, -70, 128, 128);
      var sh2 = x.createLinearGradient(0, -40, 0, 26);
      sh2.addColorStop(0, 'rgba(255,250,220,0.10)'); sh2.addColorStop(1, 'rgba(40,52,24,0.22)');
      x.fillStyle = sh2; x.fillRect(-64, -70, 128, 128);
      x.strokeStyle = 'rgba(92,108,58,0.55)'; x.lineWidth = 2; x.lineCap = 'round';
      x.beginPath();
      lobes.forEach(function (l) { x.moveTo(0, 8); x.quadraticCurveTo(l[0] * 0.45, l[1] * 0.45 + 4, l[0] * 0.85, l[1] * 0.85); });
      x.stroke();
      x.restore();
      x.strokeStyle = 'rgb(110,92,58)'; x.lineWidth = 3.2; x.lineCap = 'round';
      x.beginPath(); x.moveTo(0, 12); x.quadraticCurveTo(2, 22, -1, 30); x.stroke();
      return c;
    });
  }

  function petalSprites() {
    // soft sakura petal: rounded body, small notch at the tip, deeper pink toward the base
    var shades = [
      [[252, 214, 220], [245, 172, 181], [226, 140, 152]],
      [[248, 200, 208], [237, 159, 167], [214, 128, 140]],
      [[253, 222, 226], [240, 176, 186], [222, 146, 158]]
    ];
    return shades.map(function (sh) {
      var S = 128, c = document.createElement('canvas'); c.width = c.height = S;
      var x = c.getContext('2d');
      x.translate(S / 2, S / 2);
      x.beginPath();
      x.moveTo(0, 30);
      x.bezierCurveTo(-30, 12, -26, -26, -7, -28);
      x.quadraticCurveTo(0, -20, 7, -28);
      x.bezierCurveTo(26, -26, 30, 12, 0, 30);
      x.closePath();
      x.save(); x.clip();
      var gr = x.createLinearGradient(0, -30, 0, 30);
      gr.addColorStop(0, 'rgb(' + sh[0] + ')'); gr.addColorStop(0.5, 'rgb(' + sh[1] + ')'); gr.addColorStop(1, 'rgb(' + sh[2] + ')');
      x.fillStyle = gr; x.fillRect(-64, -64, 128, 128);
      var hl = x.createRadialGradient(-8, -10, 2, -6, -6, 24);
      hl.addColorStop(0, 'rgba(255,245,246,0.45)'); hl.addColorStop(1, 'rgba(255,245,246,0)');
      x.fillStyle = hl; x.fillRect(-64, -64, 128, 128);
      x.strokeStyle = 'rgba(205,120,135,0.35)'; x.lineWidth = 1.4;
      x.beginPath(); x.moveTo(0, 26); x.quadraticCurveTo(-2, 4, 0, -16); x.stroke();
      x.restore();
      return c;
    });
  }

  function needleSprites() {
    // a small sprig of three needles, olive like the boughs
    return [[96, 92, 44], [84, 80, 38], [110, 104, 54]].map(function (col) {
      var S = 128, c = document.createElement('canvas'); c.width = c.height = S;
      var x = c.getContext('2d');
      x.translate(S / 2, S / 2); x.lineCap = 'round';
      x.strokeStyle = 'rgb(' + col + ')'; x.lineWidth = 5;
      [[-0.32, 40], [0.02, 46], [0.34, 38]].forEach(function (n) {
        x.beginPath(); x.moveTo(0, 22); x.lineTo(Math.sin(n[0]) * n[1], 22 - Math.cos(n[0]) * n[1]); x.stroke();
      });
      x.strokeStyle = 'rgba(255,240,200,0.25)'; x.lineWidth = 1.6;
      x.beginPath(); x.moveTo(0, 20); x.lineTo(0, -20); x.stroke();
      x.strokeStyle = 'rgb(96,64,40)'; x.lineWidth = 6; x.beginPath(); x.moveTo(0, 22); x.lineTo(0, 30); x.stroke();
      return c;
    });
  }

  function coneSprites() {
    // pine cone: rows of overlapping rounded scales, warm brown with lit tips
    return [0, 1].map(function (v) {
      var S = 128, c = document.createElement('canvas'); c.width = c.height = S;
      var x = c.getContext('2d');
      x.translate(S / 2, S / 2 + 4);
      x.fillStyle = 'rgb(70,42,26)';
      x.beginPath(); x.ellipse(0, 0, 24, 38, 0, 0, Math.PI * 2); x.fill();
      for (var row = 0; row < 7; row++) {
        var y = -30 + row * 10, wRow = 24 * Math.sin((row + 0.8) / 7.6 * Math.PI);
        var n = Math.max(2, Math.round(wRow / 8)) + (v ? 1 : 0);
        for (var i = 0; i < n; i++) {
          var sx = -wRow + (i + 0.5) * (2 * wRow / n) + (row % 2 ? 3 : -3);
          var g = x.createLinearGradient(sx, y - 6, sx, y + 8);
          g.addColorStop(0, 'rgb(176,112,66)'); g.addColorStop(0.6, 'rgb(136,80,46)'); g.addColorStop(1, 'rgb(92,54,32)');
          x.fillStyle = g;
          x.beginPath(); x.ellipse(sx, y + 2, 7.5, 6.5, 0, 0, Math.PI * 2); x.fill();
          x.fillStyle = 'rgba(232,186,140,0.55)';
          x.beginPath(); x.ellipse(sx, y + 6, 4, 1.8, 0, 0, Math.PI * 2); x.fill();
        }
      }
      x.strokeStyle = 'rgb(90,60,36)'; x.lineWidth = 4; x.lineCap = 'round';
      x.beginPath(); x.moveTo(0, -36); x.lineTo(1, -44); x.stroke();
      return c;
    });
  }

  function mount(container, opts) {
    opts = opts || {};
    var S = SCENES[opts.scene || 'picnic'];
    if (!S) throw new Error('TreeScene: unknown scene "' + opts.scene + '"');
    var base = (opts.assets || './assets/').replace(/\/?$/, '/');
    var fit = opts.fit || 'cover';
    var focus = opts.focus || [0.5, 0.42];
    var interactive = opts.interactive !== false;
    var label = opts.label || S.label;
    var reduced = global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var isPetal = S.particle === 'petal', isNeedle = S.particle === 'needle';

    if (getComputedStyle(container).position === 'static') container.style.position = 'relative';
    container.style.overflow = 'hidden';
    var gl_c = document.createElement('canvas');
    var lf_c = document.createElement('canvas');
    [gl_c, lf_c].forEach(function (c) {
      c.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;';
      container.appendChild(c);
    });
    lf_c.style.pointerEvents = 'none';

    var gl = gl_c.getContext('webgl', { antialias: false, premultipliedAlpha: false, alpha: false }) ||
             gl_c.getContext('experimental-webgl');
    var api = { destroy: function () {}, press: function () {}, ready: null };
    var destroyed = false;

    function fallback() {
      gl_c.remove();
      var img = document.createElement('img');
      img.src = base + S.files.fallback + ART_V; img.alt = label;
      img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:' + fit + ';object-position:' +
        (focus[0] * 100) + '% ' + (focus[1] * 100) + '%;';
      container.insertBefore(img, lf_c);
      if (interactive && opts.onPress) img.addEventListener('click', function () { opts.onPress(); });
    }
    if (!gl) { fallback(); api.ready = Promise.resolve(api); return api; }

    function sh(type, src) {
      var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    }
    var prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog); gl.useProgram(prog);
    var buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var aPos = gl.getAttribLocation(prog, 'aPos'); gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    var U = {};
    ['uImg', 'uPlate', 'uMaps', 'uRes', 'uOff', 'uSpan', 'uAnchor', 'uSquash', 'uT', 'uGust', 'uShake', 'uMotion',
     'uCloud', 'uPlateMix', 'uSplit', 'uLowMode', 'uSteam', 'uSquashH', 'uFill', 'uSteamCol']
      .forEach(function (n) { U[n] = gl.getUniformLocation(prog, n); });

    function tex(unit, im) {
      var t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    }

    // ---------- state ----------
    var W = 1, H = 1, dpr = 1, off = [0, 0], span = [1, 1];
    var t0 = performance.now(), last = t0, raf = 0, running = false, visible = true;
    var gust = 0.5, gustKick = 0, nextGustAt = rand(6, 16);
    var squash = new Spring(), shake = 0, pressing = false, pressStart = 0, asleep = false;
    var bits = [], nextBitAt = rand(S.ambient.first[0], S.ambient.first[1]), spawnPts = [], hit = null;
    var sprites = isPetal ? petalSprites() : isNeedle ? needleSprites() : leafSprites();
    var cones = S.pressExtra === 'cone' ? coneSprites() : null;
    var lctx = lf_c.getContext('2d');

    function layout() {
      var r = container.getBoundingClientRect();
      dpr = Math.min(global.devicePixelRatio || 1, 2);
      W = Math.max(1, Math.round(r.width * dpr)); H = Math.max(1, Math.round(r.height * dpr));
      gl_c.width = lf_c.width = W; gl_c.height = lf_c.height = H;
      var ca = r.width / Math.max(1, r.height), ia = IMG_W / IMG_H;
      if ((fit === 'cover') === (ca > ia)) { span = [1, ia / ca]; } else { span = [ca / ia, 1]; }
      off = [focus[0] - span[0] / 2, focus[1] - span[1] / 2];
      if (fit === 'cover') {
        off[0] = Math.min(Math.max(off[0], 0), 1 - span[0]);
        off[1] = Math.min(Math.max(off[1], 0), 1 - span[1]);
      } else { off = [0.5 - span[0] / 2, 0.5 - span[1] / 2]; }
      gl.viewport(0, 0, W, H);
      if (!running) draw(performance.now());
      container.dispatchEvent(new CustomEvent('treelayout', { bubbles: false }));
    }

    function toImg(cx, cy) {
      var r = container.getBoundingClientRect();
      return [(off[0] + (cx / r.width) * span[0]) * IMG_W, (off[1] + (cy / r.height) * span[1]) * IMG_H];
    }
    function onTree(ix, iy) {
      if (!hit || ix < 0 || iy < 0 || ix >= IMG_W || iy >= IMG_H) return false;
      return hit[(Math.floor(iy) * IMG_W + Math.floor(ix)) * 4] > 127;
    }

    // ---------- falling leaves / petals ----------
    function spawn(near) {
      var pool = spawnPts;
      if (near) {
        pool = spawnPts.slice().sort(function (a, b) {
          return Math.abs(a[0] - near[0]) - Math.abs(b[0] - near[0]);
        }).slice(0, isPetal ? 60 : 28);
      }
      var p = pool[(rnd() * pool.length) | 0];
      if (!p) return;
      var b = {
        x: p[0], y: p[1], x0: p[0], age: 0, landed: -1, rot: 0, sx: 1, alpha: 0,
        ph: rand(0, 6.28), ground: rand(S.ground[0], S.ground[1]),
        sprite: sprites[(rnd() * sprites.length) | 0]
      };
      if (isNeedle) {
        b.vy = rand(40, 60) + (near ? 15 : 0); b.amp = rand(6, 14); b.w = rand(1.6, 2.6);
        b.flip = rand(1.5, 3.0); b.spin = rand(-2.4, 2.4); b.size = rand(24, 30); b.wind = rand(10, 18);
      } else if (isPetal) {
        b.vy = rand(30, 46) + (near ? 10 : 0); b.amp = rand(10, 24); b.w = rand(1.4, 2.4);
        b.flip = rand(3.0, 5.5); b.spin = rand(-1.6, 1.6); b.size = rand(25, 33); b.wind = rand(14, 26);
      } else {
        b.vy = rand(24, 38) + (near ? 10 : 0); b.amp = rand(18, 40); b.w = rand(1.2, 2.0);
        b.flip = rand(2.2, 3.8); b.spin = 0; b.size = rand(36, 46); b.wind = 9;
      }
      bits.push(b);
    }

    function spawnCone(near) {
      if (!cones) return;
      var landed = bits.filter(function (b) { return b.kind === 'cone'; });
      if (landed.length >= 3) bits.splice(bits.indexOf(landed[0]), 1);  // keep at most three cones on the grass
      var pool = spawnPts.slice().sort(function (a, b) {
        return Math.abs(a[0] - (near ? near[0] : 378)) - Math.abs(b[0] - (near ? near[0] : 378));
      }).slice(0, 30);
      var p = pool[(rnd() * pool.length) | 0]; if (!p) return;
      var spr = cones[(Math.random() * cones.length) | 0];
      var nw = spr.naturalWidth || 40, nh = spr.naturalHeight || 46, k = Math.min(1, 46 / nh);  // cone art is ~185px; draw at grass-cone size
      var cw = Math.round(nw * k), ch = Math.round(nh * k);
      bits.push({ kind: 'cone', x: p[0], y: p[1] - 6, vx: rand(-25, 25), vy: rand(-20, 10), age: 0, landed: -1,
        rot: rand(-0.4, 0.4), spin: rand(2.5, 4.5) * (Math.random() < 0.5 ? -1 : 1), sx: Math.random() < 0.5 ? -1 : 1,
        alpha: 1, w: cw, h: ch, bounces: 0, ground: rand(S.coneGround[0], S.coneGround[1]), sprite: spr });
    }

    function updateBits(dt) {
      for (var i = bits.length - 1; i >= 0; i--) {
        var L = bits[i]; L.age += dt;
        if (L.kind === 'cone') {
          var rest = L.ground - L.h / 2;
          if (L.landed < 0) {
            L.vy += 1150 * dt; L.x += L.vx * dt; L.y += L.vy * dt;
            L.rot += L.spin * dt * (L.bounces ? 0.5 : 1);                 // tumbles on the way down
            if (L.y >= rest) {
              L.y = rest;
              if (L.vy > 140 && L.bounces < 3) { L.vy *= -0.36; L.vx = L.vx * 0.6 + rand(-25, 25); L.spin *= 0.5; L.bounces++; }
              else { L.vy = 0; L.landed = L.age; }
            }
          } else {
            // comes to rest standing upright, like the cones already in the grass
            L.vx *= Math.pow(0.02, dt); L.x += L.vx * dt;
            var upright = Math.round(L.rot / (2 * Math.PI)) * 2 * Math.PI;
            L.rot += (upright - L.rot) * Math.min(1, dt * 7);
            var sinceC = L.age - L.landed;
            if (sinceC > 6) L.alpha = Math.max(0, 1 - (sinceC - 6) / 1.5);
            if (L.alpha <= 0) { bits.splice(i, 1); continue; }
          }
          continue;
        }
        if (L.landed < 0) {
          var flutter = Math.sin(L.age * L.w + L.ph);
          L.y += (L.vy * (0.75 + 0.35 * Math.abs(flutter))) * dt;
          L.x0 += gust * L.wind * dt;
          L.x = L.x0 + L.amp * flutter;
          L.rot = (isPetal || isNeedle) ? L.rot + L.spin * dt + 0.02 * flutter
                          : 0.65 * Math.sin(L.age * L.w + L.ph + 0.6) + 0.15 * Math.sin(L.age * 3.1);
          L.sx = Math.cos(L.age * L.flip + L.ph);
          L.alpha = Math.min(1, L.age / 0.6);
          if (L.y >= L.ground) { L.y = L.ground; L.landed = L.age; L.sx = L.sx < 0 ? -0.85 : 0.85; }
        } else {
          var since = L.age - L.landed;
          if (!isPetal && !isNeedle) L.rot *= Math.pow(0.02, dt);
          if (since > 3.5) L.alpha = Math.max(0, 1 - (since - 3.5) / 1.6);
          if (L.alpha <= 0) { bits.splice(i, 1); continue; }
        }
        if (L.x < -60 || L.x > IMG_W + 60) bits.splice(i, 1);
      }
    }

    function drawBits() {
      lctx.setTransform(1, 0, 0, 1, 0, 0);
      lctx.clearRect(0, 0, W, H);
      if (!bits.length) return;
      var scx = W / (span[0] * IMG_W), scy = H / (span[1] * IMG_H);
      for (var i = 0; i < bits.length; i++) {
        var L = bits[i];
        if (L.kind === 'cone') {
          var gx = (L.x - off[0] * IMG_W) * scx, gy = (L.ground - off[1] * IMG_H) * scy;
          var near = Math.max(0, 1 - (L.ground - (L.y + L.h / 2)) / 160);
          lctx.setTransform(1, 0, 0, 1, 0, 0);
          lctx.globalAlpha = L.alpha * near * 0.32;
          lctx.fillStyle = 'rgb(46,42,12)';
          lctx.beginPath(); lctx.ellipse(gx, gy - 1 * scy, L.w * 0.5 * scx, L.w * 0.13 * scy, 0, 0, Math.PI * 2); lctx.fill();
          lctx.globalAlpha = L.alpha;
          lctx.setTransform(scx * L.sx, 0, 0, scy, (L.x - off[0] * IMG_W) * scx, (L.y - off[1] * IMG_H) * scy);
          lctx.rotate(L.rot * L.sx);
          lctx.drawImage(L.sprite, -L.w / 2, -L.h / 2, L.w, L.h);
          continue;
        }
        // petals grow a little as they fall toward the viewer (ground perspective)
        var persp = (isPetal && L.kind !== 'cone') ? 0.8 + 0.55 * Math.min(1, Math.max(0, (L.y - 600) / 640)) : 1;
        var x = (L.x - off[0] * IMG_W) * scx, y = (L.y - off[1] * IMG_H) * scy, s = L.size * persp * scx / 128;
        lctx.globalAlpha = L.alpha;
        lctx.setTransform(s * L.sx, 0, 0, s, x, y);
        lctx.rotate(L.rot);
        lctx.drawImage(L.sprite, -64, -64);
      }
      lctx.globalAlpha = 1;
    }

    function draw(now) {
      var t = (now - t0) / 1000;
      var sq = squash.x;
      gl.uniform2f(U.uRes, W, H);
      gl.uniform2f(U.uOff, off[0], off[1]);
      gl.uniform2f(U.uSpan, span[0], span[1]);
      gl.uniform2f(U.uAnchor, S.anchor[0] / IMG_W, S.anchor[1] / IMG_H);
      gl.uniform2f(U.uSquash, 1 + 0.032 * sq, 1 - 0.05 * sq);
      gl.uniform1f(U.uSquashH, S.squashH);
      gl.uniform1f(U.uT, t % LOOP);
      gl.uniform1f(U.uGust, gust);
      gl.uniform1f(U.uShake, shake);
      gl.uniform1f(U.uMotion, reduced ? 0 : 1);
      gl.uniform1f(U.uPlateMix, reduced ? Math.min(1, Math.abs(sq) * 40 + shake * 8) : 1);
      gl.uniform1f(U.uCloud, reduced ? 0 : 42 * driftL(t, 1.7, [2, 1, 1, 3]) + 18);
      gl.uniform1f(U.uSplit, S.split / IMG_H);
      gl.uniform1f(U.uLowMode, S.low === 'water' ? 1 : 0);
      gl.uniform1f(U.uSteam, S.steam ? 1 : 0);
      gl.uniform3f(U.uFill, S.fill[0], S.fill[1], S.fill[2]);
      var sc = S.steamCol || [0.985, 0.955, 0.95];
      gl.uniform3f(U.uSteamCol, sc[0], sc[1], sc[2]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      drawBits();
    }

    function frame(now) {
      if (destroyed) return;
      var dt = Math.min(0.05, (now - last) / 1000); last = now;
      var t = (now - t0) / 1000;
      if (!reduced) {
        var tl = t % LOOP, pl = (t - dt + LOOP) % LOOP;
        for (var gi = 0; gi < GUSTS.length; gi++) if (crossed(pl, tl, GUSTS[gi][0])) gustKick = GUSTS[gi][1];
        gustKick *= Math.pow(0.82, dt);
        var target = 0.42 + 0.22 * driftL(t, 0.3, [1, 1, 1, 2]) + gustKick;
        gust += (target - gust) * Math.min(1, dt * 0.9);
        var isPetal = S.particle === 'petal', isNeedle = S.particle === 'needle';
        var sched = isPetal ? PETALS : isNeedle ? NEEDLES : LEAVES;
        for (var li = 0; li < sched.length; li++) if (crossed(pl, tl, sched[li])) {
          rnd = seeded(li + 1); if (bits.length < S.ambient.max + 2) spawn(); rnd = Math.random;
        }
      }
      updateBits(dt);
      squash.step(dt);
      shake *= Math.pow(0.12, dt);
      draw(now);
      raf = requestAnimationFrame(frame);
    }

    function start() { if (running || destroyed || asleep || !visible || document.hidden) return; running = true; last = performance.now(); raf = requestAnimationFrame(frame); }
    function stop() { running = false; cancelAnimationFrame(raf); }

    // ---------- interaction ----------
    function down() {
      pressing = true; pressStart = performance.now();
      squash.target = 1; squash.f = 7; squash.z = 0.9;
      if (!running) start();
    }
    function up(ix, iy) {
      if (!pressing) return;
      pressing = false;
      var held = performance.now() - pressStart;
      function release() {
        squash.target = 0; squash.f = 3.4; squash.z = 0.3;
        if (!reduced) {
          shake = 1;
          var n = Math.round(rand(S.burst[0], S.burst[1]));
          for (var i = 0; i < n; i++) spawn(ix != null ? [ix, iy] : null);
          if (S.pressExtra === 'cone') spawnCone(ix != null ? [ix, iy] : null);
        }
        if (opts.onPress) opts.onPress();
        container.dispatchEvent(new CustomEvent('treepress', { bubbles: true, detail: { scene: opts.scene || 'picnic', x: ix, y: iy } }));
      }
      if (held < 90) setTimeout(release, 90 - held); else release();
    }

    function local(e) { var r = container.getBoundingClientRect(); return toImg(e.clientX - r.left, e.clientY - r.top); }
    function onDown(e) {
      var p = local(e); if (!onTree(p[0], p[1])) return;
      e.preventDefault(); try { gl_c.setPointerCapture(e.pointerId); } catch (_) {}
      down();
    }
    function onUp(e) { if (!pressing) return; var p = local(e); up(p[0], p[1]); }
    function onCancel() { if (pressing) up(null, null); }
    function onMove(e) {
      if (e.pointerType !== 'mouse') return;
      var p = local(e); gl_c.style.cursor = onTree(p[0], p[1]) ? 'pointer' : '';
    }
    function onKey(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault(); if (!pressing) { down(); setTimeout(function () { up(); }, 140); }
      }
    }

    if (interactive) {
      gl_c.style.touchAction = 'manipulation';
      gl_c.addEventListener('pointerdown', onDown);
      gl_c.addEventListener('pointerup', onUp);
      gl_c.addEventListener('pointercancel', onCancel);
      gl_c.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') onCancel(); });
      gl_c.addEventListener('pointermove', onMove);
      gl_c.tabIndex = 0;
      gl_c.setAttribute('role', 'button');
      gl_c.setAttribute('aria-label', label);
      gl_c.style.outline = 'none';
      gl_c.addEventListener('keydown', onKey);
    } else {
      gl_c.setAttribute('role', 'img');
      gl_c.setAttribute('aria-label', label);
    }

    var ro = new ResizeObserver(layout);
    var io = global.IntersectionObserver ? new IntersectionObserver(function (es) {
      visible = es[0].isIntersecting; if (visible) start(); else stop();
    }) : null;
    function onVis() { if (document.hidden) stop(); else start(); }

    api.press = function () { down(); setTimeout(function () { up(); }, 140); };
    // stop drawing while something opaque covers the scene (e.g. the Branches view); wake resumes the loop
    api.sleep = function (on) { asleep = !!on; if (asleep) stop(); else start(); };
    // image px (720x1280 artwork) -> container CSS px, honouring the current cover/contain crop
    api.toScreen = function (ix, iy) {
      var r = container.getBoundingClientRect();
      return [(ix / IMG_W - off[0]) / span[0] * r.width, (iy / IMG_H - off[1]) / span[1] * r.height];
    };
    api.pxPerImagePx = function () { return container.getBoundingClientRect().width / (span[0] * IMG_W); };
    api.squash = function () { return squash.x; };          // 0 rest, 1 fully pressed, <0 springing past rest
    api.gust = function () { return gust; };                // 0.2..1.2 breeze strength right now
    api.anchor = function () { return S.anchor.slice(); };  // trunk base in image px (squash pivot)
    api.isOnTree = function (ix, iy) { return onTree(ix, iy); };
    api.destroy = function () {
      destroyed = true; stop(); ro.disconnect(); if (io) io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      gl_c.remove(); lf_c.remove();
      var ext = gl.getExtension('WEBGL_lose_context'); if (ext) ext.loseContext();
    };

    var coneFiles = S.files.cones || [];
    api.ready = Promise.all([
      loadImage(base + S.files.img + ART_V), loadImage(base + S.files.plate + ART_V), loadImage(base + S.files.maps + ART_V)
    ].concat(coneFiles.map(function (f) { return loadImage(base + f).catch(function () { return null; }); })))
    .then(function (ims) {
      if (destroyed) return api;
      var real = ims.slice(3).filter(Boolean);
      if (real.length) cones = real;
      tex(0, ims[0]); tex(1, ims[1]); tex(2, ims[2]);
      gl.uniform1i(U.uImg, 0); gl.uniform1i(U.uPlate, 1); gl.uniform1i(U.uMaps, 2);
      var c = document.createElement('canvas'); c.width = IMG_W; c.height = IMG_H;
      var x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(ims[2], 0, 0);
      hit = x.getImageData(0, 0, IMG_W, IMG_H).data;
      // things detach from the underside/edge of the canopy, where they're visible as they fall
      for (var yy = S.rim[0]; yy < S.rim[1]; yy += 4) for (var xx = 30; xx < 700; xx += 4) {
        var k = (yy * IMG_W + xx) * 4, kb = ((yy + 22) * IMG_W + xx) * 4;
        if (hit[k] > 240 && hit[k + 1] > 40 && hit[kb] < 20) spawnPts.push([xx, yy]);
      }
      ro.observe(container); if (io) io.observe(container);
      document.addEventListener('visibilitychange', onVis);
      layout(); start();
      container.dispatchEvent(new CustomEvent('treeready', { bubbles: true }));
      return api;
    }).catch(function (err) { console.warn('[TreeScene]', err); fallback(); return api; });

    return api;
  }

  SCENES.oak = SCENES.picnic;   // Prody calls the picnic oak scene 'oak'
  global.TreeScene = { mount: mount, scenes: Object.keys(SCENES) };
})(typeof window !== 'undefined' ? window : this);
