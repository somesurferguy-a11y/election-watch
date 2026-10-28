'use strict';
function snapshotStatus(stamp,connected,now=Date.now(),limitMinutes=3){
 const published=Date.parse(stamp),valid=Number.isFinite(published)&&published<=now+60000;
 const age=valid?Math.max(0,Math.floor((now-published)/60000)):null;
 const delayed=age===null||now-published>limitMinutes*60000;
 const label=!connected?'DISCONNECTED':age===null?'SNAPSHOT TIME UNAVAILABLE':delayed?'DELAYED SNAPSHOT':'AUTOMATIC SNAPSHOT';
 return {error:!connected||delayed,label,ageText:age===null?'Age unavailable':`${age} minute${age===1?'':'s'} old`};
}
function pagesStatus(){
 if(!state)return;
 const result=snapshotStatus(state.server_time,online,Date.now(),PAGE_SNAPSHOT_LIMIT);
 const banner=document.getElementById('mode-banner');banner.className=result.error?'error':'';
 banner.textContent=`${result.label} · ${result.ageText} · ${PAGE_REFRESH_NOTE} Source times in Source health.`;
 document.getElementById('connection').textContent=online?'Public snapshot connected':'Disconnected · showing last received snapshot';
 document.getElementById('checked').textContent='Snapshot generated '+time(state.server_time);
}
setInterval(pagesStatus,1000);
