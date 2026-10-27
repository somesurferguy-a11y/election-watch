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
console.log('7 JavaScript checks passed: local weighting, section rotation, opt-out, Eastern/Central split, midnight rollover, expired timer.');
