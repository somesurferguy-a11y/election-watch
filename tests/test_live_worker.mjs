import assert from 'node:assert/strict';
import worker,{SnapshotStore} from '../cloudflare/worker.mjs';
import {gzipSync} from 'node:zlib';
class SQL {
 constructor(){this.snapshots=new Map();}
 exec(sql,...args){
  if(sql.startsWith('CREATE'))return [];
  if(sql.startsWith('SELECT body')){const row=this.snapshots.get(sql.includes('id=2')?2:1);return row?[row]:[];}
  if(sql.startsWith('SELECT owner'))return this.lease?[this.lease]:[];
  if(sql.startsWith('INSERT OR REPLACE INTO lease'))this.lease={owner:args[0],expires:args[1]};
  if(sql.startsWith('INSERT OR REPLACE INTO snapshot'))this.snapshots.set(args[0],{body:args[1],stamp:args[2]});
  if(sql.startsWith('DELETE FROM lease'))this.lease=null;
  return [];
 }
}
const store=new SnapshotStore({storage:{sql:new SQL()}}),env={PUBLISH_TOKEN:'test-token',SNAPSHOTS:{idFromName:()=>1,get:()=>store}};
const call=(path,method='GET',owner='a',body=null,extra={})=>worker.fetch(new Request('https://live.example'+path,{method,headers:{Authorization:'Bearer test-token','X-Collector-ID':owner,...extra},body}),env);
assert.equal((await call('/state.json')).status,503);
assert.equal((await call('/publish','POST','a','bad',{Authorization:'Bearer wrong'})).status,401);
assert.equal((await call('/lease','POST')).status,200);
assert.equal((await call('/lease','POST','b')).status,409);
assert.equal((await call('/publish','POST','a','invalid')).status,415);
const stamp=new Date().toISOString(),body=gzipSync(JSON.stringify({server_time:stamp}));
assert.equal((await call('/publish','POST','a',body,{'Content-Encoding':'gzip','X-Snapshot-Time':'2000-01-01'})).status,400);
assert.equal((await call('/publish','POST','a',body,{'Content-Encoding':'gzip','X-Snapshot-Time':stamp})).status,200);
assert.equal((await call('/checkpoint','POST')).status,404);
assert.equal((await call('/checkpoint','POST','a',body,{'Content-Encoding':'gzip','X-Snapshot-Time':stamp})).status,200);
assert.deepEqual(new Uint8Array(await (await call('/checkpoint','POST')).arrayBuffer()),new Uint8Array(body));
assert.equal((await call('/checkpoint','POST','a',null,{Authorization:'wrong'})).status,401);
const result=await call('/state.json');assert.equal(result.status,200);assert.equal(result.headers.get('Cache-Control'),'no-store');assert.equal(result.headers.get('Access-Control-Allow-Origin'),'https://somesurferguy-a11y.github.io');
assert.equal((await result.json()).server_time,stamp);
assert.equal((await call('/release','POST')).status,200);
assert.equal((await call('/lease','POST','b')).status,200);
console.log('14 live Worker checks passed');
