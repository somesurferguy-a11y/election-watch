'use strict';
function isPerson(c){return !/^(yes|no)\b/i.test(c.name);}
function orderedCandidates(candidates){return [...candidates].sort((a,b)=>Number(b.service?.incumbent===true)-Number(a.service?.incumbent===true)||(b.votes||0)-(a.votes||0));}
function portraitHtml(c){
 if(!isPerson(c))return '<span class="choice-symbol" aria-hidden="true">'+(/^yes/i.test(c.name)?'✓':'−')+'</span>';
 const initials=c.name.replace(/\([^)]*\)/g,'').split(/\s+/).filter(Boolean).slice(0,2).map(n=>n[0]).join('');
 const path=c.photo?.path;return `<span class="portrait" title="${esc(path?'Portrait of '+(c.photo.subject||c.name)+(c.photo.image_note?' · '+c.photo.image_note:''):'Verified photo unavailable')}"><span aria-hidden="true">${esc(initials)}</span>${path&&/^\/static\/portraits\/[a-f0-9]+\.(jpg|png|webp)$/.test(path)?`<img src="${esc(path)}" alt="${esc(c.photo.subject||c.name)}" loading="lazy" decoding="async">`:''}</span>`;
}
function serviceBadge(c){
 if(!isPerson(c)||state.demo)return '';
 const s=c.service;
 let text=!s?'Service unverified':s.incumbent?'Incumbent':s.terms_completed>0?'Former member':'Challenger';
 if(s&&s.terms_started!=null)text+=s.incumbent?` · term ${s.terms_started} in progress · ${s.terms_completed} completed`:` · ${s.terms_completed} completed term${s.terms_completed===1?'':'s'}`;
 else text+=' · terms unverified';
 return `<small class="service-badge ${s?.incumbent?'incumbent':''}">${esc(text)}</small>`;
}
function serviceDetails(r){return `<section class="service-details"><h2>Incumbency, terms &amp; portraits</h2><p class="note">Incumbents are listed first. Term counts refer to this office/chamber and include the current term only where explicitly stated. Unverified is not zero.</p>${orderedCandidates(r.candidates).filter(isPerson).map(c=>`<div class="service-record">${portraitHtml(c)}<div><strong class="party-text" data-party="${esc(c.party)}">${esc(c.name)}</strong>${serviceBadge(c)}<p class="note">${esc(c.service?.term_note||'Service history has not been verified for this candidate.')}${c.service?.since?' Serving since '+esc(c.service.since)+'.':''}</p>${c.service?.source_url?`<a class="note" href="${safeLink(c.service.source_url)}" target="_blank" rel="noopener">Service source ↗</a>`:''}${c.photo?.source_url?` · <a class="note" href="${safeLink(c.photo.source_url)}" target="_blank" rel="noopener">Portrait source ↗</a><span class="note"> ${esc(c.photo.credit||'')} ${esc(c.photo.image_note||'')}</span>`:''}</div></div>`).join('')}<p class="note">${esc(state.profile_coverage||'')}</p></section>`;}
function racePage(races){const groups=[];let pair=[];for(const r of races){if((r.seats_to_elect||1)>1){if(pair.length){groups.push(pair);pair=[];}groups.push([r]);}else{pair.push(r);if(pair.length===2){groups.push(pair);pair=[];}}}if(pair.length)groups.push(pair);pageCount=Math.max(1,groups.length);pages[view]=((pages[view]||0)%pageCount+pageCount)%pageCount;return groups[pages[view]]||[];}
function seatRank(c,r){
 const seats=r.seats_to_elect||1,total=r.candidates.reduce((n,c)=>n+c.votes,0);
 if(seats===1||!r.has_results||r.result_incomplete||!total)return '';
 const rank=1+r.candidates.filter(other=>other.votes>c.votes).length;
 const tied=r.candidates.filter(other=>other.votes===c.votes).length;
 const label=rank<=seats?(rank+tied-1>seats?'Tied at cutoff':`In top ${seats} · unofficial`):'Outside current top '+seats;
 return `<small class="rank-badge">Rank ${rank} · ${esc(label)}</small>`;
}
document.addEventListener('error',e=>{if(e.target instanceof HTMLImageElement&&e.target.closest('.portrait'))e.target.hidden=true;},true);
