"""Thread-safe snapshots, source health, host preferences and update events."""
import copy
import hashlib
import json
import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import config
from feeds import ADAPTERS, NotConfigured, NotPublished
from validation import iso_now
from roster import load_roster,compose_roster,names_for,normalized
from history import load_history
from watch_features import night_guide,competitive_races
from candidate_profiles import enrich_candidates,profiles

VIEWS=['national','power','florida','indian_river','watchlist','comparisons','history','night','health']
DEFAULTS={'mode':config.DEFAULT_MODE,'view':'national','rotation':True,'rotation_seconds':25,'local_spotlight':True,'ticker':True,'ticker_paused':False,'ticker_seconds':12,'reduced_motion':False,'text_scale':1.0,'pins':[]}

class Database:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(path,check_same_thread=False)
        self.lock=threading.RLock()
        with self.conn:
            self.conn.execute('CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            self.conn.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, source TEXT, created TEXT, payload TEXT)')
    def get(self,key,default=None):
        with self.lock:
            row=self.conn.execute('SELECT value FROM kv WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else copy.deepcopy(default)
    def put(self,key,value):
        encoded=json.dumps(value,allow_nan=False)
        with self.lock,self.conn:self.conn.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',(key,encoded))
    def snapshot(self,source,payload):
        with self.lock,self.conn:
            self.conn.execute('INSERT INTO snapshots(source,created,payload) VALUES(?,?,?)',(source,iso_now(),json.dumps(payload,allow_nan=False)))
            # Bounded history: latest 120 changed snapshots per source, plus latest persisted state.
            self.conn.execute('DELETE FROM snapshots WHERE source=? AND id NOT IN (SELECT id FROM snapshots WHERE source=? ORDER BY id DESC LIMIT 120)',(source,source))

def age(stamp):
    if not stamp:return None
    return max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace('Z','+00:00'))).total_seconds())

def fingerprint(payload):
    def clean(obj):
        if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items() if k not in ['source_updated_at','metadata_updated_at','retrieved_at','checked_at']}
        if isinstance(obj,list):return [clean(v) for v in obj]
        return obj
    return hashlib.sha256(json.dumps(clean(payload),sort_keys=True,allow_nan=False).encode()).hexdigest()

def leader(race):
    cs=sorted(race.get('candidates',[]),key=lambda c:c['votes'],reverse=True)
    if not cs or cs[0]['votes']==0 or (len(cs)>1 and cs[0]['votes']==cs[1]['votes']):return None
    return cs[0]

def chamber_summary(races):
    # Count only explicitly attributed calls. Never infer calls from a lead.
    output=[]
    for chamber,total,threshold in [('house',435,218),('senate',100,51)]:
        seats={'DEM':0,'REP':0,'OTHER':0};seen=set()
        for r in races:
            if r.get('scope')!='national' or r.get('chamber')!=chamber or r.get('status') not in ['projected','certified']:continue
            seat_id=r.get('seat_id',r['id'])
            if seat_id in seen:continue
            winner=next((c for c in r['candidates'] if c['id']==r.get('winner_id')),None)
            if not winner:continue
            seen.add(seat_id);p=winner.get('caucus',winner['party']);seats[p if p in seats else 'OTHER']+=1
        if sum(seats.values())>total:raise ValueError('Chamber seat calls exceed capacity')
        output.append({'chamber':chamber,'total':total,'threshold':threshold,'seats':seats,'unresolved_or_unprovided':total-sum(seats.values()),
            'note':'Only attributed seats in the connected dataset are counted. Seats not up, vacancies and missing seats remain unprovided unless included by the provider. Senate 50–50 control also depends on the vice president.'})
    return output

