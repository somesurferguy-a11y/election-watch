const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const c={document:{addEventListener(){}},esc:x=>String(x).replaceAll('<','&lt;'),num:x=>String(x)};vm.createContext(c);
for(const f of ['candidate-profiles','night'])vm.runInContext(fs.readFileSync('static/js/'+f+'.js','utf8'),c);
c.r={seats_to_elect:3,has_results:true,candidates:[{name:'A',votes:100},{name:'B',votes:90},{name:'C',votes:80},{name:'D',votes:75}]};
const run=x=>vm.runInContext(x,c);
assert.match(run('councilCutoff(r)'),/5 vote gap/);c.r.candidates[3].votes=80;assert.match(run('councilCutoff(r)'),/TIED AT CUTOFF/);
c.r.result_incomplete=true;assert.match(run('councilCutoff(r)'),/awaiting complete/);c.r.result_incomplete=false;c.r.candidates[0].votes_available=false;assert.match(run('councilCutoff(r)'),/awaiting complete/);
for(const [text,label] of [['X takes the lead — unofficial','Lead change'],['first reported totals','First totals'],['source corrected totals','Source correction'],['X — projected by Official','Attributed call'],['updated totals','Vote update']]){c.e={text};assert.equal(run('changeCategory(e)'),label);}
console.log('Council cutoff and meaningful change checks passed');
