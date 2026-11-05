(function(){
  const root=document.documentElement;
  document.addEventListener('click',e=>{
    const t=e.target.closest('[data-theme-toggle]');
    if(t){const n=root.dataset.theme==='dark'?'light':'dark';window.prodySetTheme(n);}
    const dd=e.target.closest('[data-dropdown]');
    document.querySelectorAll('.dropdown.open').forEach(d=>{if(!dd||d!==dd.parentElement)d.classList.remove('open')});
    if(dd) dd.parentElement.classList.toggle('open');
    const x=e.target.closest('.toast button'); if(x) x.parentElement.remove();
    const c=e.target.closest('[data-confirm]'); if(c && !confirm(c.dataset.confirm)) e.preventDefault();
    const pw=e.target.closest('[data-pw]'); if(pw){const i=pw.previousElementSibling;i.type=i.type==='password'?'text':'password';pw.querySelector('.ms').textContent=i.type==='password'?'visibility':'visibility_off';}
  });
  /* theme button shows the theme you'd switch TO: sun in dark, moon in light; kept in sync with any data-theme change (toggle, system follow) */
  const syncIcon=()=>document.querySelectorAll('[data-theme-toggle] .ms').forEach(i=>i.textContent=root.dataset.theme==='dark'?'light_mode':'dark_mode');
  syncIcon();new MutationObserver(syncIcon).observe(root,{attributes:true,attributeFilter:['data-theme']});
  setTimeout(()=>document.querySelectorAll('.toast').forEach((t,i)=>setTimeout(()=>{t.classList.add('hide');setTimeout(()=>t.remove(),350)},i*300)),1800);
  window.celebrate=function(){
    if(!window.confetti) return;
    const c=['#2F5D46','#A9BFA2','#E9DFCB','#B4593A'];
    confetti({particleCount:70,spread:70,origin:{y:.65},colors:c,shapes:['circle'],scalar:.8,gravity:.8,ticks:180});
  };
  window.prodyToast=function(t,cls){const d=document.createElement('div');d.className='toast '+(cls||'success');d.innerHTML='<span class="ms">check_circle</span><div></div>';d.querySelector('div').textContent=t;document.querySelector('.toasts').appendChild(d);setTimeout(()=>{d.classList.add('hide');setTimeout(()=>d.remove(),350)},4500);};
})();
document.querySelectorAll('[data-hscroll]').forEach(s=>{const bar=s.parentElement.querySelector('[data-hbar]');if(!bar)return;
  const upd=()=>{const r=s.clientWidth/s.scrollWidth;bar.style.width=Math.max(r*100,12)+'%';bar.style.transform='translateX('+(s.scrollLeft/s.clientWidth)*100+'%)';if(r>=1)bar.parentElement.style.display='none';};
  s.addEventListener('scroll',upd,{passive:true});addEventListener('resize',upd);upd();});
