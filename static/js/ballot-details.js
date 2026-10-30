'use strict';
function ballotDetailsHtml(r){
 if(!r.ballot_text)return '';
 const source=safeLink(r.ballot_text_source_url);
 return `<section class="ballot-details"><h2>Official ballot question</h2><p class="note">${esc(r.ballot_text)}</p>${r.yes_meaning?`<p class="note"><strong>Yes:</strong> ${esc(r.yes_meaning)}</p>`:''}${r.no_meaning?`<p class="note"><strong>No:</strong> ${esc(r.no_meaning)}</p>`:''}${source?`<a class="note" href="${source}" target="_blank" rel="noopener">Official sample ballot ↗</a>`:''}</section>`;
}
