const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={document:{addEventListener(){}},state:{demo:false},esc:s=>String(s??''),view:'indian_river',pages:{},pageCount:0};vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/candidate-profiles.js','utf8'),context);
const app=fs.readFileSync('static/js/app.js','utf8');vm.runInContext(app.slice(app.indexOf('function candidateWindow('),app.indexOf('function candidatesHtml(')),context);
context.candidates=[{id:'a',name:'Challenger',votes:90,service:{incumbent:false}},{id:'b',name:'Incumbent',votes:10,service:{incumbent:true}}];
assert.equal(vm.runInContext('orderedCandidates(candidates)[0].id',context),'b');
context.race={candidates:context.candidates,seats_to_elect:3,has_results:true};assert.equal(vm.runInContext('candidateWindow(race).selected.length',context),2);
context.race.candidates=Array.from({length:8},(_,i)=>({id:String(i),name:'Candidate '+i,votes:0}));assert.equal(vm.runInContext('candidateWindow(race).selected.length',context),8);
context.race.candidates=[{name:'A',votes:40},{name:'B',votes:30},{name:'C',votes:15},{name:'D',votes:15}];assert.match(vm.runInContext('seatRank(race.candidates[2],race)',context),/Tied at cutoff/);
assert.doesNotMatch(vm.runInContext('seatRank(race.candidates[2],race)',context),/elected|winner/);
context.race.has_results=false;assert.equal(vm.runInContext('seatRank(race.candidates[0],race)',context),'');
context.races=[{id:'a'},{id:'b'},{id:'vero',seats_to_elect:3},{id:'c'}];vm.runInContext('racePage(races)',context);assert.equal(context.pageCount,3);context.pages.indian_river=1;assert.equal(vm.runInContext('racePage(races)[0].id',context),'vero');
context.candidate={name:'Test Person',photo:{path:'https://external.example/photo.jpg'}};assert.doesNotMatch(vm.runInContext('portraitHtml(candidate)',context),/<img/);
assert.equal(vm.runInContext('isPerson({name:"Yes for Approval"})',context),false);
assert.equal(vm.runInContext('serviceDetails({candidates:[{name:"Yes"},{name:"No"}]})',context),'');
context.cropPhoto={path:'/static/portraits/abcdef123456.jpg',crop:{x:1110,y:224,width:128,height:110,source_width:1280,source_height:720}};
context.croppedCandidate={name:'Craig MacCoy',photo:context.cropPhoto};
const frame=vm.runInContext('portraitHtml(croppedCandidate)',context);assert.match(frame,/viewBox="1110 224 128 110"/);assert.match(frame,/preserveAspectRatio="xMidYMid slice"/);assert.match(frame,/<image href="\/static\/portraits\/abcdef123456.jpg"/);
context.cropPhoto.crop.width=9999;assert.equal(vm.runInContext('validPhotoCrop(cropPhoto)',context),null);
assert.doesNotMatch(vm.runInContext('portraitHtml(croppedCandidate)',context),/<img|<svg/);
context.cropPhoto.crop.width='128';assert.equal(vm.runInContext('validPhotoCrop(cropPhoto)',context),null);
console.log('9 candidate display checks passed: incumbent-first order, all multi-seat candidates, cutoff ties, pending ranks, whole-contest pagination, safe photo paths and ballot choices.');

for(const invalid of [null,false,0,'',{},[]]){context.cropPhoto.crop=invalid;assert.doesNotMatch(vm.runInContext('portraitHtml(croppedCandidate)',context),/<img|<svg/);}
context.cropPhoto.path='/static/portraits/abcdef123456.frame.jpg';delete context.cropPhoto.crop;assert.doesNotMatch(vm.runInContext('portraitHtml(croppedCandidate)',context),/<img|<svg/);
context.cropPhoto.crop={x:1110,y:224,width:128,height:110,source_width:1280,source_height:720};assert.match(vm.runInContext('portraitHtml(croppedCandidate)',context),/<svg/);
assert.equal(/^\/static\/portraits\/[a-f0-9]+\.(jpg|png|webp)$/.test(context.cropPhoto.path),false);

context.former={name:'Former Person',service:{incumbent:false,former_member:true,terms_started:null,terms_completed:null}};
assert.match(vm.runInContext('serviceBadge(former)',context),/Former member/);
assert.doesNotMatch(vm.runInContext('serviceBadge(former)',context),/0 completed/);
context.safeLink=u=>/^https:\/\//.test(u||'')?u:'';
context.reviewed={as_of:'2026-11-01',verification_status:'Partial history',evidence:[{url:'https://city.example/minutes',title:'Council minutes',supports:'Prior membership confirmed'},{url:'javascript:alert(1)',title:'Unsafe'}]};
const evidence=vm.runInContext('serviceEvidenceHtml(reviewed)',context);assert.match(evidence,/Council minutes/);assert.match(evidence,/2026-11-01/);assert.doesNotMatch(evidence,/javascript:|Unsafe/);

context.positionPhoto={position:{x:30,y:30}};assert.equal(vm.runInContext('photoPosition(positionPhoto)',context),'30% 30%');context.positionPhoto.position.x='30; color:red';assert.equal(vm.runInContext('photoPosition(positionPhoto)',context),'50% 15%');
context.cropPhoto.path='/static/portraits/abcdef123456.frame.webp';assert.match(vm.runInContext('portraitHtml(croppedCandidate)',context),/<svg/);context.cropPhoto.crop=null;assert.doesNotMatch(vm.runInContext('portraitHtml(croppedCandidate)',context),/<img|<svg/);

let imageError;const errorContext={document:{addEventListener(name,handler){if(name==='error')imageError=handler;}},HTMLImageElement:class {}};vm.createContext(errorContext);vm.runInContext(fs.readFileSync('static/js/candidate-profiles.js','utf8'),errorContext);let failureMarked=false;const photoFrame={style:{}};const portrait={classList:{add(name){failureMarked=name==='photo-failed';}}};imageError({target:{tagName:'image',closest(selector){return selector==='.portrait'?portrait:photoFrame;}}});assert.equal(failureMarked,true);assert.equal(photoFrame.style.display,'none');
