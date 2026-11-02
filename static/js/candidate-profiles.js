'use strict';
function isPerson(c){return !/^(yes|no)\b/i.test(c.name);}
function orderedCandidates(candidates){return [...candidates].sort((a,b)=>Number(b.service?.incumbent===true)-Number(a.service?.incumbent===true)||(b.votes||0)-(a.votes||0));}
function validPhotoCrop(photo){
 const c=photo?.crop;if(!c)return null;
 if(!['x','y','width','height','source_width','source_height'].every(k=>typeof c[k]==='number'&&Number.isFinite(c[k])))return null;
 if(c.x<0||c.y<0||c.width<=0||c.height<=0||c.source_width>10000||c.source_height>10000||c.x+c.width>c.source_width||c.y+c.height>c.source_height)return null;
 return c;
}
function photoPosition(photo){const p=photo?.position;return p&&['x','y'].every(k=>typeof p[k]==='number'&&Number.isFinite(p[k])&&p[k]>=0&&p[k]<=100)?p.x+'% '+p.y+'%':'50% 15%';}
function portraitHtml(c){
 if(!isPerson(c))return '<span class="choice-symbol" aria-hidden="true">'+(/^yes/i.test(c.name)?'✓':'−')+'</span>';
 const initials=c.name.replace(/\([^)]*\)/g,'').split(/\s+/).filter(Boolean).slice(0,2).map(n=>n[0]).join('');
 const path=c.photo?.path,crop=validPhotoCrop(c.photo),hasCrop=!!c.photo&&Object.hasOwn(c.photo,'crop');
 const safe=typeof path==='string'&&(/^\/static\/portraits\/[a-f0-9]+\.(jpg|png|webp)$/.test(path)||(/^\/static\/portraits\/[a-f0-9]+\.frame\.(jpg|png|webp)$/.test(path)&&crop));
 const media=(!safe||(hasCrop&&!crop))?'':crop?`<svg class="portrait-frame" viewBox="${crop.x} ${crop.y} ${crop.width} ${crop.height}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${esc(c.photo.subject||c.name)}"><image href="${esc(path)}" width="${crop.source_width}" height="${crop.source_height}"/></svg>`:`<img style="object-position:${photoPosition(c.photo)}" src="${esc(path)}" alt="${esc(c.photo.subject||c.name)}" loading="lazy" decoding="async">`;
 return `<span class="portrait" title="${esc(media?'Portrait of '+(c.photo.subject||c.name)+(c.photo.image_note?' · '+c.photo.image_note:''):'Verified photo unavailable')}"><span aria-hidden="true">${esc(initials)}</span><small class="portrait-unavailable">Photo unavailable</small>${media}</span>`;
}
function serviceBadge(c){
 if(!isPerson(c)||state.demo)return '';
 const s=c.service;
 let text=!s?'Service unverified':s.incumbent?'Incumbent':(s.former_member||s.terms_completed>0)?'Former member':'Challenger';
 if(s?.current_term_label&&s.incumbent)text+=' · '+s.current_term_label+(s.terms_completed!=null?' · '+s.terms_completed+' completed':' · lifetime terms unverified');
 else if(s&&s.terms_started!=null)text+=s.incumbent?` · term ${s.terms_started} in progress · ${s.terms_completed} completed`:` · ${s.terms_completed} completed term${s.terms_completed===1?'':'s'}`;
 else text+=' · terms unverified';
 if(s?.count_basis==='reported'&&s.terms_completed!=null)text+=' (reported)';
 return `<small class="service-badge ${s?.incumbent?'incumbent':''}">${esc(text)}</small>`;
}
function serviceEvidenceHtml(s){
 if(!s?.evidence?.length)return '';
 return `<div class="service-evidence"><p class="note">Records reviewed ${esc(s.as_of||'date unavailable')} · ${esc(s.verification_status||'Partial history; exact lifetime count may remain unknown')}</p>${s.evidence.map(e=>safeLink(e.url)?`<p class="note"><a href="${safeLink(e.url)}" target="_blank" rel="noopener">${esc(e.title||'Official record')} ↗</a> · ${esc(e.supports||'Service record')}</p>`:'').join('')}</div>`;
}
function serviceDetails(r){if(!r.candidates.some(isPerson))return '';return `<section class="service-details"><h2>Incumbency, terms &amp; portraits</h2><p class="note">Incumbents are listed first. Term counts refer to this office/chamber and include the current term only where explicitly stated. Unverified is not zero.</p>${orderedCandidates(r.candidates).filter(isPerson).map(c=>`<div class="service-record">${portraitHtml(c)}<div><strong class="party-text" data-party="${esc(c.party)}">${esc(c.name)}</strong>${serviceBadge(c)}<p class="note">${esc(c.service?.term_note||'Service history has not been verified for this candidate.')}${c.service?.since?(c.service.incumbent?' Current service began ':' Prior service began ')+esc(c.service.since)+'.':''}</p>${c.service?.source_url?`<a class="note" href="${safeLink(c.service.source_url)}" target="_blank" rel="noopener">Service source ↗</a>`:''}${serviceEvidenceHtml(c.service)}${c.photo?.source_url?` · <a class="note" href="${safeLink(c.photo.source_url)}" target="_blank" rel="noopener">Portrait source ↗</a><span class="note"> ${esc(c.photo.credit||'')} ${esc(c.photo.image_note||'')}</span>`:''}</div></div>`).join('')}<p class="note">${esc(state.profile_coverage||'')}</p></section>`;}
function racePage(races){const groups=[];let pair=[];for(const r of races){if((r.seats_to_elect||1)>1){if(pair.length){groups.push(pair);pair=[];}groups.push([r]);}else{pair.push(r);if(pair.length===2){groups.push(pair);pair=[];}}}if(pair.length)groups.push(pair);pageCount=Math.max(1,groups.length);pages[view]=((pages[view]||0)%pageCount+pageCount)%pageCount;return groups[pages[view]]||[];}
function seatRank(c,r){
 const seats=r.seats_to_elect||1,total=r.candidates.reduce((n,c)=>n+c.votes,0);
 if(seats===1||!r.has_results||r.result_incomplete||!total)return '';
 const rank=1+r.candidates.filter(other=>other.votes>c.votes).length;
 const tied=r.candidates.filter(other=>other.votes===c.votes).length;
 const label=rank<=seats?(rank+tied-1>seats?'Tied at cutoff':`In top ${seats} · unofficial`):'Outside current top '+seats;
 return `<small class="rank-badge">Rank ${rank} · ${esc(label)}</small>`;
}
document.addEventListener('error',e=>{const portrait=e.target.closest?.('.portrait');if(!portrait)return;if(e.target instanceof HTMLImageElement){e.target.hidden=true;portrait.classList.add('photo-failed');}else if(e.target.tagName?.toLowerCase()==='image'&&e.target.closest('.portrait-frame')){e.target.closest('.portrait-frame').style.display='none';portrait.classList.add('photo-failed');}},true);
