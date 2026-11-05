/* Prody rain loop: CC0/PD recording (see static/ui/audio/CREDITS.md).
   window.prodyRain.start() / .stop() / .playing. Web Audio looped AudioBuffer
   (gapless) with short fades; falls back to a looping <audio> element. */
(function(){
  var V='?v=1', BASE='/static/ui/audio/rain_loop', VOL=0.6, FADE=0.6;
  var a=document.createElement('audio');
  var IOS=/iP(hone|ad|od)/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  var AS=navigator.audioSession; if(AS){try{AS.type='playback';}catch(e){AS=null;}}
  var useOpus=!IOS&&a.canPlayType&&a.canPlayType('audio/ogg; codecs="opus"')==='probably';
  var URL_=BASE+(useOpus?'.opus':'.m4a')+V;
  var ac=null, buf=null, loading=null, src=null, gain=null, el=null, on=false;
  function load(){
    if(buf) return Promise.resolve(buf);
    if(loading) return loading;
    loading=fetch(URL_).then(function(r){if(!r.ok)throw new Error(r.status);return r.arrayBuffer();})
      .then(function(ab){return new Promise(function(res,rej){var p=ac.decodeAudioData(ab,res,rej);if(p&&p.then)p.then(res,rej);});})
      .then(function(b){buf=b;return b;});
    loading.catch(function(){loading=null;});
    return loading;
  }
  function elStart(){
    if(!el){el=new Audio();el.loop=true;el.preload='auto';
      (IOS?[['m4a','audio/mp4']]:[['opus','audio/ogg; codecs=opus'],['m4a','audio/mp4']]).forEach(function(s){var e=document.createElement('source');e.src=BASE+'.'+s[0]+V;e.type=s[1];el.appendChild(e);});}
    el.volume=VOL;var p=el.play();if(p&&p.catch)p.catch(function(){});
  }
  function start(){
    if(on) return; on=true;
    if(IOS&&!AS){elStart();return;}
    try{
      var AC=window.AudioContext||window.webkitAudioContext; if(!AC) throw 0;
      ac=ac||new AC(); if(ac.state==='suspended'&&ac.resume) ac.resume();
      gain=ac.createGain(); gain.gain.value=0; gain.connect(ac.destination);
      var g=gain;
      load().then(function(b){
        if(!on||g!==gain) return;
        src=ac.createBufferSource(); src.buffer=b; src.loop=true; src.loopStart=Math.min(0.03,b.duration/2); src.loopEnd=b.duration; src.connect(g);
        var t=ac.currentTime; g.gain.setValueAtTime(0,t); g.gain.linearRampToValueAtTime(VOL,t+FADE);
        src.start();
      }).catch(function(){ if(on&&g===gain) elStart(); });
    }catch(e){ elStart(); }
  }
  function stop(){
    if(!on) return; on=false;
    if(el){el.pause();}
    if(src&&gain&&ac){var s=src,g=gain,t=ac.currentTime;
      g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(g.gain.value,t); g.gain.linearRampToValueAtTime(0,t+FADE);
      try{s.stop(t+FADE+0.05);}catch(e){} setTimeout(function(){try{g.disconnect();}catch(e){}},(FADE+0.2)*1000);}
    src=null; gain=null;
  }
  window.prodyRain={start:start,stop:stop,get playing(){return on;}};
})();
