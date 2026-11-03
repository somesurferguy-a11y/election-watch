const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let current=Date.parse('2026-11-03T23:00:00Z');
class Clock extends Date{static now(){return current;}}
const timers=[{dataset:{countdown:'2026-11-03T19:00:00-05:00'}},{dataset:{countdown:'2026-11-03T20:00:00-05:00'}},{dataset:{countdown:'2026-11-04T01:00:00-05:00'}}];
const context={Date:Clock,state:{settings:{local_spotlight:true}},views:['national','power','florida','indian_river','night'],pages:{},document:{addEventListener(){},querySelectorAll(){return timers;}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/js/night.js','utf8'),context);
assert.equal(vm.runInContext("rotationPlaylist().filter(v=>v==='indian_river').length",context),3);
const modes=vm.runInContext("(()=>{const modes=[];for(let i=0;i<44;i++){if(nextAutoView()==='night')modes.push(nightMode);}return modes;})()",context);
assert.equal(JSON.stringify(modes),JSON.stringify(['updates','closings','close','amendments']));
vm.runInContext('state.settings.local_spotlight=false',context);
assert.equal(vm.runInContext('rotationPlaylist().length',context),context.views.length);
vm.runInContext('updateCountdowns()',context);
assert.equal(timers[0].textContent,'1h 0m 0s');assert.equal(timers[1].textContent,'2h 0m 0s');assert.equal(timers[2].textContent,'7h 0m 0s');
current=Date.parse('2026-11-04T06:01:00Z');vm.runInContext('updateCountdowns()',context);assert.equal(timers[2].textContent,'Scheduled time reached');
const bar={};context.$=()=>bar;context.view='indian_river';context.online=true;context.esc=x=>String(x);context.state={demo:false,server_time:new Clock(current).toISOString(),sources:[{id:'indian_river',status:'not_published',last_attempt:new Clock(current-60000).toISOString()}]};
vm.runInContext('updateFreshness()',context);assert.match(bar.innerHTML,/awaiting official November returns/);assert.match(bar.innerHTML,/last attempted check 1m ago/);assert.doesNotMatch(bar.innerHTML,/checked never/);
console.log('7 JavaScript checks passed: local weighting, section rotation, opt-out, Eastern/Central split, midnight rollover, expired timer.');
// Source health follows visible cards, including county pins on other views.
let visibleCards=[];
context.document.querySelectorAll=selector=>selector==='[data-open-race]'?visibleCards:timers;
context.time=x=>x;
context.state.sources=[
 {id:'indian_river',name:'Indian River County Supervisor of Elections',status:'error',last_success:new Clock(current-3600000).toISOString()},
 {id:'florida',name:'Florida Division of Elections',status:'connected',last_success:new Clock(current).toISOString()},
 {id:'national',name:'National feed',status:'connected',last_success:new Clock(current).toISOString()}
];
context.state.races=[
 {id:'county',scope:'indian_river',source_name:'Indian River County Supervisor of Elections'},
 {id:'state',scope:'florida',source_name:'Florida Division of Elections'},
 {id:'federal',scope:'national',source_name:'National feed'},
 {id:'county-state-feed',scope:'indian_river',source_name:'Florida Division of Elections'}
];
const show=(ids,view='watchlist')=>{visibleCards=ids.map(id=>({dataset:{openRace:id}}));context.view=view;context.updateFreshness();return bar.innerHTML;};
let html=show(['county']);
assert.match(html,/<span class="amber">County: checked 1h ago/);
assert.match(html,/Florida: checked 0s ago/);assert.doesNotMatch(html,/National:/);
assert.match(show(['county'],'national'),/County: checked 1h ago/);
html=show(['county','state','federal']);
assert.match(html,/County:/);assert.match(html,/Florida:/);assert.match(html,/National:/);
assert.equal((html.match(/Florida:/g)||[]).length,1);
assert.doesNotMatch(show(['county-state-feed']),/County:/);
context.state.settled_races=[{id:'earlier',scope:'indian_river',source_name:'Indian River County Supervisor of Elections'}];
assert.match(show(['earlier']),/County: checked 1h ago/);
html=show([],'indian_river');assert.match(html,/County:/);assert.match(html,/Florida:/);
html=show([],'watchlist');assert.match(html,/Florida:/);assert.match(html,/National:/);
delete context.document.querySelectorAll;
assert.doesNotThrow(()=>context.updateFreshness());assert.match(bar.innerHTML,/National:/);
console.log('Visible-card source checks passed: stale county pins, mixed feeds, settled races, source attribution and DOM fallback.');
