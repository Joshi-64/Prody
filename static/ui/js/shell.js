/* Prody shell motion (owner: Ripple): sliding tab pill + page fade-out. transform/opacity only. */
(function(){
  var R=document.documentElement;
  if(document.visibilityState==='visible'){R.classList.add('shell-anim');setTimeout(function(){R.classList.remove('shell-anim')},400);}
  var bar=document.querySelector('.tabbar'),pill=bar&&bar.querySelector('.tab-pill');
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  function place(el,anim){
    if(!pill||!el||el.classList.contains('tab-zen')){if(pill)bar.style.setProperty('--pill-o',0);return;}
    if(!anim)bar.classList.add('no-anim');
    var w=Math.min(el.offsetWidth-4,64);
    bar.style.setProperty('--pill-w',w+'px');
    bar.style.setProperty('--pill-x',(el.offsetLeft+(el.offsetWidth-w)/2)+'px');
    bar.style.setProperty('--pill-o',1);
    if(!anim){bar.offsetWidth;bar.classList.remove('no-anim');}
  }
  if(bar){
    var tabs=[].slice.call(bar.querySelectorAll('.tab')),cur=bar.querySelector('.tab.active');
    var prev=tabs[+sessionStorage.getItem('prody-tab')];
    if(prev&&prev!==cur&&!reduce){place(prev,false);requestAnimationFrame(function(){requestAnimationFrame(function(){place(cur,true);});});}
    else place(cur,false);
    addEventListener('resize',function(){place(bar.querySelector('.tab.active'),false);});
    tabs.forEach(function(t,i){t.addEventListener('click',function(){
      var a=bar.querySelector('.tab.active');sessionStorage.setItem('prody-tab',a?tabs.indexOf(a):-1);
      if(t.classList.contains('tab-zen'))return;
      if(a)a.classList.remove('active');t.classList.add('active');place(t,true);
    });});
  }
  // outgoing fade 120ms for same-origin nav links in the shell
  document.addEventListener('click',function(e){
    var a=e.target.closest('.tabbar a,.navlinks a');
    if(!a||e.metaKey||e.ctrlKey||e.shiftKey||reduce||a.target)return;
    e.preventDefault();document.documentElement.classList.add('shell-leaving');
    setTimeout(function(){location.href=a.href;},120);
  });
  addEventListener('pageshow',function(){document.documentElement.classList.remove('shell-leaving');});
})();

/* owner-fb + nav-perf: tab switches felt like buffering. Warm the next page on hover/touchstart so the tap is served
   from cache: <link rel=prefetch> where supported (Chromium, Firefox); fetch() elsewhere (WebKit/Safari has no rel=prefetch).
   The fetch sends X-Prody-Prefetch: 1; for allowlisted read-only pages (server PREFETCH_OK) the server answers private, max-age=10.
   Any POST / fetch mutation / form submit marks every warmed page stale (sessionStorage, survives the navigation): stale pages are
   re-fetched with cache:'reload' (overwrites the cached copy with a no-cache one) and a tap on one waits for that, so it revalidates. */
(function(){
  if(window.__prodyPrefetch)return;window.__prodyPrefetch=1;
  var OK=/^\/(dashboard|tasks|calendar|achievements|friends|store|u\/[A-Za-z0-9_.-]+)\/?$/,K='pp_pf',ss;
  try{ss=window.sessionStorage;}catch(_){}
  function list(k){try{return JSON.parse(ss.getItem(k)||'[]');}catch(_){return [];}}
  function save(k,a){try{ss.setItem(k,JSON.stringify(a));}catch(_){}}
  var of=window.fetch&&window.fetch.bind(window),pend={};
  function reval(p){if(!pend[p])pend[p]=of(p,{credentials:'same-origin',cache:'reload',keepalive:true}).then(function(r){return r.blob();}).catch(function(){}).then(function(){var s=list(K+'s').filter(function(x){return x!==p;});save(K+'s',s);});return pend[p];}
  function stale(){var w=list(K);if(!w.length)return;save(K+'s',list(K+'s').concat(w));save(K,[]);done={};if(of)w.forEach(reval);}
  if(of){window.fetch=function(i,o){var m=((o&&o.method)||(i&&i.method)||'GET').toUpperCase();if(m!=='GET'&&m!=='HEAD')stale();return of(i,o);};}
  document.addEventListener('submit',stale,true);
  if(of)list(K+'s').forEach(reval);
  document.addEventListener('click',function(e){
    var a=e.target&&e.target.closest&&e.target.closest('a[href]');if(!a||e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey)return;
    var u;try{u=new URL(a.href,location.href);}catch(_){return;}
    if(u.origin!==location.origin||!pend[u.pathname]||list(K+'s').indexOf(u.pathname)<0)return;
    e.preventDefault();pend[u.pathname].then(function(){location.href=u.href;});
  },true);
  var tl=document.createElement('link'),LINK=!!(tl.relList&&tl.relList.supports&&tl.relList.supports('prefetch'));
  if(!LINK&&!of)return;
  var done={};
  var c=navigator.connection;if(c&&(c.saveData||/2g/.test(c.effectiveType||'')))return;
  function go(p){
    var w=list(K);if(w.indexOf(p)<0){w.push(p);save(K,w);}
    if(LINK){var l=document.createElement('link');l.rel='prefetch';l.href=p;document.head.appendChild(l);return;}
    of(p,{credentials:'same-origin',headers:{'X-Prody-Prefetch':'1',Accept:'text/html'}}).then(function(r){return r.blob();}).catch(function(){});
  }
  function warm(e){
    var a=e.target&&e.target.closest&&e.target.closest('a[href]');if(!a||a.target||a.hasAttribute('download')||a.hasAttribute('data-no-prefetch'))return;
    var u;try{u=new URL(a.href,location.href);}catch(_){return;}
    if(u.origin!==location.origin||u.search||!OK.test(u.pathname)||u.pathname===location.pathname||done[u.pathname])return;
    done[u.pathname]=1;go(u.pathname);
  }
  document.addEventListener('pointerenter',warm,{capture:true,passive:true});
  document.addEventListener('touchstart',warm,{capture:true,passive:true});
  document.addEventListener('focusin',warm,{passive:true});
})();
