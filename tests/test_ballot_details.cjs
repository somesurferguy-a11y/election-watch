const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={esc:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),safeLink:x=>{try{const u=new URL(x);return u.protocol==='https:'?u.href:'';}catch{return '';}}};vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/ballot-details.js','utf8'),context);
assert.equal(context.ballotDetailsHtml({}),'');
const html=context.ballotDetailsHtml({ballot_text:'<script>bad</script>',yes_meaning:'Approve & apply',no_meaning:'Keep current provision',ballot_text_source_url:'https://www.voterfocus.com/SampleBallots/ballot'});
assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'));assert.ok(!html.includes('<script>'));
assert.ok(html.includes('Official sample ballot'));assert.ok(html.includes('Approve &amp; apply'));
assert.ok(!context.ballotDetailsHtml({ballot_text:'Question',ballot_text_source_url:'javascript:alert(1)'}).includes('href='));
console.log('6 ballot-details checks passed');
