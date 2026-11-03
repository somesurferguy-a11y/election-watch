const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={URL,Date,document:{addEventListener:()=>{}}};vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/candidate-profiles.js','utf8'),context);
const app=fs.readFileSync('static/js/app.js','utf8');
vm.runInContext(app.slice(0,app.indexOf('function chamber(')),context);
vm.runInContext('function render(){}',context);
const candidates=Array.from({length:8},(_,i)=>({id:String(i),name:`Candidate ${i}`,party:'NON',votes:0,service:{incumbent:i===0}}));
const race={id:'race',name:'Test race',candidates};context.race=race;
vm.runInContext('state={races:[race],settled_races:[]}',context);
const window=()=>context.candidateWindow(race);
assert.deepEqual(Array.from(window().selected,c=>c.id),['0','1','2']);
assert.equal(window().pageCount,4);
const seen=new Set();
for(let page=0;page<4;page++){
 assert.equal(window().page,page);
 assert.equal(window().selected[0].id,'0');
 window().selected.forEach(c=>seen.add(c.id));
 assert.match(context.candidatePager(race),new RegExp(`Candidate page ${page+1} of 4`));
 context.changeCandidatePage('race',1);
}
assert.equal(seen.size,8);
assert.equal(window().page,3);
assert.match(context.candidatePager(race),/data-candidate-step="1" disabled/);
context.changeCandidatePage('race',-1);assert.equal(window().page,2);
assert.equal(vm.runInContext('localPause',context),true);
// Refreshes, time changes and revisiting a race cannot silently choose a new page.
context.Date={now:()=>9999999999999};assert.equal(window().page,2);
race.candidates=[...candidates];assert.equal(window().page,2);
assert.equal(context.candidateWindow({...race,id:'other'}).page,0);
assert.equal(context.candidateWindow({...race,seats_to_elect:3}).selected.length,8);
assert.equal(context.candidatePager({...race,seats_to_elect:3}),'');
assert.equal(context.candidateWindow(race,true).selected.length,8);
// Many incumbents must not consume all slots and hide challengers.
race.candidates=candidates.map((c,i)=>({...c,service:{incumbent:i<4}}));
vm.runInContext('candidatePages.clear()',context);
const manySeen=new Set();
for(let i=0;i<3;i++){window().selected.forEach(c=>manySeen.add(c.id));assert.ok(window().selected.length<=3);context.changeCandidatePage('race',1);}
assert.equal(manySeen.size,8);
race.candidates=candidates.slice(0,2);assert.equal(window().page,0);assert.equal(context.candidatePager(race),'');
assert.match(app,/if\(b.dataset.candidateRace\)\{changeCandidatePage/);
assert.ok(!app.includes('Math.floor(Date.now()/12000)'));
console.log('Candidate pagination: stable pages, navigation, reachability, incumbent and multi-seat checks passed');

// Unattended TV advances every visible group; a pause/modal guard holds identity.
race.candidates=candidates;vm.runInContext('candidatePages.clear()',context);
context.document.querySelectorAll=()=>[{dataset:{openRace:'race'}}];
const autoSeen=new Set();
for(let tick=0;tick<4;tick++){window().selected.forEach(c=>autoSeen.add(c.id));context.advanceCandidatePages();}
assert.equal(autoSeen.size,8);assert.equal(window().page,0);
context.advanceCandidatePages();const held=window().page;context.advanceCandidatePages(true);assert.equal(window().page,held);
assert.match(app,/const paused=localPause\|\|!state.settings.rotation\|\|\$\('details'\).open/);
assert.match(app,/if\(!paused&&now-lastPage>=12000\)/);
console.log('Unattended candidate traversal and pause guard passed');

// Exercise the real timer with the fastest supported view interval (10 seconds).
let clock=0;context.Date=class extends Date{static now(){return clock;}};
context.document.getElementById=id=>({open:false,textContent:''});
context.updateFreshness=()=>{};context.updateCountdowns=()=>{};context.renderTicker=()=>{};
context.nextAutoView=()=> 'florida';context.setView=()=>vm.runInContext('lastRotate=Date.now();lastPage=Date.now()',context);
vm.runInContext('state.settings={rotation:true,rotation_seconds:10,ticker_paused:false};localPause=false;lastRotate=0;lastPage=0;candidatePages.clear()',context);
const timer=app.slice(app.indexOf('setInterval(()=>{const now='),app.indexOf("document.addEventListener('visibilitychange'"));
let tick;context.setInterval=fn=>{tick=fn;};vm.runInContext(timer,context);
const fastSeen=new Set();
for(let cycle=0;cycle<4;cycle++){window().selected.forEach(c=>fastSeen.add(c.id));clock+=10000;tick();}
assert.equal(fastSeen.size,8);
const pausedPage=window().page;vm.runInContext('localPause=true',context);clock+=10000;tick();assert.equal(window().page,pausedPage);
console.log('Real 10-second view scheduler reaches all candidates and respects pause');

context.sourceRace={scope:'national',source_name:'Guam Election Commission report via Public Radio Guam',reviewed_snapshot:true,source_updated_at:'2026-11-03T15:30:00Z'};
vm.runInContext("state.demo=false;state.sources=[{id:'national',name:'National',status:'connected'},{id:'guam',name:sourceRace.source_name,status:'error'}]",context);
assert.equal(context.sourceFor(context.sourceRace).id,'guam');
assert.match(context.sourceSuffix(context.sourceRace),/LAST REVIEWED DATA/);
console.log('Guam exact source attribution and changed-report warning passed');
