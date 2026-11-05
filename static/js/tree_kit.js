/* Prody dashboard tree renderer v3 (oak_kit_v3_6f: real stage art, per-slot rot bakes, root chains). Places/scales/stretches oak kit pieces from kit.json only (no hardcoded coords,
   no shading in code). Data: GET /api/tree (contract v0.5); ?tree_sample=... forces a sample. */
(function(){
/* r3: flower art drawn as SVG; petals take the branch dot colour (--d, same value as the chip dot), stem stays green */
function tkFlowerSVG(kind){var P='style="fill:var(--dp,var(--d))"',C='<circle cx="12" cy="9" r="2.6" fill="#FFE3A3" stroke="rgba(0,0,0,.18)" stroke-width=".6"/>',ST='<path d="M12 13v10M12 19l4-2" stroke="#5E8A4A" stroke-width="2" stroke-linecap="round" fill="none"/>',H;
  /* r7g: one flower shape for every item and user: the demo tree's tinted tulip (star + 5-circle shapes removed) */
  H='<path '+P+' stroke="rgba(0,0,0,.22)" stroke-width=".7" d="M5.5 5.5c0 5 2.5 8 6.5 8s6.5-3 6.5-8l-3.2 2.4L12 3 8.7 7.9z"/>';
  /* r7d: 1.5px warm cream rim (#FFF6E6 @80%) on the petal shape: an underlay copy stroked 3px so only 1.5px shows outside the fill (no inner seams); fill stays --d */
  var shape=H.replace(C,''),rim=shape.replace(P,'class="tk-rim" style="fill:#FFF6E6"').replace(/stroke="rgba\(0,0,0,\.22\)" stroke-width="\.7"/,'stroke="#FFF6E6" stroke-width="3" stroke-linejoin="round"');
  return '<svg class="tk-fla" viewBox="0 0 24 24" aria-hidden="true">'+ST+'<g class="tk-rimg" opacity=".8">'+rim+'</g>'+H+'</svg>';}

'use strict';
var BASE='/static/img/oak_kit/', AV=window.__AV||{}, V='?v='+(AV['img/oak_kit']||'5'), SV='?v='+(AV['img/soil_v1f']||'5'), IMG=function(f){return window.__noWebp?f:f.replace(/\.png$/,'.webp');}/* perf_r1: WebP art (scripts/build_webp.py), PNG when the base.html probe says no WebP (Safari<14); ?v= = content hash of the kit dir */, FLOWER_SCALE=1, CLUMP_SCALE=1.12, CROWN_PULL=[0.9,0.62], ROT_LIMIT=15,MINH0=410, HIT=44, CROWN_S1=1/* r7b: stage-1 keeps the kit's natural trunk:crown proportions */, SKY_S1=0.5/* r7b: stage-1 sapling drawn smaller (uniform), sky fills the extra phone height */, ZOOM_TOP=24/* r8: phone sapling crown top this far below the stage top */, TBG_PX=70/* r7: base moss drawn ~70px tall on screen at any tree size */;
/* v1r (Lumen kit_2d_v1r): ALL new art paths live here. v1s crown swap = change ART.base (and add ART.crown) only. */
var ART={base:'/static/img/kit_v1s_b/'/* ONE kit path: v1s_b swap = change this only */,v:'?v=1',
  trunkRoots:{file:'trunk/trunk_roots_v1r',size:[350,434],anchor:[180.8,200.9],tips:[[87.0,246.6],[292.8,408.5],[29.8,392.8],[69.9,251.8],[245.5,293.5],[49.5,288.3],[173.4,377.6],[219.1,409.2]]},
  tiles:{sky:'background/sky_tile_v1r',soil:'background/soil_tile_v1r',grass:'background/grass_tile_v1s'},
  soilLine:521,crown:{file:'crown/crown_A_v1s',size:[360,250],centreY:252.5,zone:{cy:242.5,rx:133.2,ry:78.6},mask:["000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000111000000000000000000000000000000000000000","000000000000000000000000000001111100000000000000000000000000000000000000","000000000000000000000000000011111110000000000000000000000000000000000000","000000000000000000000000000011111111100000010000000000000000000000000000","000000000000000000000000000111111111111111111000000000000000000000000000","000000000000000000000000001111111111111111111100000000000000000000000000","000000000000000000000000011111111111111111111110000000000000000000000000","000000000000000000000000011111111111111111111110000000000000000000000000","000000000000000000001111111111111111111111111111111100000000000000000000","000000000000000000011111111111111111111111111111111110000000000000000000","000000000000000001111111111111111111111111111111111111100000000000000000","000000000000000011111111111111111111111111111111111111110000000000000000","000000000000000111111111111111111111111111111111111111111000000000000000","000000000000000111111111111111111111111111111111111111111000000000000000","000000000000001111111111111111111111111111111111111111111100000000000000","000000000000001111111111111111111111111111111111111111111100000000000000","000000000000001111111111111111111111111111111111111111111100000000000000","000000000000001111111111111111111111111111111111111111111100000000000000","000000000000001111111111111111111111111111111111111111111100000000000000","000000000000001111111111111111111111111111111111111111111100000000000000","000000000000111111111111111111111111111111111111111111111111000000000000","000000000001111111111111111111111111111111111111111111111111100000000000","000000000111111111111111111111111111111111111111111111111111111000000000","000000000111111111111111111111111111111111111111111111111111111000000000","000000000111111111111111111111111111111111111111111111111111111000000000","000000000111111111111111111111111111111111111111111111111111111000000000","000000001111111111111111111111111111111111111111111111111111111100000000","000000011111111111111111111111111111111111111111111111111111111110000000","000001111111111111111111111111111111111111111111111111111111111111100000","000011111111111111111111111111111111111111111111111111111111111111110000","000111111111111111111111111111111111111111111111111111111111111111111000","000111111111111111111111111111111111111111111111111111111111111111111000","000111111111111111111111111111111111111111111111111111111111111111111000","000011111111111111111111111111111111111111111111111111111111111111110000","000001111111111000000111000000100000000000111111111000000111111111100000","000000111111000000000000000000000000000000000000000000000000111111000000","000000011111000000000000000000000000000000000000000000000000111110000000","000000000111000000000000000000000000000000000000000000000000111000000000","000000000011000000000000000000000000000000000000000000000000110000000000","000000000011000000000000000000000000000000000000000000000000110000000000","000000000011000000000000000000000000000000000000000000000000110000000000","000000000001000000000000000000000000000000000000000000000000100000000000","000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000000000000000000000000000000000000000000000","000000000000000000000000000000000000000000000000000000000000000000000000"]/* v7 bloom mask: crown_A_v1s alpha>200 eroded 12px, minus trunk/fork zone (y>192,|x-180|<120); 5px cells */}/* geometry_v1s.json */,flowerScale:1.6,flowerSlots:40,
  /* grass tuft layers (Lumen, paths pending): [{file:'grass/tuft_A_v1s',h:28 (pt tall),y:0 (pt the base sits below the soil line),x:0 (pt offset from trunk centre),w:120 (pt wide),z:6}] - stacked over the trunk base; a missing file is skipped */
  tufts:[],flowerMax:12,flowerV:4/* flower art cache version */,
  /* kit_v1s_b flowers/cherry_blossom (round 5-petal, pre-tinted class_tint_v1r_pastel); app class colour -> nearest kit class_tint */
  flower:{dir:'flowers/cherry_blossom_',tints:{pink:'D45E81',teal:'5ED4C3',violet:'975ED4',ochre:'D9A441',blue:'5E97D4',peach:'D68866',lime:'C6D93B',tan:'8F783E'}}};
function tkHue(v){var r=(v>>16)/255,g=(v>>8&255)/255,b=(v&255)/255,M=Math.max(r,g,b),n=Math.min(r,g,b),d=M-n,h=0;if(!d)return -1;h=M===r?((g-b)/d)%6:M===g?(b-r)/d+2:(r-g)/d+4;return (h*60+360)%360;}
/* nearest pastel kit tint by hue (class dots are dark/saturated; RGB distance sent them all to tan) */
function tkPal(hex){var m=/^#?([0-9a-f]{6})$/i.exec(String(hex||'').trim()),best='pink',bd=1e9;if(!m)return best;var h=tkHue(parseInt(m[1],16));if(h<0)return 'tan';
  Object.keys(ART.flower.tints).forEach(function(n){if(n==='tan')return;var w=tkHue(parseInt(ART.flower.tints[n],16)),d=Math.min(Math.abs(h-w),360-Math.abs(h-w));if(d<bd){bd=d;best=n;}});return best;}
function tkFlowerIMG(kind,col){var f=ART.flower.dir+tkPal(col)+'_'+(kind==='bud'?'bud':'open');
  return '<img class="tk-fla tk-flimg" alt="" draggable="false" src="'+ART.base+f+'@2x.webp'+ART.v+'&f='+ART.flowerV+'" onerror="this.onerror=null;this.src=\''+ART.base+f+'@2x.png'+ART.v+'\'">';}
function tkTufts(el,gY,pt){var st=el.querySelector('.tk-stage');if(!st||!pt)return;st.querySelectorAll('.tk-tuft').forEach(function(x){x.remove();});
  (ART.tufts||[]).forEach(function(t){if(!t||!t.file)return;var im=new Image();im.className='tk-tuft';im.alt='';im.setAttribute('aria-hidden','true');im.draggable=false;
    im.onerror=function(){im.remove();};/* absent layer: skip silently */
    var w=(t.w||120)*pt,h=(t.h||28)*pt;im.style.cssText='position:absolute;pointer-events:none;left:calc(50% + '+((t.x||0)*pt-w/2).toFixed(1)+'px);top:'+(gY+(t.y||0)*pt-h).toFixed(1)+'px;width:'+w.toFixed(1)+'px;height:'+h.toFixed(1)+'px;z-index:'+(t.z||6);
    im.src=artURL(t.file,'webp');st.appendChild(im);});}
function artURL(f,ext){return ART.base+f+'@2x.'+(ext||'webp')+ART.v;}
function artBG(f){return 'image-set(url('+artURL(f,'webp')+') type("image/webp"),url('+artURL(f,'png')+') type("image/png"))';}
var STAGE_SCALE={1:0.6,2:0.8,3:1}/* only used when the kit has no real art for a stage */, CLUMPS=[3,5,5,7,7,8];
var ROOT_MIN=0.03, ROOT_MAX=0.42, ROOT_SPREAD=0.36, ROOT_EDGE=36/* tip x kept this far from the stage edges: badge (<=24px wide, centred on the tip) stays >=24px in */, ROOT_BADGE_GAP=8/* soonest badge top this far below the front-grass bottom */, ROOT_BAND=112/* min px of soil below the grass for roots */, ROOT_BAND_MOB=86/* phones: smaller band so the tree shrinks less (44px flower targets) */, ROOT_PAD=12/* deepest badge bottom this far above the band (stage) bottom */, ROOT_BH=18/* root badge height, centred on the tip */; /* root vertical reach below ground, as a fraction of the trunk height (flare socket -> trunk tip) */
var BANDS=[[0,0.25,['base','mid1','tip_m1']],[0.25,0.5,['base','mid1','mid2','tip_m2']],[0.5,0.75,['base','mid1','mid2','mid3','tip']]];
function chainFor(len){for(var i=0;i<BANDS.length;i++)if(len<BANDS[i][1])return BANDS[i][2].slice();
  var L=Math.min(3,1+Math.floor((len-0.75)/0.125)),c=['base','mid1'];for(var j=0;j<L;j++)c.push('mid_loop');return c.concat(['mid2','mid3','tip']);}
function tipGrow(len){/* continuous growth inside a chain band: tip scales 0.7..1.3 */
  var lo,hi;if(len>=0.75){lo=0.75+Math.min(2,Math.floor((len-0.75)/0.125))*0.125;hi=lo+0.125;}else{for(var i=0;i<BANDS.length;i++)if(len<BANDS[i][1]){lo=BANDS[i][0];hi=BANDS[i][1];break;}}
  return 0.7+0.6*Math.max(0,Math.min(1,(len-lo)/(hi-lo)));}
function rot(v,deg){var a=deg*Math.PI/180,c=Math.cos(a),s=Math.sin(a);return [v[0]*c-v[1]*s,v[0]*s+v[1]*c];}
function add(a,b){return [a[0]+b[0],a[1]+b[1]];}
function sub(a,b){return [a[0]-b[0],a[1]-b[1]];}
function len(v){return Math.sqrt(v[0]*v[0]+v[1]*v[1]);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

/* ---------- sample data (contract v0.5 shape) ---------- */
var NAMES=['Calculus I','Biology','English Comp','World History','Chemistry Lab','Intro to Psychology','Spanish II','Art Studio','Statistics','Music Theory','Economics','Physics'];
var LONG='Introduction to Comparative Political Systems and Global Governance';
var COLORS=['#CFDCC6','#E8D3A9','#C9D7E8','#E6C7C0','#D9CFE6','#C8E0DA','#EAD9B8','#D4D9C2'];
var KINDS=['task','deadline','focus'];
function sample(spec){
  var o={c:5,r:6,f:null,phase:'mid',long:false,stage:null};
  String(spec||'').split(',').forEach(function(t){t=t.trim().toLowerCase();var m=t.match(/^(\d+)([crf])$/);
    if(m)o[m[2]]=+m[1];else if(t==='start'||t==='end'||t==='mid')o.phase=t;else if(t==='long')o.long=true;
    else if(/^s[0-5]$/.test(t))o.stage=+t[1];});
  if(o.stage==null)o.stage=o.phase==='start'?1:o.phase==='end'?5:3;
  var start=new Date(2026,7,24),end=new Date(2026,11,14),total=(end-start)/864e5;
  var prog=o.phase==='start'?0.03:o.phase==='end'?0.97:0.52;
  var today=new Date(start.getTime()+prog*total*864e5),left=Math.max(0,Math.round((end-today)/864e5));
  var nf=o.f==null?o.c*3:o.f,branches=[],overflow=[];
  for(var i=0;i<o.c;i++){var nm=(o.long&&i%2===0)?LONG:NAMES[i%NAMES.length];
    var b={course_id:100+i,name:nm,code:'C'+(101+i),color:COLORS[i%8],slot:i,side:i%2?'right':'left',
      length:Math.min(1,0.15+0.85*Math.min(1,0.7*prog+0.3*((i*37)%100)/100)),flowers:[],buds:[]};
    if(i<8)branches.push(b);else overflow.push({course_id:b.course_id,name:nm,code:b.code,color:b.color});}
  for(var f=0;f<nf&&branches.length;f++){var bb=branches[f%branches.length];
    bb.flowers.push({id:KINDS[f%3]+':'+f,kind:KINDS[f%3],label:KINDS[f%3]+' item '+(f+1),done_at:null});}
  branches.forEach(function(b,i){b.flower_count=b.flowers.length;for(var k=0;k<1+i%2;k++)b.buds.push({id:'task:open'+i+k,label:'Open task '+(k+1)});});
  var roots=[];for(var r=0;r<o.r;r++){var dl=r===0&&o.r>2?-2:Math.round(r*(left+14)/Math.max(1,o.r-1));
    roots.push({deadline_id:500+r,course_id:100+(r%Math.max(1,o.c)),name:(o.long&&r%2?LONG:'Deadline '+(r+1)),days_left:dl,overdue:dl<0});}
  roots.forEach(function(x){x.depth=x.overdue?0:(left<=0?1:Math.max(0,Math.min(1,x.days_left/left)));});
  return {version:1,kit_version:'oak-kit-3',today:today.toISOString().slice(0,10),
    semester:{start:'2026-08-24',end:'2026-12-14',progress:prog},tree:{stage_idx:o.stage},branches:branches,roots:roots,overflow:overflow};
}

/* ---------- contract v0.5 logical mapping (client fills if the server omitted it) ---------- */
function normalize(d){
  d.branches=d.branches||[];d.roots=d.roots||[];
  var si=d.tree&&d.tree.stage_idx!=null?d.tree.stage_idx:5;d.stage_idx=si;
  if(d.stage==null)d.stage=si<2?1:si<4?2:3;
  if(d.stage_scale==null)d.stage_scale=si%2===1?1.1:1;
  d.branches.forEach(function(b){if(!b.kit)b.kit={slot:b.slot+1,chain:chainFor(b.length)};if(!b.kit.chain)b.kit.chain=chainFor(b.length);});
  var rs=d.roots.slice().sort(function(a,b){return (b.overdue-a.overdue)||(a.days_left-b.days_left);});
  var SOCK=[2,3,1,4],ANG=['ap0','am12','ap12'];
  if(!d.roots_more){d.roots=rs.slice(0,12);d.roots_more=rs.slice(12);}
  d.roots.forEach(function(r,i){if(!r.kit)r.kit={socket:SOCK[i%4],angle:ANG[Math.floor(i/4)%3]};});
  return d;
}

/* ---------- layout in kit (2048) space ---------- */
function layout(kit,d){
  var P={};kit.pieces.forEach(function(p){P[p.name]=p;});
  var items=[],hits=[],missing=[],rotWarn=[];
  function piece(n){var p=P[n];if(!p&&missing.indexOf(n)<0)missing.push(n);return p;}
  /* item: attach_px at world w; m = 2x2 linear map about attach (rotation/scale/stretch) */
  function M(deg,s){var a=deg*Math.PI/180,c=Math.cos(a)*s,n=Math.sin(a)*s;return [c,n,-n,c];}
  function put(p,w,m,layer){var it={p:p,w:w,m:m,layer:layer};items.push(it);return it;}
  function world(it,local){var v=[local[0]-it.p.attach_px[0],local[1]-it.p.attach_px[1]],m=it.m;return [it.w[0]+m[0]*v[0]+m[2]*v[1],it.w[1]+m[1]*v[0]+m[3]*v[1]];}
  /* stage art: <name>_s1/_s2 when the kit paints that stage, else the stage-3 piece (kit only bakes what changes) */
  var suf=d.stage===3?'':'_s'+d.stage;
  function SP(n){return P[n+suf]||(P[n]?P[n]:piece(n));}
  /* baked angle from the name: <am|ap>NN [_rot<m|p>NN] ; per-slot bakes drop in with no code change */
  var VRX=/^(am|ap)(\d+)(?:_rot([mp])(\d+))?(?:_s(\d))?$/;
  function variant(N,seg,heading){var pre='branch_'+N+'_'+seg+'_',c=[];kit.pieces.forEach(function(p){
      if(p.name.indexOf(pre)!==0)return;var m=VRX.exec(p.name.slice(pre.length));if(!m||+m[2]===4)return;
      c.push({p:p,a:(m[1]==='am'?-1:1)*m[2]+(m[3]?(m[3]==='m'?-1:1)*m[4]:0),s:m[5]?+m[5]:3});});
    var st=c.filter(function(x){return x.s===d.stage;});if(!st.length)st=c.filter(function(x){return x.s===3;});
    var best=null;st.forEach(function(x){if(!best||Math.abs(heading-x.a)<Math.abs(heading-best.a))best=x;});
    if(!best){if(missing.indexOf(pre+'*')<0)missing.push(pre+'*');return null;}return best;}
  var flare=SP('trunk_flare'),trunk=P['trunk_core'+suf]||P.trunk_core||piece('trunk');
  var realStage=!suf||!!P['trunk_core'+suf];
  /* roots: stage art if painted; otherwise borrow the nearest painted stage, re-anchored and scaled to this flare */
  function rootSrc(base){var tries=[suf,'_s2','_s1',''].filter(function(x,i,a){return a.indexOf(x)===i;});
    for(var i=0;i<tries.length;i++){var sfx=tries[i],pc=P[base+sfx]||P[base+'_base'+sfx];if(!pc)continue;
      var fl=P['trunk_flare'+sfx]||P.trunk_flare,r=sfx===suf?1:flare.size[0]/fl.size[0];
      var chain=['_base','_mid','_tip'].map(function(k){return P[base+k+sfx];}).filter(Boolean);
      var first=chain.length?chain[0]:pc,sock=first.socket_px||pc.socket_px;
      return {chain:chain.length?chain:[pc],sock:sfx===suf?sock:add(flare.socket_px,[(sock[0]-fl.socket_px[0])*r,(sock[1]-fl.socket_px[1])*r]),r:r};}
    piece(base);return null;}
  var RS=d.roots.map(function(r){return rootSrc('root_'+r.kit.socket+'_'+r.kit.angle);});
  var ground=1e9;RS.forEach(function(s){if(s)ground=Math.min(ground,s.sock[1]);});if(ground>1e8)ground=flare?flare.socket_px[1]-flare.attach_px[1]*0.1:1800;
  var trunkH=trunk?Math.abs(trunk.attach_px[1]-trunk.tip_px[1]):1000;
  /* angled roots (Design r8): no kit root pieces; each deadline is a tapered matte root from the trunk flare angling down into the soil band.
     Depth = due date (sooner = shallower, latest = bottom of the band). Geometry in world px; drawn as SVG in screen space by fit(). */
  var pv=flare?flare.socket_px:[1024,ground],fw=flare?flare.size[0]:200,rootGeo=[];
  d.roots.forEach(function(r,ri){var dep=r.overdue?0:Math.max(0,Math.min(1,r.depth||0)),h={type:'root',at:[pv[0],ground],data:r,depth:dep};
    rootGeo.push({sx:pv[0]+(ri%2?1:-1)*fw*(0.05+0.025*(ri%3)),side:ri%2?1:-1,rank:Math.floor(ri/2),dep:dep,seed:ri+1,od:!!r.overdue,hit:h});hits.push(h);});
  /* v1r: one piece (trunk + flare + full roots) replaces trunk_full, trunk_flare and the stub roots; anchor_base_centre on the trunk base at the soil line */
  var TR=ART.trunkRoots,trS=trunkH/TR.anchor[1],trW=[pv[0],ground];
  put({file:TR.file,src:artURL(TR.file,'webp'),png:artURL(TR.file,'png'),size:TR.size,attach_px:TR.anchor},trW,M(0,trS),1);
  /* deadline badges pinned to root_tips_1x: soonest -> shallowest tip */
  var tipsW=TR.tips.map(function(t){return [trW[0]+(t[0]-TR.anchor[0])*trS,trW[1]+(t[1]-TR.anchor[1])*trS];}).sort(function(a,b){return a[1]-b[1];});
  rootGeo.slice().sort(function(a,b){return a.dep-b.dep;}).forEach(function(g,i){g.tipW=tipsW[Math.min(i,tipsW.length-1)];});
  var clumps=[],used={},avail=[];kit.pieces.forEach(function(p){var m=/^branch_slot_(\d+)(_s\d)?$/.exec(p.name);if(m&&(m[2]||'')===(realStage?suf:''))avail.push(+m[1]);});
  avail.sort(function(a,b){return a-b;});var taken={};
  d.branches.forEach(function(b){var N=b.kit.slot;
    if(avail.indexOf(N)<0||taken[N]){var f=avail.filter(function(x){return !taken[x];});N=f.length?f[0]:avail[d.branches.indexOf(b)%avail.length];}
    taken[N]=1;var sl=P['branch_slot_'+N+(realStage?suf:'')]||piece('branch_slot_'+N);if(!sl)return;b._slot=N;
    var heading=sl.angle,w=sl.socket_px,segs=[],ch=b.kit.chain,g=tipGrow(b.length||0);
    ch.forEach(function(seg,k){var vb=variant(N,seg,heading);if(!vb)return;var p=vb.p;
      var res=heading-vb.a;if(Math.abs(res)>ROT_LIMIT){if(rotWarn.indexOf(N)<0)rotWarn.push(N);res=Math.max(-ROT_LIMIT,Math.min(ROT_LIMIT,res));}
      var it=put(p,w,M(res,k===ch.length-1?g:1),3);segs.push(it);w=world(it,p.tip_px);});
    /* tip->base draw order so each base cap tucks under the previous end */
    items.splice(items.length-segs.length,segs.length);segs.slice().reverse().forEach(function(s){items.push(s);});
    var cl=P['canopy_clump_'+N+(realStage?suf:'')];if(cl)clumps.push([cl,w]);used[N]=1;
    var pts=[];segs.forEach(function(s){(s.p.bloom_px||[]).forEach(function(bp){pts.push(world(s,bp));});});
    var buds=(b.buds||[]).map(function(x){return {id:x.id,kind:'bud',label:x.label||x.title||x.name||'Open item'};});
    var all=b.flowers.concat(buds),fl=all.slice(0,ART.flowerMax||12);/* v5: buds are open tasks -> never truncated by the old bloom-point count (that hid new buds) */b._more=Math.max(0,b.flowers.length-pts.length)+(b.flowers_more||0);
    fl.forEach(function(f,i){var fp=f.kind==='bud'?(P.bud||P.flower_task):(P[f.piece]||P['flower_'+f.kind]||P.flower_task||P.bud);if(!fp){piece('flower_'+f.kind);return;}if(f.kind!=='bud'&&!P[f.piece]&&!P['flower_'+f.kind]&&missing.indexOf('flower_'+f.kind)<0)missing.push('flower_'+f.kind+'(fallback)');f._art=BASE+IMG(fp.file)+V;
      var it={p:fp,w:pts[i%Math.max(1,pts.length)]||w,m:M(0,FLOWER_SCALE),layer:5};/* v4: flower art is drawn in screen space inside its ring, above the canopy */hits.push({type:'flower',at:world(it,[fp.attach_px[0],fp.size[1]/2]),data:f,branch:b});});
    b._fl=fl.length;
    /* r6: anchors this branch's flowers may sit on (bloom points, joints, tip) */b._anc=pts.concat(segs.map(function(s){return s.w;}),[w]);
    hits.push({type:'branch',at:w,data:b,side:sl.tip_px[0]<0?'left':'right'});});
  kit.pieces.forEach(function(p){var m=/^canopy_clump_(\d+)(_s\d)?$/.exec(p.name);if(m&&(m[2]||'')===(realStage?suf:'')&&!used[+m[1]])clumps.push([p,p.socket_px]);});
  /* r5: one connected crown — pull the chosen clumps toward their centroid (y harder than x) and enlarge slightly so the top cluster overlaps the lower mass instead of floating on a bare stem */
  var crown=[],CS=clumps.slice(0,CLUMPS[Math.max(0,Math.min(5,d.stage_idx))]),cx=0,cy=0;CS.forEach(function(c){cx+=c[1][0];cy+=c[1][1];});cx/=CS.length||1;cy/=CS.length||1;
  var fs=d.stage===1&&realStage?CROWN_S1:1,ay=cy;if(fs<1)CS.forEach(function(c){ay=Math.max(ay,cy+(c[1][1]-cy)*CROWN_PULL[1]+c[0].size[1]*0.3);});/* shrink stage-1 crown about its base so it still sits on the stem */
  CS.forEach(function(c){var q=[cx+(c[1][0]-cx)*CROWN_PULL[0]*fs,ay+(cy+(c[1][1]-cy)*CROWN_PULL[1]-ay)*fs],cs=CLUMP_SCALE*fs;var it=put(c[0],q,M(0,cs),4);crown.push({c:world(it,[c[0].size[0]/2,c[0].size[1]/2]),rx:c[0].size[0]*cs*0.4,ry:c[0].size[1]*cs*0.4});/* ellipse inside the clump's painted mass (~88% leaf coverage, measured on the art) */});
  /* v1r spread flowers (port of kit _src/render_v1q/compose_v1r.py): golden-angle sunflower inside 0.78 of the crown ellipse, seeded shuffle */
  var crownBox=null;
  /* v1s: crown_A_v1s replaces crown mass, lobes and branch chains; centred on trunk_base_x */
  (function(){var C=ART.crown,keep=items.filter(function(it){return it.p.src;});items.length=0;keep.forEach(function(it){items.push(it);});
    var cw=[trW[0],trW[1]-(ART.soilLine-C.centreY)*trS];
    put({file:C.file,src:artURL(C.file,'webp'),png:artURL(C.file,'png'),size:C.size,attach_px:[C.size[0]/2,C.size[1]/2]},cw,M(0,trS),4);
    crownBox=[{c:cw,rx:C.size[0]/2*trS,ry:C.size[1]/2*trS}];crown.length=0;crown.push({c:[trW[0],trW[1]-(ART.soilLine-C.zone.cy)*trS],rx:C.zone.rx*trS,ry:C.zone.ry*trS});})();
  (function(){var F=hits.filter(function(h){return h.type==='flower';}),N=F.length;if(!N||!crown.length)return;
    var x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;crown.forEach(function(c){x0=Math.min(x0,c.c[0]-c.rx);x1=Math.max(x1,c.c[0]+c.rx);y0=Math.min(y0,c.c[1]-c.ry);y1=Math.max(y1,c.c[1]+c.ry);});
    var mc=[(x0+x1)/2,(y0+y1)/2],rx=(x1-x0)/2,ry=(y1-y0)/2,S=ART.flowerSlots,taken={};
    /* v5 stable slots: each flower/bud owns slot hash(id) % S in a fixed S-point sunflower (independent of N); collisions probe forward in hash order, so adding one never moves the others */
    function hid(x){var h=2166136261;x=String(x);for(var i=0;i<x.length;i++){h^=x.charCodeAt(i);h=Math.imul(h,16777619)>>>0;}return h;}
    F.map(function(h){return [hid(h.data.id||h.data.label),h];}).sort(function(a,b){return a[0]-b[0]||String(a[1].data.id).localeCompare(String(b[1].data.id));}).forEach(function(e){
      var j=e[0]%S;for(var n=0;n<S&&taken[j];n++)j=(j+1)%S;taken[j]=1;var r=0.78*Math.sqrt((j+0.5)/S),t=j*2.39996+0.6;e[1].at=[mc[0]+Math.cos(t)*rx*r,mc[1]+Math.sin(t)*ry*r*0.92-ry*0.06];});})();
  items.sort(function(a,b){return a.layer-b.layer;});
  return {crownBox:crownBox,ptS:trS,crown:crown,items:items,hits:hits,missing:missing,rotWarn:rotWarn,realStage:realStage,stage1:d.stage===1&&realStage,ground:ground,trunkH:trunkH,rootGeo:rootGeo,pivot:flare?flare.socket_px:[1024,ground],P:P};
}

/* ---------- frame = bbox of everything drawn (after stage scale) + full root range ---------- */
function frame(L,sc){var x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,pv=L.pivot;
  function S(pt){return [pv[0]+(pt[0]-pv[0])*sc,pv[1]+(pt[1]-pv[1])*sc];}
  function inc(pt){pt=S(pt);x0=Math.min(x0,pt[0]);y0=Math.min(y0,pt[1]);x1=Math.max(x1,pt[0]);y1=Math.max(y1,pt[1]);}
  L.items.forEach(function(it){var p=it.p;[[0,0],[p.size[0],0],[0,p.size[1]],[p.size[0],p.size[1]]].forEach(function(c){
    var v=[c[0]-p.attach_px[0],c[1]-p.attach_px[1]],m=it.m;inc([it.w[0]+m[0]*v[0]+m[2]*v[1],it.w[1]+m[1]*v[0]+m[3]*v[1]]);});});
  inc([pv[0],L.ground+L.trunkH*ROOT_MAX]);if(L.rootGeo&&L.rootGeo.length){inc([pv[0]-L.trunkH*ROOT_SPREAD,L.ground]);inc([pv[0]+L.trunkH*ROOT_SPREAD,L.ground]);}/* r8: room for the angled roots (kit root pieces used to widen the frame) */
  var mx=(x1-x0)*0.05,my=(y1-y0)*0.04;
  if(L.stage1){var sky=(y1-y0)*SKY_S1;y0-=sky;}/* r7b: extra sky above the sapling instead of a bigger (pole-like) tree */
  return {x:x0-mx,y:y0-my,w:x1-x0+2*mx,h:y1-y0+2*my+L.trunkH*0.04*sc,ground:S([0,L.ground])[1],S:S};}

/* ---------- render ---------- */
function render(el,kit,d){
  d=normalize(d);var L=layout(kit,d),sc=(L.realStage?1:STAGE_SCALE[d.stage])*(d.stage_scale||1),F=frame(L,sc);
  var h='<div class="tk-stage"><div class="tk-soil slot-soil" style="top:'+((F.ground-F.y)/F.h*100).toFixed(2)+'%"></div><svg class="tk-roots" aria-hidden="true"></svg>';
  h+='<div class="tk-world" style="width:'+F.w.toFixed(1)+'px;height:'+F.h.toFixed(1)+'px">';
  h+='<div class="tk-grow" style="transform-origin:'+(L.pivot[0]-F.x).toFixed(1)+'px '+(L.pivot[1]-F.y).toFixed(1)+'px;transform:scale('+sc+')">';
  L.items.forEach(function(it){var p=it.p,m=it.m;
    h+='<img alt="" draggable="false" src="'+(p.src||BASE+IMG(p.file)+V)+'"'+(p.png?' onerror="this.onerror=null;this.src=\''+p.png+'\'"':'')+' style="left:'+(it.w[0]-p.attach_px[0]-F.x).toFixed(1)+'px;top:'+(it.w[1]-p.attach_px[1]-F.y).toFixed(1)+'px;width:'+p.size[0]+'px;height:'+p.size[1]+'px;transform-origin:'+p.attach_px[0]+'px '+p.attach_px[1]+'px;transform:matrix('+m.map(function(x){return x.toFixed(4);}).join(',')+',0,0)">';});
  /* soil v1f (Lumen): band under tree (.tk-soil), then tree, then tree_base_grass anchored on the trunk-base socket (.tk-top, sways with tree), root flare, then front_grass (.tk-fg) */
  var GT=((F.ground-F.y)/F.h*100).toFixed(2),TBG=[589,178],TBA=[289,88];
  h+='</div></div><div class="tk-fg" style="top:'+GT+'%"></div>';
  h+='<div class="tk-world tk-top" style="width:'+F.w.toFixed(1)+'px;height:'+F.h.toFixed(1)+'px"><div class="tk-grow" style="transform-origin:'+(L.pivot[0]-F.x).toFixed(1)+'px '+(L.pivot[1]-F.y).toFixed(1)+'px;transform:scale('+sc+')"><img alt="" draggable="false" class="tk-tbg" src="/static/img/soil_v1f/'+IMG('tree_base_grass.png')+SV+'" style="left:'+(L.pivot[0]-TBA[0]-F.x).toFixed(1)+'px;top:'+(L.ground-TBA[1]-F.y).toFixed(1)+'px;width:'+TBG[0]+'px;height:'+TBG[1]+'px"></div></div>';
  h+='<div class="tk-hits"></div><div class="tk-badges">';
  /* (badges) */
  if(d.roots_more&&d.roots_more.length&&!d.roots.length)h+='<span class="tk-more" title="'+esc(d.roots_more.map(function(r){return r.name;}).join(', '))+'">+'+d.roots_more.length+' due</span>';
  if(d.overflow&&d.overflow.length)h+='<span class="tk-more" title="'+esc(d.overflow.map(function(c){return c.name;}).join(', '))+'">+'+d.overflow.length+' classes</span>';
  h+='</div></div><div class="tk-legend"></div>';
  el.innerHTML=h;el.classList.add('tk-v1r');el.style.setProperty('--tk-sky',artBG(ART.tiles.sky));el.style.setProperty('--tk-soilt',artBG(ART.tiles.soil));el.style.setProperty('--tk-grasst',artBG(ART.tiles.grass));el.style.setProperty('--tk-flsc',ART.flowerScale);el.dataset.flv=ART.flowerV;el.dataset.flb=d.branches.filter(function(b){return b._fl>0;}).map(function(b){return d.branches.indexOf(b);}).join(',');el.dataset.missing=L.missing.join(',');el.dataset.rot=L.rotWarn.join(',');
  el._tk={fz:L.crown[0],cb:L.crownBox&&L.crownBox[0],rm:d.roots_more||[],F:F,rootGeo:L.rootGeo,hits:L.hits,crown:L.crownBox||L.crown,ptS:L.ptS,sc:sc,tba:TBA,tbh:TBG[1],s1:L.stage1,gy:L.ground,py:L.pivot[1]};fit(el);
}
/* screen-space pass: size the stage, place labels without overlap, cluster crowded flowers/roots */
/* r7: phones keep the tree tall enough for every 44px flower target to sit on its branch/crown; short phones scroll */
function MIN_H_MOB(){return window.TK_MINH||MINH0;}
function fit(el){var T=el._tk;if(!T)return;var F=T.F,st=el.querySelector('.tk-stage'),wd=el.querySelector('.tk-world'),hb=el.querySelector('.tk-hits');
  var cw=el.clientWidth,mob=innerWidth<=760,maxH,lg=el.querySelector('.tk-legend');
  if(mob){var nav=document.querySelector('.tabbar'),navH=nav&&getComputedStyle(nav).display!=='none'?innerHeight-nav.getBoundingClientRect().top:0;
    var top0=el.getBoundingClientRect().top+scrollY;maxH=Math.max(MIN_H_MOB(),Math.min(innerHeight-navH-24,innerHeight-navH-top0-8));el.style.paddingBottom='';if(el._tkCap)maxH=Math.min(maxH,el._tkCap);/* r9: stage ends at the bottom of the soil band (no mint strip under the nav pill); the tree may scroll under the nav per the r7 phone rule */}
  else{/* whole stage (incl. deepest roots) inside the first viewport: 100vh - top offset - margin */
    var top1=el.getBoundingClientRect().top+scrollY;maxH=Math.max(320,innerHeight-top1-24);el.style.paddingBottom='';}
  var H=Math.min(cw*F.h/F.w,maxH),W=H*F.w/F.h,k=W/F.w;
  /* r8: phone sapling (stage 1) - trim the extra sky band off the frame top so the tree draws larger (uniform, no stretch)
     until the crown top sits ZOOM_TOP px below the stage top; never trims below the MIN_H_MOB stage height. */
  if(mob&&T.s1&&T.crown&&T.crown.length){var u=F.S([1,0])[0]-F.S([0,0])[0],cw0=Infinity;
    T.crown.forEach(function(c){cw0=Math.min(cw0,F.S(c.c)[1]-c.ry*u);});/* crown top, frame coords */
    for(var it=0;it<6;it++){var gap=(cw0-F.y)*k-ZOOM_TOP;if(gap<2)break;
      var t=gap/k,nh=F.h-t;if(cw*nh/F.w<MIN_H_MOB())nh=Math.max(F.h-t,MIN_H_MOB()*F.w/cw);if(nh>=F.h-0.5)break;
      F={x:F.x,y:F.y+F.h-nh,w:F.w,h:nh,ground:F.ground,S:F.S};H=Math.min(cw*F.h/F.w,maxH);W=H*F.w/F.h;k=W/F.w;}}
  /* front grass (soil v1f) is drawn at --tk-sb-h tall, offset -17.3%; its opaque bottom edge is row 224/640. the stage ends at the soil band bottom */
  var SBH=parseFloat(getComputedStyle(el).getPropertyValue('--tk-sb-h'))||230,ROOT_GRASS=SBH*(224/640-0.173);
  /* r10: roots need ROOT_BAND px of open soil under the grass. The stage never grows past maxH (phone: it ends above the nav); the tree scales down instead so the band fits inside the same stage */
  var RB=mob?ROOT_BAND_MOB:ROOT_BAND,gY0=(F.ground-F.y)*k,xs=Math.max(0,RB-(H-gY0-ROOT_GRASS));
  if(xs>0&&H+xs>maxH){H=Math.max(200,maxH-xs);W=H*F.w/F.h;k=W/F.w;gY0=(F.ground-F.y)*k;xs=Math.max(0,RB-(H-gY0-ROOT_GRASS));}
  H+=xs;
  st.style.width=W+'px';st.style.height=H+'px';var F0=T.F;/* r8: art is laid out against the render-time frame; shift it when fit() trimmed the frame */el.querySelectorAll('.tk-world').forEach(function(w){w.style.transform=(F!==F0?'translate('+((F0.x-F.x)*k).toFixed(2)+'px,'+((F0.y-F.y)*k).toFixed(2)+'px) ':'')+'scale('+k+')';});
  /* r9: soil band + front grass follow the (possibly trimmed) frame so the ground line, moss and band stay together at any scale */
  var gyS=((F.ground-F.y)*k).toFixed(1)+'px';if(T.ptS){el.style.setProperty('--tk-pt',(T.ptS*k*T.sc).toFixed(4));}/* v1r: screen px per kit pt (grass band height) */el.querySelectorAll('.tk-soil,.tk-fg').forEach(function(x){x.style.top=gyS;});tkTufts(el,(F.ground-F.y)*k,(T.ptS||0)*k*T.sc);
  var tb=el.querySelector('.tk-tbg');if(tb&&T.sc){tb.style.transformOrigin=T.tba[0]+'px '+T.tba[1]+'px';tb.style.transform='scale('+(TBG_PX/T.tbh/(k*T.sc)).toFixed(4)+')';}/* r7: base moss at native screen size, only the tree scales */
  function scr(pt){var q=F.S(pt);return [(q[0]-F.x)*k,(q[1]-F.y)*k];}
  /* angled roots: placed in screen px so depth spans the visible soil under the (native-size) front grass: grass line -> band bottom.
     sooner = shallow + flatter (~28deg), latest = band bottom + steeper (~58deg). Tapered polygon ~10px at the flare -> ~3px at the tip. */
  function inv(q){var a=F.S([0,0]),b=F.S([1,1]),s=b[0]-a[0];return [(q[0]/k+F.x-a[0])/s,(q[1]/k+F.y-a[1])/s];}
  function rnd(n){var x=Math.sin(n*12.9898+78.233)*43758.5453;return x-Math.floor(x);}
  var gY=(F.ground-F.y)*k,top0=gY+ROOT_GRASS+ROOT_BADGE_GAP+9,bot0=H-ROOT_PAD-ROOT_BH/2,rsv=el.querySelector('.tk-roots');
  /* r10: dep 1 (latest) puts the badge bottom ROOT_PAD above the band bottom; all others shallower */
  (T.rootGeo||[]).forEach(function(g){var s0=[scr([g.sx,0])[0],gY-3],ty=top0+Math.max(0,bot0-top0)*(0.06+0.94*Math.sqrt(g.dep))/* r11: sqrt keeps near deadlines clear of the grass in a short phone band; still strictly increasing */,dy=ty-s0[1],
      ang=(28+30*g.dep)*Math.PI/180,dx=dy/Math.tan(ang)+18+26*g.rank+10*rnd(g.seed),tx=Math.max(ROOT_EDGE,Math.min(W-ROOT_EDGE,s0[0]+g.side*dx));
    g.s=s0;g.t=[tx,ty];g.c=[s0[0]+(tx-s0[0])*(0.52+0.14*rnd(g.seed+7)),s0[1]+dy*(0.12+0.12*rnd(g.seed+3))];g.hit.at=inv(g.t);});
  /* r11: tips pushed to the same edge clamp keep their 44px badges apart: the shallower tip on a side moves inward */
  (function(){var G=T.rootGeo||[],HB=52;for(var pass=0;pass<4;pass++)G.forEach(function(a){G.forEach(function(b){if(a===b||a.side!==b.side||a.t[1]>=b.t[1])return;
    if(Math.abs(a.t[0]-b.t[0])<HB&&Math.abs(a.t[1]-b.t[1])<HB){var nx=b.t[0]-a.side*HB;a.t=[Math.max(ROOT_EDGE,Math.min(W-ROOT_EDGE,nx)),a.t[1]];
      a.c=[a.s[0]+(a.t[0]-a.s[0])*0.6,a.c[1]];a.hit.at=inv(a.t);}});});})();
  (T.rootGeo||[]).forEach(function(g){if(g.tipW){g.t=scr(g.tipW);g.hit.at=g.tipW;}});/* v1r: badges on the painted root tips */
  var rp=(T.rootGeo||[]).map(function(g){var s0=g.s,c0=g.c,t0=g.t,N=24,L=[],R=[];
      for(var i=0;i<=N;i++){var u=i/N,a=(1-u)*(1-u),b=2*(1-u)*u,e=u*u,x=a*s0[0]+b*c0[0]+e*t0[0],y=a*s0[1]+b*c0[1]+e*t0[1];
        var tx=2*(1-u)*(c0[0]-s0[0])+2*u*(t0[0]-c0[0]),ty=2*(1-u)*(c0[1]-s0[1])+2*u*(t0[1]-c0[1]),l=Math.hypot(tx,ty)||1,w=(11-8*Math.pow(u,0.7))/2;
        L.push((x-ty/l*w).toFixed(1)+','+(y+tx/l*w).toFixed(1));R.unshift((x+ty/l*w).toFixed(1)+','+(y-tx/l*w).toFixed(1));}
      return '<path class="tk-root'+(g.od?' od':'')+'" d="M'+L.join('L')+'L'+R.join('L')+'Z"/>';}).join('');
  /* roots sit under the tree, front grass and base moss: they emerge from under the moss tuft at the trunk base */
  if(rsv){rsv.setAttribute('width',W);rsv.setAttribute('height',H);rsv.setAttribute('viewBox','0 0 '+W.toFixed(1)+' '+H.toFixed(1));rsv.innerHTML=rp;}
  var boxes=[],out=[],lbls=[],chips=[];
  function hitsBox(b){for(var i=0;i<boxes.length;i++){var q=boxes[i];if(b.l<q.r&&q.l<b.r&&b.t<q.b&&q.t<b.b)return true;}return false;}
  /* r6: a flower box must sit on its own branch (within SNAP of a bloom point/joint/tip) or inside the crown, never in open sky */
  var SNAP=HIT*0.6,EDGE=12,/* crown edge: the 24px glyph still overlaps leaf mass */CR=(T.crown||[]).map(function(c){return {c:scr(c.c),rx:c.rx*k*sc0(),ry:c.ry*k*sc0()};});
  function sc0(){var a=F.S([0,0]),b=F.S([1,0]);return b[0]-a[0];}
  function ancOf(br){return (br&&br._anc||[]).map(scr);}
  /* r7g: bare trunk = within half a target of the trunk centreline and outside every crown clump; never a flower spot */
  /* r7g: below the canopy (under every crown clump's bottom, outside the clumps) is bare trunk / sapling stub: never a flower spot */
  var CB=CR.length?Math.max.apply(null,CR.map(function(C){return C.c[1]+C.ry;})):1e9;
  function bareTrunk(x,y){if(y<=CB)return false;for(var j=0;j<CR.length;j++)if(Math.hypot((CR[j].c[0]-x)/(CR[j].rx+EDGE),(CR[j].c[1]-y)/(CR[j].ry+EDGE))<=1)return false;return true;}
  function onTree(bx,br,strict){var x=(bx.l+bx.r)/2,y=(bx.t+bx.b)/2,A=ancOf(br);if(bareTrunk(x,y))return false;if(T.onMask)return T.onMask([x,y]);/* v7: blooms only on the opaque canopy mask (was: crown-image bbox ellipse + EDGE, or any branch anchor incl. the trunk fork, which let groups land in the sky / on the trunk) */for(var i=0;i<A.length;i++)if(Math.hypot(A[i][0]-x,A[i][1]-y)<=SNAP)return true;var E2=strict?0:EDGE;/* r7g: widened search lands well inside leaf mass */for(var j=0;j<CR.length;j++)if(Math.hypot((CR[j].c[0]-x)/(CR[j].rx+E2),(CR[j].c[1]-y)/(CR[j].ry+E2))<=1)return true;return false;}
  function snapBox(bx,br){if(onTree(bx,br))return bx;var x=(bx.l+bx.r)/2,y=(bx.t+bx.b)/2,A=ancOf(br),bp=null,bd=1e9;A.forEach(function(a){var d=Math.hypot(a[0]-x,a[1]-y);if(d<bd){bd=d;bp=a;}});if(!bp)return bx;return clampBox({l:bp[0]-HIT/2,r:bp[0]+HIT/2,t:bp[1]-HIT/2,b:bp[1]+HIT/2});}
  function clampBox(b){var dx=Math.max(0,-b.l)-Math.max(0,b.r-W),dy=Math.max(0,-b.t)-Math.max(0,b.b-H);return {l:b.l+dx,r:b.r+dx,t:b.t+dy,b:b.b+dy};}
  /* 1. branch labels: try own side, then flip, then push down/up */
  /* 2. flowers & roots: greedy clusters with 44px targets; clusters that would overlap anything merge into the nearest cluster */
  /* v1r: relax flowers in screen px so 1.6x flowers never overlap (small Profile stage) */
  /* Profile only: cap flower groups to what fits at 44px touch area (Design call; flowers stay 1.6x) */
  if(el.closest('.me-plant')){var stW=(el.querySelector('.tk-stage')||el).offsetWidth,fsc=innerWidth<=600?(parseFloat(getComputedStyle(el).getPropertyValue('--me-tk-s'))||.59):1,cap=Math.max(1,Math.floor(stW/Math.max(44,(20*ART.flowerScale+16)/fsc))),nf=0;
    T.hits=T.hits.filter(function(t){return t.type!=='flower'||(nf++<cap);});}
  (function(){var F=T.hits.filter(function(t){return t.type==='flower';}),P=F.map(function(t){return scr(t.at);}),D=Math.max(20*ART.flowerScale+4,(el.querySelector(".tk-hits .tk-fl")||{offsetWidth:0}).offsetWidth+2,(parseFloat(getComputedStyle(el.querySelector(".tk-fla")||el).width)||0)+4,48);
    /* v5 stable: each item starts at its own id slot (t.at0, never mutated) and only moves itself; items placed oldest-id first, so a newly added one never displaces the others */
    var SW=st.offsetWidth,SH=st.offsetHeight,m=D/2,idn=function(t){var x=String(t.data.id||''),n=parseInt(x.split(':').pop(),10);return isNaN(n)?1e9:n;},
      ord=F.map(function(_,i){return i;}).sort(function(a,b){return idn(F[a])-idn(F[b])||String(F[a].data.id).localeCompare(String(F[b].data.id));}),done=[];
    /* v7: every flower/bud stays inside the crown flower_zone ellipse (screen px). The relax spiral used to only clamp to the stage box, so at 390 (zone ~ D-sized) collisions spiralled items up into the sky */
    var Z=T.fz,zc=scr(Z.c),zr=scr([Z.c[0]+Z.rx,Z.c[1]+Z.ry]),zx=Math.abs(zr[0]-zc[0]),zy=Math.abs(zr[1]-zc[1]);
    function ez(q){return Math.hypot((q[0]-zc[0])/zx,(q[1]-zc[1])/zy);}
    /* v7: blooms must sit on the crown's opaque canopy (alpha mask, eroded by a bloom radius) and off the trunk/fork zone; the id slot is kept, only the spiral search is constrained */
    var CBX=T.cb,MK=ART.crown.mask,cc=CBX?scr(CBX.c):zc,cu=CBX?Math.abs(scr([CBX.c[0]+CBX.rx,CBX.c[1]])[0]-cc[0])/(ART.crown.size[0]/2):1;
    function onMask(q){if(!CBX)return ez(q)<=0.92;var x=(q[0]-cc[0])/cu+ART.crown.size[0]/2,y=(q[1]-cc[1])/cu+ART.crown.size[1]/2,r=MK[Math.floor(y/5)];return !!r&&x>=0&&r.charAt(Math.floor(x/5))==='1';}
    T.onMask=onMask;
    ord.forEach(function(i){var t=F[i];t.at0=t.at0||t.at;var b0=scr(t.at0),q=b0,best=null,bd=-1;
      for(var k=0;k<600;k++){var a=k*2.39996,r=k?D*0.3*Math.sqrt(k):0;q=[b0[0]+Math.cos(a)*r,b0[1]+Math.sin(a)*r];if(!onMask(q))continue;
        var md=done.reduce(function(v,p){return Math.min(v,Math.hypot(p[0]-q[0],p[1]-q[1]));},1e9);if(md>=D){best=q;break;}if(md>bd){bd=md;best=q;}}
      q=best||b0;done.push(q);P[i]=q;});
    T.fzS=[zc[0],zc[1],zx,zy];T.flS=P.slice();
    F.forEach(function(t,i){t.at=inv(P[i]);});})();
  function cluster(type){var cl=[];T.hits.filter(function(t){return t.type===type;}).forEach(function(t){var p=scr(t.at),best=null,bd=1e9;
      cl.forEach(function(c){if(type==='flower'&&c.items[0].branch!==t.branch)return;var dd=Math.hypot(c.x-p[0],c.y-p[1]);if(dd<HIT*1.05&&dd<bd){bd=dd;best=c;}});
      if(best){best.items.push(t);best.x=(best.x*(best.items.length-1)+p[0])/best.items.length;best.y=(best.y*(best.items.length-1)+p[1])/best.items.length;}
      else cl.push({x:p[0],y:p[1],items:[t]});});return cl;}
  function placeLabels(){
  var meas=document.createElement('span');meas.className='tk-hit tk-lbl';meas.style.visibility='hidden';hb.appendChild(meas);
  T.hits.filter(function(t){return t.type==='branch';}).sort(function(a,b){return a.at[1]-b.at[1];}).forEach(function(t){
    if(true){/* v23: legend chips at every width, no on-tree tags */var L0={b:null,t:t,extra:[]};lbls.push(L0);chips.push(L0);return;}
    meas.innerHTML='<span>'+esc(t.data.code||t.data.name)+'</span>'+(t.data._more?'<em>+'+t.data._more+'</em>':'');
    var bw=Math.min(meas.offsetWidth+2,mob?110:150),p=scr(t.at),sides=t.side==='left'?['left','right']:['right','left'],pick=null;
    for(var dy=0;dy<=6*HIT&&!pick;dy+=HIT/2){for(var sgn=0;sgn<(dy?2:1)&&!pick;sgn++){var y=p[1]+(sgn?-dy:dy);
      for(var s=0;s<2&&!pick;s++){var l=sides[s]==='left'?p[0]-8-bw:p[0]+8,b=clampBox({l:l,r:l+bw,t:y-HIT/2,b:y+HIT/2});if(!hitsBox(b))pick=b;}}}
    if(!pick)pick=clampBox({l:p[0]-bw/2,r:p[0]+bw/2,t:p[1]-HIT/2,b:p[1]+HIT/2});
    boxes.push(pick);lbls.push({b:pick,t:t,extra:[]});});
  meas.remove();
  }
  ['flower','root'].forEach(function(type){if(type==='root')placeLabels();var cl=cluster(type),changed=true,guard=0;
    while(changed&&guard++<40){changed=false;for(var i=0;i<cl.length;i++){var a=cl[i],ba=clampBox({l:a.x-HIT/2,r:a.x+HIT/2,t:a.y-HIT/2,b:a.y+HIT/2});
        for(var j=i+1;j<cl.length;j++){var c=cl[j];if(type==='flower'&&c.items[0].branch!==a.items[0].branch)continue;if(Math.abs(c.x-a.x)<HIT&&Math.abs(c.y-a.y)<HIT){a.items=a.items.concat(c.items);a.x=(a.x+c.x)/2;a.y=(a.y+c.y)/2;cl.splice(j,1);changed=true;break;}}if(changed)break;}}
    cl.forEach(function(c){var b=clampBox({l:c.x-HIT/2,r:c.x+HIT/2,t:c.y-HIT/2,b:c.y+HIT/2});
      /* nudge off labels/other boxes; if no free spot nearby, fold into the overlapped label's count */
      var tries=[[0,0]],ok=null;for(var rr=1;rr<=(type==='flower'?2:1);rr++)for(var ty=-rr;ty<=rr;ty++)for(var tx=-rr;tx<=rr;tx++)if(Math.max(Math.abs(tx),Math.abs(ty))===rr)tries.push([tx*HIT/2*(type==='flower'?1:2),ty*HIT/2*(type==='flower'?1:2)]);
      tries.sort(function(a,b){return Math.hypot(a[0],a[1])-Math.hypot(b[0],b[1]);});
      for(var i=0;i<tries.length&&!ok;i++){var q=clampBox({l:b.l+tries[i][0],r:b.r+tries[i][0],t:b.t+tries[i][1],b:b.b+tries[i][1]});if(!hitsBox(q)&&(type!=='flower'||onTree(q,c.items[0].branch)))ok=q;}
      if(!ok&&type==='flower'){/* never fold a branch's flowers into text: merge into this branch's other placed cluster, else take the free spot nearest the stage edge */
        /* v4: rings stay within one ring-width of their flower; crowded flowers join the nearest ring (count) or sit on the flower */
        var mine=null,md=1e9;out.forEach(function(o){if(o.type!=='flower'||o.br!==c.items[0].branch)return;var dd=Math.hypot((o.b.l+o.b.r)/2-c.x,(o.b.t+o.b.b)/2-c.y);if(dd<md){md=dd;mine=o;}});
        if(mine){mine.items=mine.items.concat(c.items);return;}
        /* v4.1: never merge across branches; widen the search for a free spot for this branch's own ring */
        for(var rr2=3;rr2<=8&&!ok;rr2++)for(var ty2=-rr2;ty2<=rr2&&!ok;ty2++)for(var tx2=-rr2;tx2<=rr2&&!ok;tx2++){if(Math.max(Math.abs(tx2),Math.abs(ty2))!==rr2)continue;var q2=clampBox({l:b.l+tx2*HIT/2,r:b.r+tx2*HIT/2,t:b.t+ty2*HIT/2,b:b.b+ty2*HIT/2});if(!hitsBox(q2)&&onTree(q2,c.items[0].branch,1))ok=q2;}
        if(ok){boxes.push(ok);out.push({b:ok,br:c.items[0].branch,type:type,items:c.items,od:false,title:''});return;}
        /* r6: still nothing free near the cluster: try free spots around each of this branch's own anchors (still on the branch) */
        var A6=ancOf(c.items[0].branch);for(var ai=0;ai<A6.length&&!ok;ai++)for(var r6=0;r6<=2&&!ok;r6++)for(var y6=-r6;y6<=r6&&!ok;y6++)for(var x6=-r6;x6<=r6&&!ok;x6++){if(Math.max(Math.abs(x6),Math.abs(y6))!==r6)continue;var q6=clampBox({l:A6[ai][0]-HIT/2+x6*HIT/4,r:A6[ai][0]+HIT/2+x6*HIT/4,t:A6[ai][1]-HIT/2+y6*HIT/4,b:A6[ai][1]+HIT/2+y6*HIT/4});if(!hitsBox(q6)&&onTree(q6,c.items[0].branch))ok=q6;}
        /* r6: else the nearest free spot inside the crown (canopy mass), never open sky */
        if(!ok){var bd6=1e9;CR.forEach(function(C){var ex=C.rx+EDGE,ey=C.ry+EDGE;for(var gy=-ey;gy<=ey;gy+=HIT/8)for(var gx=-ex;gx<=ex;gx+=HIT/8){if(Math.hypot(gx/ex,gy/ey)>1)continue;var px=C.c[0]+gx,py=C.c[1]+gy,q7=clampBox({l:px-HIT/2,r:px+HIT/2,t:py-HIT/2,b:py+HIT/2});if(!onTree(q7,c.items[0].branch)||hitsBox(q7))continue;var d7=Math.hypot(px-c.x,py-c.y);if(d7<bd6){bd6=d7;ok=q7;}}});}
        /* r6: tiny stages: a free spot on any branch's wood (joint/tip/bloom point), still on the tree */
        if(!ok){var bd8=1e9;T.hits.forEach(function(h){if(h.type!=='branch')return;ancOf(h.data).forEach(function(a8){for(var y8=-1;y8<=1;y8++)for(var x8=-1;x8<=1;x8++){var q8=clampBox({l:a8[0]-HIT/2+x8*HIT/4,r:a8[0]+HIT/2+x8*HIT/4,t:a8[1]-HIT/2+y8*HIT/4,b:a8[1]+HIT/2+y8*HIT/4});if(hitsBox(q8)||!onTree(q8,h.data))continue;var d8=Math.hypot((q8.l+q8.r)/2-c.x,(q8.t+q8.b)/2-c.y);if(d8<bd8){bd8=d8;ok=q8;}}});});}
        /* r6: squeezed stage (tree too small for every 44px target on wood/crown): take the free spot that hugs the tree closest, never the open-sky spot nearest the old cluster */
        if(!ok){var bd9=1e9,AA=[];T.hits.forEach(function(h){if(h.type==='branch')AA=AA.concat(ancOf(h.data));});
          function gap(x,y){var g=1e9;AA.forEach(function(a){g=Math.min(g,Math.hypot(a[0]-x,a[1]-y)-SNAP);});CR.forEach(function(C){var e=Math.hypot((C.c[0]-x)/(C.rx+EDGE),(C.c[1]-y)/(C.ry+EDGE));g=Math.min(g,(e-1)*Math.min(C.rx,C.ry));});return Math.max(0,g);}
          for(var y9=HIT/2;y9<=H-HIT/2;y9+=HIT/8)for(var x9=HIT/2;x9<=W-HIT/2;x9+=HIT/8){var q9={l:x9-HIT/2,r:x9+HIT/2,t:y9-HIT/2,b:y9+HIT/2};if(hitsBox(q9)||!onTree(q9,c.items[0].branch))continue;/* r7g: on wood/crown only; else fold into the class label below */var d9=gap(x9,y9)*4+Math.hypot(x9-c.x,y9-c.y)*0.05;if(d9<bd9){bd9=d9;ok=q9;}}}
        if(!ok){var sb=snapBox(b,c.items[0].branch);if(!bareTrunk((sb.l+sb.r)/2,(sb.t+sb.b)/2)&&(type!=='flower'||onTree(sb,c.items[0].branch)))ok=sb;}}
      if(!ok){/* no free 44px spot: fold into the nearest class label (tap the label) */
        var nl=null,nd=1e9;lbls.forEach(function(L){var q=L.b?[(L.b.l+L.b.r)/2,(L.b.t+L.b.b)/2]:scr(L.t.at),dd=Math.hypot(q[0]-c.x,q[1]-c.y);if(dd<nd){nd=dd;nl=L;}});
        if(nl)nl.extra=nl.extra.concat(c.items);return;}
      boxes.push(ok);var t0=c.items[0];
      var title=c.items.map(function(t){return type==='root'?t.data.name+(t.data.overdue?' (overdue)':' ('+t.data.days_left+'d)'):t.data.label;}).join(', ');
      var od=type==='root'&&c.items.some(function(t){return t.data.overdue;});
      out.push({b:ok,br:type==='flower'?t0.branch:null,type:type,items:c.items,od:od,title:title});});});
  /* r7g: final guard: any flower box that ended off its branch/crown (or on bare trunk) moves to the nearest free crown/branch spot, else joins its branch's nearest ring */
  out.slice().forEach(function(o){if(o.type!=='flower'||onTree(o.b,o.br))return;var i0=boxes.indexOf(o.b);if(i0>=0)boxes.splice(i0,1);var cx=(o.b.l+o.b.r)/2,cy=(o.b.t+o.b.b)/2,best=null,bd=1e9;
    for(var y=HIT/2;y<=H-HIT/2;y+=HIT/8)for(var x=HIT/2;x<=W-HIT/2;x+=HIT/8){var q={l:x-HIT/2,r:x+HIT/2,t:y-HIT/2,b:y+HIT/2};if(hitsBox(q)||!onTree(q,o.br))continue;var d=Math.hypot(x-cx,y-cy);if(d<bd){bd=d;best=q;}}
    if(best){o.b=best;boxes.push(best);return;}
    var m=null,md=1e9;out.forEach(function(p){if(p===o||p.type!=='flower'||p.br!==o.br)return;var d=Math.hypot((p.b.l+p.b.r)/2-cx,(p.b.t+p.b.b)/2-cy);if(d<md){md=d;m=p;}});
    if(m){m.items=m.items.concat(o.items);out.splice(out.indexOf(o),1);return;}
    /* no room on the tree at all (tiny stage): fold into this class's label/chip count, like the no-spot path */
    var nl=null;lbls.forEach(function(L){if(L.t&&L.t.data===o.br)nl=L;});if(!nl){var nd=1e9;lbls.forEach(function(L){var q=L.b?[(L.b.l+L.b.r)/2,(L.b.t+L.b.b)/2]:scr(L.t.at),dd=Math.hypot(q[0]-cx,q[1]-cy);if(dd<nd){nd=dd;nl=L;}});}
    if(nl){nl.extra=nl.extra.concat(o.items);out.splice(out.indexOf(o),1);}else boxes.push(o.b);});
  /* v6 spill: roots past the 12 drawn add their count to the badge whose deadlines are nearest in days, so the badge sum == all open deadlines (the +N pill only shows when no badge is drawn) */
  (function(){var RC=out.filter(function(o){return o.type==='root';});if(!RC.length)return;(T.rm||[]).forEach(function(r){var best=null,bd=1e9;
    RC.forEach(function(o){o.items.forEach(function(t){var dd=Math.abs((t.data.days_left||0)-(r.days_left||0));if(dd<bd){bd=dd;best=o;}});});(best.spill=best.spill||[]).push(r);});})();
  out.forEach(function(o){if(!o.type)return;var type=o.type,n=o.items.length+(o.spill?o.spill.length:0),od=o.od,title=o.items.map(function(t){return type==='root'?t.data.name+(t.data.overdue?' (overdue)':' ('+t.data.days_left+'d)'):t.data.label;}).concat((o.spill||[]).map(function(r){return r.name+(r.overdue?' (overdue)':' ('+r.days_left+'d)');})).join(', '),bi=type==='flower'?T.hits.filter(function(x){return x.type==='branch';}).map(function(x){return x.data;}).indexOf(o.br):-1;
      o.html='<button type="button" style="POS'+(o.br?';--c:'+o.br.color+';--d:'+(o.br.dot||o.br.color):'')+'"'+(bi>=0?' data-b="'+bi+'" data-bs="'+(function(){var B=T.hits.filter(function(x){return x.type==='branch';}).map(function(x){return x.data;}),u=[];o.items.forEach(function(t){var k=B.indexOf(t.branch);if(k>=0&&u.indexOf(k)<0)u.push(k);});return u.join(' ');})()+'"':'')+' class="tk-hit '+(type==='root'?'tk-rt':'tk-fl')+(od?' od':'')+(n>1?' grp':'')+'" title="'+esc(title)+'" aria-label="'+esc(n>1?n+' '+type+'s: '+title:title)+'">'+(type==='root'?'<b>'+n+'</b>':((o.br&&o.items[0].data.kind)?tkFlowerIMG/* buds too: kit_v1s_b cherry_blossom_{tint}_bud, not the old v1q tulip bud */(o.items[0].data.kind,o.br&&(o.br.dot||o.br.color)):'<img class="tk-fla" alt="" draggable="false" src="'+(o.items[0].data._art||BASE+IMG('flowers/flower_task.png')+V)+'">'))+(n>1&&type!=='root'?'<b>'+n+'</b>':'')+'</button>';});
  lbls.forEach(function(L){if(!L.b)return;var t=L.t,fx=L.extra.filter(function(x){return x.type==='flower';}).length,rx=L.extra.length-fx,more=(t.data._more||0)+fx;
    var title=t.data.name+(L.extra.length?' · '+L.extra.map(function(x){return x.data.label||x.data.name;}).join(', '):'');
    out.push({b:L.b,html:'<button type="button" class="tk-hit tk-lbl" style="--c:'+t.data.color+';POS" title="'+esc(title)+'"><span>'+esc(t.data.code||t.data.name)+'</span>'+(more?'<em>✿'+more+'</em>':'')+(rx?'<em>↓'+rx+'</em>':'')+'</button>'});});
  /* root depth on screen (px below soil line) for QA */
  el._tk.dbg={snap:SNAP,edge:EDGE,crown:CR,anc:T.hits.filter(function(x){return x.type==='branch';}).map(function(x){return ancOf(x.data);}),cb:CB};
  el.dataset.rootDepths=T.hits.filter(function(t){return t.type==='root';}).map(function(t){return Math.round(scr(t.at)[1]-((F.ground-F.y)*k));}).join(',');
  /* 390: compact legend chips under the tree, keyed by branch colour + number (number also on the flower clusters) */
  if(lg){lg.innerHTML=chips.map(function(L,i){var t=L.t,fx=L.extra.filter(function(x){return x.type==='flower';}).length,rx=L.extra.length-fx,more=(t.data._more||0)+fx;
      return '<button type="button" class="tk-hit tk-chip" style="--c:'+t.data.color+';--d:'+(t.data.dot||t.data.color)+'" title="'+esc(t.data.name)+'"><i></i><span>'+esc(t.data.code||t.data.name)+'</span>'+(more?'<em>✿'+more+'</em>':'')+(rx?'<em>↓'+rx+'</em>':'')+'</button>';}).join('');lg.hidden=!chips.length;}
  hb.innerHTML=out.map(function(o){return o.html.replace('POS','left:'+o.b.l.toFixed(1)+'px;top:'+o.b.t.toFixed(1)+'px;width:'+(o.b.r-o.b.l).toFixed(1)+'px;height:'+(o.b.b-o.b.t).toFixed(1)+'px');}).join('');
  /* r9: flowers rendered <=24px get a thinner, softer cream rim (1px visible @60%); larger flowers keep 1.5px @80% */
  hb.querySelectorAll('svg.tk-fla').forEach(function(sv){sv.classList.toggle('tk-rim-sm',sv.getBoundingClientRect().width<=24.5);});
}

/* r2: reserve the final stage height while /api/tree loads (same maxH rule as fit) so nothing shifts when the tree lands */
function reserve(el){var mob=innerWidth<=760,top0=el.getBoundingClientRect().top+scrollY,H;
  if(mob){var nav=document.querySelector('.tabbar'),navH=nav&&getComputedStyle(nav).display!=='none'?innerHeight-nav.getBoundingClientRect().top:0;
    H=Math.max(MIN_H_MOB(),Math.min(innerHeight-navH-24,innerHeight-navH-top0-8));}
  else H=Math.min(el.clientWidth*0.7,Math.max(320,innerHeight-top0-24));
  /* the stage plus legend/badges below it end up ~64px taller than maxH on phones; once a tree has drawn at this viewport, reuse its exact height */
  var k='tkH:'+innerWidth+'x'+innerHeight,c=0;try{c=+localStorage.getItem(k)||0;}catch(_){}
  el._tkR=Math.round(c||H+(mob?64:0));el._tkVK=k;el.style.minHeight=el.style.height=el._tkR+'px';}
/* r3: lock the box at the reserved height. If the tree came out taller, cap the stage so the whole box equals the reservation (0px shift); shorter trees keep min-height */
function settle(el){var R=el._tkR;if(!R)return;for(var i=0;i<4;i++){var h=el.scrollHeight,st=el.querySelector('.tk-stage');if(!st||Math.abs(h-R)<0.5||h<R)break;
  el._tkCap=(el._tkCap||st.getBoundingClientRect().height)-(h-R);fit(el);}}
function remember(el){try{localStorage.setItem('tkH:'+innerWidth+'x'+innerHeight,Math.round(el.getBoundingClientRect().height));}catch(_){}}
function boot(){
  var el=document.querySelector('[data-tree-kit]');if(!el)return;if(el.classList.contains('tk-pending'))reserve(el);
  var spec=new URLSearchParams(location.search).get('tree_sample');
  var dataP=spec!=null?Promise.resolve(sample(spec)):(window.__tkP&&!el.dataset.treeSrc?(function(q){window.__tkP=null;return q;})(window.__tkP):fetch(el.dataset.treeSrc||'/api/tree',{credentials:'same-origin',headers:{Accept:'application/json'},redirect:'manual'})).then(function(r){
      if(!r.ok||r.type==='opaqueredirect'||(r.headers.get('content-type')||'').indexOf('json')<0)throw new Error('no tree');return r.json();});
  Promise.all([dataP,(function(q){window.__tkK=null;return q||fetch(BASE+'kit.json'+(AV['img/oak_kit/kit.json']?'?v='+AV['img/oak_kit/kit.json']:V));})(window.__tkK).then(function(r){return r.json();})]).then(function(a){
    el.hidden=false;el.classList.remove('tk-pending','tk-failed');el.removeAttribute('aria-busy');
    render(el,a[1],a[0]);var t;window.addEventListener('resize',function(){cancelAnimationFrame(t);t=requestAnimationFrame(function(){rf();});});
    /* the page above the tree can still shift (fonts, images): refit so the stage bottom stays inside the viewport */
    var rf=function(){if(el._tkR&&el._tkVK!=='tkH:'+innerWidth+'x'+innerHeight){el._tkR=el._tkCap=0;el.style.minHeight=el.style.height='';}fit(el);if(el._tkR)settle(el);};if(document.fonts&&document.fonts.ready)document.fonts.ready.then(rf);window.addEventListener('load',rf);
    var lastTop=null;if(window.ResizeObserver)new ResizeObserver(function(){var tp=el.getBoundingClientRect().top+scrollY;if(tp!==lastTop){lastTop=tp;rf();}}).observe(document.body);
    requestAnimationFrame(function(){rf();settle(el);el.dataset.ready='1';remember(el);});}).catch(function(e){if(window.console)console.info('tree_kit: tree unavailable',e&&e.message);el.classList.remove('tk-pending');el.classList.add('tk-failed');el.removeAttribute('aria-busy');});
}
window.ProdyTreeKit={render:render,sample:sample,normalize:normalize,chainFor:chainFor};
/* bfcache restore: a restored page already has its tree; only re-boot if it never finished */
window.addEventListener('pageshow',function(e){var el=document.querySelector('[data-tree-kit]');if(e.persisted&&el&&!el.dataset.ready){el.innerHTML='';boot();}});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