class Engine:
    def __init__(self,data_dir=None):
        self.dir=Path(data_dir or config.DATA_DIR);self.dir.mkdir(parents=True,exist_ok=True)
        self.db=Database(self.dir/'watch.sqlite3');self.lock=threading.RLock();self.stop_event=threading.Event()
        self.settings=self.db.get('settings',DEFAULTS)
        self.settings={**DEFAULTS,**self.settings}
        self.settings_revision=self.db.get('settings_revision',0)
        self.sources={}
        for key,meta in config.SOURCES.items():
            stored=self.db.get('source:'+key,{})
            self.sources[key]={'status':'pending',**stored,**meta,'busy':False,'next_due':0,'id':key}
        self.events=self.db.get('events',[])
        self.pool=ThreadPoolExecutor(max_workers=6,thread_name_prefix='feed')
        self.started=False
    def start(self):
        if self.started:return
        self.started=True
        self.thread=threading.Thread(target=self.run,daemon=True,name='refresh-scheduler');self.thread.start()
    def close(self):
        self.stop_event.set()
        if self.started:self.thread.join(timeout=2)
        self.pool.shutdown(wait=True)
    def run(self):
        while not self.stop_event.is_set():
            self.refresh_due()
            self.stop_event.wait(1)
    def refresh_due(self):
        with self.lock:
            for key,state in self.sources.items():
                if not state['busy'] and time.time()>=state['next_due']:
                    state['busy']=True
                    self.pool.submit(self.refresh_one,key)
    def refresh_one(self,key):
        with self.lock:
            state=self.sources[key]
            if state.get('imported') and ((key=='national' and not config.NATIONAL_JSON_URL) or (key=='polls' and not config.POLLS_JSON_URL) or key=='indian_river'):
                state['status']='imported';state['next_due']=time.time()+state['interval'];state['busy']=False
                self.save_source(key)
                return
            state['last_attempt']=iso_now()
        try:
            payload=ADAPTERS[key]()
            self.accept(key,payload)
        except Exception as exc:
            logging.warning('%s: %s',key,exc)
            with self.lock:
                state=self.sources[key];state['failures']=state.get('failures',0)+1
                state['status']='not_published' if isinstance(exc,NotPublished) or isinstance(exc,urllib.error.HTTPError) and exc.code==404 else 'not_configured' if isinstance(exc,NotConfigured) else 'error'
                state['error']=str(exc)[:400]
                delay=min(900,state['interval']*(2**min(state['failures']-1,4)))
                if isinstance(exc,urllib.error.HTTPError) and exc.code==429:
                    try:delay=max(delay,int(exc.headers.get('Retry-After',0)))
                    except (ValueError,TypeError):pass
                if isinstance(exc,NotConfigured):delay=state['interval']
                state['next_due']=time.time()+min(delay,7200)
                self.save_source(key)
        finally:
            with self.lock:self.sources[key]['busy']=False
    def save_source(self,key):
        self.db.put('source:'+key,{k:v for k,v in self.sources[key].items() if k not in ['busy']})
    def accept(self,key,payload,imported=False):
        with self.lock:
            state=self.sources[key];now=iso_now();old=state.get('payload',{})
            if key=='polls':
                baseline=self.db.get('poll_baseline',{})
                for poll in payload.get('polls',[]):
                    if datetime.now(timezone.utc).date().isoformat()<config.ELECTION_DATE:
                        baseline.setdefault(poll['id'],{**poll,'baseline_at':now})
                self.db.put('poll_baseline',baseline)
                payload={**payload,'polls':list(baseline.values()) or payload.get('polls',[])}
            changed=fingerprint(old)!=fingerprint(payload)
            if changed:
                state['last_observed_change']=now
                self.make_events(key,old,payload)
                self.db.snapshot(key,payload)
            state.update(payload=payload,last_success=now,source_updated_at=payload.get('source_updated_at'),status='imported' if imported else 'connected',error=None,failures=0,next_due=time.time()+state['interval'],imported=imported)
            if key=='national' and payload.get('refresh_after'):
                state['interval']=max(60,min(900,int(payload['refresh_after'])))
                state['next_due']=time.time()+state['interval']
            if imported:state['last_attempt']=now
            self.save_source(key)
            if key in ['polymarket','kalshi']:
                baseline=self.db.get('market_baseline',{})
                # First observed snapshot before election day; never overwrite it silently.
                if datetime.now(timezone.utc).date().isoformat()<config.ELECTION_DATE:
                    for m in payload.get('markets',[]):
                        baseline.setdefault(m['id'],{**m,'baseline_at':now})
                    self.db.put('market_baseline',baseline)
    def make_events(self,key,old,new):
        previous={r['id']:r for r in old.get('races',[])}
        now=iso_now()
        ballot=load_roster()['races'] if new.get('races') else []
        for r in new.get('races',[]):
            before=previous.get(r['id']);winner=leader(r);oldwinner=leader(before) if before else None
            message=None
            roster_match=next((b for b in ballot if b['scope']==r['scope'] and (b['id']==r['id'] or normalized(r['name']) in names_for(b))),{})
            seats=roster_match.get('seats_to_elect',1)
            if seats>1:
                if before and sum(c['votes'] for c in r['candidates'])!=sum(c['votes'] for c in before['candidates']):
                    message=f"{r['name']}: candidate totals updated — {seats} seats; no winners inferred"
            elif r['status'] in ['certified','projected'] and (not before or before.get('winner_id')!=r.get('winner_id') or before['status']!=r['status']):
                called=next((c for c in r['candidates'] if c['id']==r.get('winner_id')),None)
                if called:message=f"{r['name']}: {called['name']} — {r['status']} by {r.get('call_source',r['source_name'])}"
            elif before and sum(c['votes'] for c in r['candidates'])<sum(c['votes'] for c in before['candidates']):message=f"{r['name']}: source corrected vote totals; counts decreased"
            elif before and winner and oldwinner and winner['id']!=oldwinner['id']:message=f"{r['name']}: {winner['name']} takes the lead — unofficial"
            elif before and winner and sum(c['votes'] for c in r['candidates'])!=sum(c['votes'] for c in before['candidates']):message=f"{r['name']}: updated totals; {winner['name']} leads — unofficial"
            total=sum(c['votes'] for c in r['candidates']);previous_total=sum(c['votes'] for c in before['candidates']) if before else None
            if not message and total>0 and (not before or previous_total==0):message=f"{r['name']}: first reported totals — {total:,} candidate votes; no winner inferred"
            if not message and before and {c['id']:c['votes'] for c in r['candidates']}!={c['id']:c['votes'] for c in before['candidates']} and total>0:message=f"{r['name']}: candidate counts revised; total unchanged"
            if message:
                self.events.append({'id':hashlib.sha256((r['id']+message+now).encode()).hexdigest()[:20],'text':message,'at':now,'source':r['source_name'],'race_id':roster_match.get('id',r['id']),'scope':r['scope'],'demo':False,'total_votes':total,'previous_total':previous_total,'vote_delta':total-previous_total if previous_total is not None else None})
        self.events=self.events[-100:];self.db.put('events',self.events)
    def update_settings(self,patch):
        with self.lock:
            new={**self.settings}
            for key,value in patch.items():
                if key not in DEFAULTS:raise ValueError('Unknown setting: '+key)
                if key in ['rotation','local_spotlight','ticker','ticker_paused','reduced_motion'] and type(value) is not bool:raise ValueError('Expected true or false')
                if key=='mode' and value not in ['live','demo']:raise ValueError('Invalid mode')
                if key=='view' and value not in VIEWS:raise ValueError('Invalid view')
                if key in ['rotation_seconds','ticker_seconds','text_scale']:
                    from validation import number
                    low,high=(10,120) if key=='rotation_seconds' else (5,60) if key=='ticker_seconds' else (.8,1.3)
                    value=number(value,low,high)
                if key=='pins' and (not isinstance(value,list) or len(value)>100 or any(not isinstance(x,str) or len(x)>200 for x in value)):raise ValueError('Invalid watchlist')
                new[key]=value
            self.settings=new
            # Pins update without resetting a TV's current view or pause state.
            if any(k!='pins' for k in patch):self.settings_revision+=1
            self.db.put('settings',new);self.db.put('settings_revision',self.settings_revision)
            return copy.deepcopy(new)
    def check_now(self):
        with self.lock:
            queued=[]
            for key,s in self.sources.items():
                if not s['busy'] and time.time()>=s['next_due']:
                    s['busy']=True;self.pool.submit(self.refresh_one,key);queued.append(key)
            return queued
    def public_sources(self):
        out=[]
        with self.lock:
            for key,s in self.sources.items():
                item={k:copy.deepcopy(v) for k,v in s.items() if k not in ['payload','next_due','failures']}
                item['seconds_since_success']=age(s.get('last_success'))
                item['source_age_seconds']=age(s.get('source_updated_at'))
                item['publication_delayed']=s['kind']=='results' and not s.get('imported') and datetime.now(timezone.utc).date().isoformat()>=config.ELECTION_DATE and item['source_age_seconds'] is not None and item['source_age_seconds']>max(300,s['interval']*5)
                item['next_check_at']=datetime.fromtimestamp(s.get('next_due') or time.time(),timezone.utc).isoformat()
                item['has_data']=bool(s.get('payload'))
                item['retrieval_overdue']=not s.get('imported') and item['seconds_since_success'] is not None and item['seconds_since_success']>max(180,s['interval']*3)
                if item['retrieval_overdue'] and item['status']=='connected':item['status']='delayed'
                if item['publication_delayed'] and item['status']=='connected':item['status']='source_delayed'
                if s.get('payload',{}).get('provider_stale') and item['status']=='connected':item['status']='source_delayed'
                out.append(item)
        return out
    def state(self):
        with self.lock:
            settings=copy.deepcopy(self.settings)
            demo=settings['mode']=='demo'
            ballot_roster=load_roster() if not demo else {'races':[],'settled_races':[],'verified_at':None}
            if demo:
                payload=json.loads((config.ROOT/'data'/'demo_data.json').read_text(encoding='utf-8'))
                races=payload['races'];polls=payload['polls'];markets=payload['markets'];chambers=payload['chambers'];events=payload['ticker_events']
            else:
                payloads={key:copy.deepcopy(s.get('payload',{})) for key,s in self.sources.items()}
                races=[]
                for key in ['national','florida','indian_river']:
                    batch=payloads[key].get('races',[])
                    races.extend(batch)
                # Stable ID dedup: one current record per ID, no arithmetic merging across providers.
                races=list({r['id']:r for r in races}.values())
                races=enrich_candidates(compose_roster(ballot_roster,races))
                ballot_roster['settled_races']=enrich_candidates(ballot_roster.get('settled_races',[]))
                polls=payloads['polls'].get('polls',[])
                markets=payloads['polymarket'].get('markets',[])+payloads['kalshi'].get('markets',[])
                chambers=chamber_summary(races)
                events=[e for e in self.events if (age(e['at']) or 0)<1800]
            sources=self.public_sources()
            baseline=self.db.get('market_baseline',{}) if not demo else {}
            for m in markets:
                m['baseline']=baseline.get(m['id'])
            pins=set(settings['pins'])
            events=sorted(events,key=lambda e:(e.get('race_id') in pins,e.get('scope')=='indian_river',e.get('at','')),reverse=True)
            outages=[s for s in sources if s['status'] in ['error','delayed','source_delayed']]
            if not demo:
                for s in outages:
                    events.insert(0,{'id':'outage:'+s['id'],'text':s['name']+': '+('showing last known data' if s['has_data'] else 'feed unavailable'),'at':s.get('last_attempt'),'source':'Source health','demo':False,'scope':'health'})
            national_ready=bool(self.sources['national'].get('payload',{}).get('races'))
            county_ready=bool(self.sources['indian_river'].get('payload',{}).get('races'))
            return {'election_date':config.ELECTION_DATE,'demo':demo,'server_time':iso_now(),'settings':settings,'settings_revision':self.settings_revision,
                'races':races,'polls':polls,'markets':markets,'chambers':chambers,'ticker_events':events,'sources':sources,
                'settled_races':ballot_roster.get('settled_races',[]),'roster_verified_at':ballot_roster.get('verified_at'),
                'history':load_history() if not demo else None,
                'night_guide':night_guide() if not demo else None,'competitive':competitive_races(races),
                'profile_coverage':profiles().get('coverage_note') if not demo else 'Fictional demonstration candidates have no real service records or photos.',
                'power':(self.sources['power'].get('payload') or json.loads((config.ROOT/'data'/'power.json').read_text(encoding='utf-8'))) if not demo else None,
                'coverage':{'national':self.sources['national'].get('payload',{}).get('coverage_note') or ('Connected provider snapshot: coverage is limited to the supplied contests; unprovided seats are shown explicitly.' if national_ready else 'Free multi-state source pending. Florida federal races are shown; full nationwide coverage is not guaranteed.'),
                    'indian_river':'November ballot roster is populated independently of vote returns. City and district eligibility varies. Previously decided and unopposed offices are listed separately; no returns are inferred.' if ballot_roster['races'] else 'State-file county portions available; complete county and municipal coverage awaits the county ENR or a sourced host import.'},
                'snapshot_count':len(self.events)}
