'use strict';
let historyMode='candidates',historyRace='',historyScope='indian_river';
const historyDate=value=>new Date(value+'T12:00:00Z').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'America/New_York'});
function historyRows(r,c){return (state.history?.candidates||[]).filter(h=>h.race_id===r.id&&h.candidate_id===c.id);}
function historicalResult(h,detail=false){
 const party=h.phase==='primary'?`${h.party} primary`:h.phase==='municipal'?'Municipal election':'General election';
 return `<section class="past-result"><div class="race-meta"><strong>${esc(historyDate(h.date))} · ${esc(party)}</strong><span>HISTORICAL</span></div><h3>${esc(h.name)}</h3><p class="note">${esc(h.geography)} · <span class="party-text" data-party="${esc(h.party)}">${esc(h.historical_name)}</span></p><div class="past-numbers"><strong>${pct(h.percentage)}</strong><span>${num(h.votes)} votes<br>Rank ${h.rank} of ${h.field_size}</span></div><p class="note">Share of ${num(h.total_votes)} candidate votes in this contest.</p>${detail?`<p class="note">Other candidates: ${h.opponents.map(c=>`<span class="party-text" data-party="${esc(c.party)}">${esc(c.name)}</span>: ${num(c.votes)} (${pct(c.percentage)})`).join(' · ')}</p>`:''}<a class="note" href="${safeLink(h.source_url)}" target="_blank" rel="noopener">${esc(h.source_name)} ↗</a></section>`;
}
function candidateHistoryCard(r,c){
 const records=historyRows(r,c);
 return `<article class="race-card history-card"><div class="race-heading">${portraitHtml(c)}<h2 class="party-text" data-party="${esc(c.party)}">${esc(c.name)}</h2><span class="party">${esc(c.party)}</span></div>${serviceBadge(c)}${records.length?'<p class="note">Most recent verified result</p>'+historicalResult(records[0]):'<div class="empty-history"><h3>No verified result in these archives</h3><p>This does not establish that the candidate has never run. Unopposed races may have no vote tally.</p></div>'}${records.length?`<button data-past-candidate="${esc(c.id)}" data-past-race="${esc(r.id)}">Full history &amp; opponents (${records.length})</button>`:''}</article>`;
}
function renderHistory(){
 if(state.demo){pageCount=1;return empty('History is available in Live sources mode','Real historical results are kept out of the fictional demo. Switch modes in host controls.');}
 const data=state.history;
 if(!data){pageCount=1;return empty('History unavailable','No reviewed historical archive is installed.');}
 const head=`<div class="rail-head"><h1>Election history</h1><div class="history-tabs"><button data-history-mode="candidates" aria-pressed="${historyMode==='candidates'}">Candidate results</button><button data-history-mode="senate" aria-pressed="${historyMode==='senate'}">U.S. Senate wins</button></div></div>`;
 if(historyMode==='senate'&&!data.senate?.length){pageCount=1;return empty('Senate history unavailable','No reviewed Senate history is installed.');}
 if(historyMode==='senate'){
  const cycle=slicePage(data.senate,1)[0];
  return `<div class="section-layout">${head}<p class="coverage">Historical context · seats won that cycle and seats held afterward measure different things.</p><div class="race-list"><article class="race-card history-card"><h2>${cycle.year} U.S. Senate election</h2><h3>Seats won in this cycle</h3><div class="past-numbers"><strong class="blue">${cycle.democratic_aligned_won}</strong><span>Democratic-aligned<br>including allied independents</span><strong class="red">${cycle.republican_won}</strong><span>Republican</span></div><div class="seatbar"><div class="dem" style="width:${cycle.democratic_aligned_won/(cycle.democratic_aligned_won+cycle.republican_won)*100}%"></div><div class="rep" style="width:${cycle.republican_won/(cycle.democratic_aligned_won+cycle.republican_won)*100}%"></div></div><h3>Total seats held afterward</h3><p>${cycle.democratic_aligned_held} Democratic-aligned · ${cycle.republican_held} Republican · 100 total</p><p class="note">${esc(cycle.note)}</p><a class="note" href="${safeLink(cycle.source_url)}" target="_blank" rel="noopener">${esc(cycle.source_name)} ↗</a></article><article class="race-card history-card"><h2>Florida’s previous U.S. Senate election</h2>${data.florida_senate.map(h=>`<section class="past-result"><p>${esc(historyDate(h.date))} · General election</p><h3 class="party-text" data-party="${esc(h.party)}">${esc(h.name)} · ${esc(h.party)}</h3><div class="past-numbers"><strong>${pct(h.percentage)}</strong><span>${num(h.votes)} votes<br>${h.margin_pp.toFixed(2)} percentage-point winning margin</span></div><a class="note" href="${safeLink(h.source_url)}" target="_blank" rel="noopener">${esc(h.source_name)} ↗</a></section>`).join('')}<p class="note">This is a different Senate seat and candidate from the 2026 special election. Historical totals do not predict this year’s outcome.</p><p class="note">Reviewed ${esc(time(data.verified_at))} · Historical snapshots, not live returns.</p></article></div></div>`;
 }
 const races=orderedRaces([...state.races,...(state.settled_races||[])].filter(r=>r.scope===historyScope));
 let race=races.find(r=>r.id===historyRace);
 if(!race){race=races.find(r=>data.candidates.some(h=>h.race_id===r.id))||races[0];historyRace=race?.id||'';}
 const subset=slicePage(orderedCandidates(race?.candidates||[]),2);
 return `<div class="section-layout">${head}<div class="history-filters"><label>Area <select id="history-scope"><option value="indian_river" ${historyScope==='indian_river'?'selected':''}>Indian River County</option><option value="florida" ${historyScope==='florida'?'selected':''}>Florida · full contest</option></select></label><label>Current race <select id="history-race">${races.map(r=>`<option value="${esc(r.id)}" ${r.id===race?.id?'selected':''}>${esc(r.name)}</option>`).join('')}</select></label></div><p class="coverage">Dated archive results · primaries have different electorates. Multi-seat shares count candidate votes, not voters. ${race?esc(race.name):''}</p><div class="race-list">${race?subset.map(c=>candidateHistoryCard(race,c)).join(''):empty('No races in this area','Select another area.')}</div><p class="note history-coverage">${esc(data.coverage_note)}</p></div>`;
}
document.addEventListener('change',e=>{
 if(e.target.id==='history-scope'){historyScope=e.target.value;historyRace='';pages.history=0;localPause=true;render();}
 if(e.target.id==='history-race'){historyRace=e.target.value;pages.history=0;localPause=true;render();}
});
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b||!state)return;
 if(b.dataset.historyMode){historyMode=b.dataset.historyMode;pages.history=0;render();}
 if(b.dataset.historyRace){const r=[...state.races,...(state.settled_races||[])].find(r=>r.id===b.dataset.historyRace);if(!r)return;historyRace=r.id;historyScope=r.scope;historyMode='candidates';pages.history=0;localPause=true;$('details').close();setView('history');}
 if(b.dataset.pastCandidate){const r=[...state.races,...(state.settled_races||[])].find(r=>r.id===b.dataset.pastRace),c=r?.candidates.find(c=>c.id===b.dataset.pastCandidate);if(!c)return;$('details-content').innerHTML=`<h1 class="party-text" data-party="${esc(c.party)}">${esc(c.name)} · past elections</h1><p class="note">Historical results · no current winner implied. Rank is by votes; it is not a winner call.</p>${historyRows(r,c).map(h=>historicalResult(h,true)).join('')}<p class="note">${esc(state.history.coverage_note)}</p>`;$('details').showModal();}
});
