const origin='https://somesurferguy-a11y.github.io';
export default {async fetch(request,env){
 const path=new URL(request.url).pathname;
 const headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Methods':'GET, OPTIONS','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
 if(request.method==='OPTIONS')return new Response(null,{headers});
 if(!['/state.json','/lease','/release','/checkpoint','/publish'].includes(path))return new Response('Not found',{status:404,headers});
 if(path==='/state.json'&&request.method!=='GET')return new Response('Method not allowed',{status:405,headers});
 if(path!=='/state.json'){
  if(request.method!=='POST')return new Response('Method not allowed',{status:405,headers});
  if(!env.PUBLISH_TOKEN)return new Response('Publisher not configured',{status:503,headers});
  const expected=new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode('Bearer '+env.PUBLISH_TOKEN)));
  const supplied=new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(request.headers.get('Authorization')||'')));
  let mismatch=0;for(let i=0;i<expected.length;i++)mismatch|=expected[i]^supplied[i];
  if(mismatch)return new Response('Unauthorized',{status:401,headers});
 }
 const response=await env.SNAPSHOTS.get(env.SNAPSHOTS.idFromName('election-2026')).fetch(request);
 const result=new Response(response.body,response);for(const [k,v] of Object.entries(headers))result.headers.set(k,v);return result;
}};
export class SnapshotStore {
 constructor(ctx,env){this.sql=ctx.storage.sql;this.sql.exec('CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY, body BLOB, stamp TEXT)');this.sql.exec('CREATE TABLE IF NOT EXISTS lease (id INTEGER PRIMARY KEY, owner TEXT, expires INTEGER)');}
 async fetch(request){
  const path=new URL(request.url).pathname,now=Date.now();
  if(path==='/state.json'){
   const row=[...this.sql.exec('SELECT body,stamp FROM snapshot WHERE id=1')][0];
   return row?new Response(row.body,{headers:{'Content-Type':'application/json','Content-Encoding':'gzip','X-Snapshot-Time':row.stamp}}):Response.json({error:'First live snapshot pending'},{status:503});
  }
  const owner=request.headers.get('X-Collector-ID');if(!owner||owner.length>100)return new Response('Collector ID required',{status:400});
  const lease=[...this.sql.exec('SELECT owner,expires FROM lease WHERE id=1')][0];
  if(lease&&lease.owner!==owner&&lease.expires>now)return new Response('Another collector is active',{status:409});
  if(path==='/lease'){
   this.sql.exec('INSERT OR REPLACE INTO lease VALUES (1,?,?)',owner,now+180000);return Response.json({leased:true});
  }
  if(path==='/release'){
   if(lease?.owner===owner)this.sql.exec('DELETE FROM lease WHERE id=1');
   return Response.json({released:true});
  }
  if(!lease||lease.owner!==owner||lease.expires<=now)return new Response('Lease expired',{status:409});
  if(path==='/checkpoint'&&!request.headers.has('Content-Encoding')){
   const row=[...this.sql.exec('SELECT body,stamp FROM snapshot WHERE id=2')][0];
   return row?new Response(row.body,{headers:{'Content-Type':'application/octet-stream'}}):new Response('No checkpoint',{status:404});
  }
  if(request.headers.get('Content-Encoding')!=='gzip')return new Response('Compressed snapshot required',{status:415});
  const body=await request.arrayBuffer();if(body.byteLength>1800000)return new Response('Snapshot too large',{status:413});
  const stamp=request.headers.get('X-Snapshot-Time');if(!stamp||!Number.isFinite(Date.parse(stamp))||Math.abs(Date.parse(stamp)-now)>180000)return new Response('Snapshot timestamp invalid',{status:400});
  this.sql.exec('INSERT OR REPLACE INTO snapshot VALUES (?, ?, ?)',path==='/checkpoint'?2:1,body,stamp);return Response.json({published:true,at:stamp});
 }
}
