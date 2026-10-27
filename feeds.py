"""Read-only official results and prediction-market adapters; no sample fallbacks."""
import csv
import gzip
import hashlib
import io
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlencode
import config
from validation import validate_results, validate_polls, number

class NotPublished(Exception): pass
class NotConfigured(Exception): pass

def fetch_url(url):
    if not url.startswith('https://'): raise ValueError('Feeds require HTTPS')
    request=urllib.request.Request(url,headers={'User-Agent':'ElectionWatch/2.0 (read-only local dashboard)', 'Accept':'application/json,text/plain,text/html', 'Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=config.HTTP_TIMEOUT) as r:
        raw=r.read(config.MAX_RESPONSE_BYTES+1)
        if len(raw)>config.MAX_RESPONSE_BYTES: raise ValueError('Feed exceeds size limit')
        headers=dict(r.headers)
    try: content=raw.decode('utf-8-sig')
    except UnicodeDecodeError: content=raw.decode('cp1252')
    stamp=headers.get('Last-Modified')
    timestamp=parsedate_to_datetime(stamp).isoformat() if stamp else None
    return content,timestamp

def fetch_json(url):
    content,_=fetch_url(url)
    return json.loads(content)

def stable_id(*parts):
    return hashlib.sha256('|'.join(str(x) for x in parts).encode()).hexdigest()[:20]

def amendment_title(name,election_date):
    # Official 2026 ballot numbers; source TSV omits a numbered jurisdiction field.
    titles={
        'Budget Stabilization Fund':1,
        'Exemption of Tangible Personal Property on Agricultural Land From Taxation':2,
        'Increased Homestead Exemption; Lower Cap On Increases In Non-Homestead Property Assessments':3,
    }
    number=titles.get(name) if election_date=='2026-11-03' else None
    return f'Amendment {number} — {name}' if number else name

def parse_florida(content, source_time=None, expected_date=config.ELECTION_DATE):
    rows=list(csv.DictReader(io.StringIO(content.replace('\r\r\n','\n')),delimiter='\t'))
    required={'ElectionDate','RaceCode','RaceName','CountyCode','CanNameLast','CanVotes','Precincts','PrecinctsReporting'}
    if not rows or not required.issubset(rows[0]): raise ValueError('Unexpected official file layout')
    groups={}
    seen=set()
    for row in rows:
        if datetime.strptime(row['ElectionDate'],'%m/%d/%Y').strftime('%Y-%m-%d')!=expected_date:
            raise ValueError('Election date mismatch; refusing another election')
        code=row['RaceCode'].strip()
        key=stable_id(code,row.get('Juris1num','').strip(),row.get('Juris2num','').strip(),row['RaceName'].strip())
        first=row.get('CanNameFirst','').strip(); last=row['CanNameLast'].strip(); middle=row.get('CanNameMiddle','').strip()
        name=(' / '.join([first,last]) if code=='GOV' else ' '.join(x for x in [first,middle,last] if x))
        party=row.get('PartyCode','').strip() or 'NON'
        cid=stable_id(key,name,party)
        dupe=(key,cid,row['CountyCode'])
        if dupe in seen: raise ValueError('Duplicate county candidate row; refusing double count')
        seen.add(dupe)
        votes=number(row['CanVotes'])
        if int(votes)!=votes: raise ValueError('Noninteger votes')
        for scope in (['florida','indian_river'] if row['CountyCode']=='IND' else ['florida']):
            gid=('irc:' if scope=='indian_river' else 'fl:')+key
            if gid not in groups:
                groups[gid]={'id':gid,'name':amendment_title(row['RaceName'].strip(),expected_date) if code=='AMD' else row['RaceName'].strip(),'scope':scope,'jurisdiction':'Indian River County portion' if scope=='indian_river' else 'Florida',
                    'office_code':code,'chamber':'house' if code=='USR' else 'senate' if code=='USS' else None,
                    'source_name':'Florida Division of Elections','source_url':config.FL_FILE_URL,'source_updated_at':source_time,
                    'candidates':{},'counties':{},'status':'awaiting','is_complete':False,
                    'coverage_note':'County portion of this contest; district/municipal eligibility varies.' if scope=='indian_river' else 'Totals across counties present in the official state file.',
                    'passage_threshold':60 if code=='AMD' else None,
                    'threshold_source':'https://www.leg.state.fl.us/statutes/index.cfm?submenu=3#A11S05' if code=='AMD' else None}
            g=groups[gid]
            c=g['candidates'].setdefault(cid,{'id':cid,'name':name,'party':party,'votes':0})
            c['votes']+=int(votes)
            precincts=(int(number(row['Precincts'])),int(number(row['PrecinctsReporting'])))
            previous=g['counties'].get(row['CountyCode'])
            if previous and previous!=precincts: raise ValueError('Inconsistent precinct totals in official file')
            g['counties'][row['CountyCode']]=precincts
    races=[]
    for g in groups.values():
        counties=g.pop('counties');g['candidates']=list(g['candidates'].values())
        g['precincts_total']=sum(v[0] for v in counties.values());g['precincts_reporting']=sum(v[1] for v in counties.values())
        g['status']='unofficial' if sum(c['votes'] for c in g['candidates']) else 'awaiting'
        races.append(g)
    payload={'election_date':expected_date,'demo':False,'source_updated_at':source_time,'races':races}
    # Historical fixture testing is explicit and never used by the live adapter.
    if expected_date==config.ELECTION_DATE: validate_results(payload)
    return payload

class Node:
    def __init__(self,tag='',attrs=None):self.tag=tag;self.attrs=dict(attrs or []);self.children=[];self.parts=[]
    def text(self):return ' '.join(' '.join(self.parts).split())
    def find(self,cls):
        out=[]
        for c in self.children:
            if cls in c.attrs.get('class','').split():out.append(c)
            out.extend(c.find(cls))
        return out

class Tree(HTMLParser):
    def __init__(self,html):
        super().__init__();self.root=Node();self.stack=[self.root];self.feed(html)
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs);self.stack[-1].children.append(node)
        if tag not in ['input','img','meta','link','br','hr','source','wbr']:self.stack.append(node)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):
        for node in self.stack:node.parts.append(data)

def parse_irc(content,url,source_time=None):
    tree=Tree(content).root
    if re.search(r'(test(ing)? results|test data|logic and accuracy)',tree.text(),re.I):
        raise ValueError('County source explicitly labels testing data; not election returns')
    # Require date and general-election title, even for a manually configured ID.
    if not re.search(r'Election Date:\s*11/3/2026',tree.text()) or not re.search(r'General Election',tree.text(),re.I):
        raise ValueError('County feed is not the November 3, 2026 general election')
    races=[]
    for node in tree.find('Race'):
        names=node.find('RaceName')
        if not names:continue
        labels=[x.text() for x in names[0].children if x.tag=='label']
        name=labels[-1] if labels else names[0].text()
        name=re.sub(r'Add or Take Out of Favorite Races','',name).strip()
        rid='irc:enr:'+node.attrs.get('id',stable_id(name))
        candidates=[]
        # ENR repeats candidates in graphical and detailed tables. Only ResultsRow.
        for row in node.find('ResultsRow'):
            choices=row.find('ChoiceColumn');nums=row.find('ResultsColumn')
            if len(choices)!=1 or len(nums)!=2:continue
            raw=choices[0].text();match=re.search(r'\(([^()]+)\)\s*$',raw)
            party=match.group(1) if match else 'NON';cname=raw[:match.start()].strip() if match else raw
            count=nums[-1].text().replace(',','')
            if not count.isdigit():raise ValueError('Invalid county vote count')
            candidates.append({'id':stable_id(rid,cname,party),'name':cname,'party':party,'votes':int(count)})
        if not candidates:raise ValueError('County layout changed: candidate rows missing')
        races.append({'id':rid,'name':name,'scope':'indian_river','jurisdiction':'Indian River County',
            'status':'unofficial' if sum(c['votes'] for c in candidates) else 'awaiting','is_complete':False,
            'source_name':'Indian River County Supervisor of Elections','source_url':url,'source_updated_at':source_time,
            'candidates':candidates,'coverage_note':'Eligibility varies by district and municipality. No winner is inferred.'})
    if not races:raise ValueError('County feed returned no parsable races')
    return validate_results({'election_date':config.ELECTION_DATE,'demo':False,'races':races,'source_updated_at':source_time})

def florida_feed():
    content,stamp=fetch_url(config.FL_FILE_URL)
    return parse_florida(content,stamp)

def irc_feed():
    eid=config.IRC_GENERAL_ID
    if eid and not eid.isdigit():raise ValueError('County election ID must be numeric')
    if not eid:
        html,_=fetch_url(config.IRC_ARCHIVE_URL)
        for value,label in re.findall(r'<option[^>]*value=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</option>',html,re.S|re.I):
            if re.search(r'11/0?3/2026',label) and 'general' in label.lower() and re.fullmatch(r'IND\|\d+',value):eid=value.split('|')[1];break
    if not eid:raise NotPublished('November county results feed is not linked yet. The verified ballot roster is already populated; vote returns remain pending.')
    url=f'https://enr.electionsfl.org/IND/{eid}/Summary/'
    content,stamp=fetch_url(url)
    return parse_irc(content,url,stamp)

def national_feed():
    if config.NATIONAL_JSON_URL:return validate_results(fetch_json(config.NATIONAL_JSON_URL))
    races=[];timestamps=[];counting=False;stale=False
    for office in ['House','Senate']:
        data=cached_json('https://openamerica.io/elections/results.json?'+urlencode({'year':2026,'office':office}))
        part=parse_openamerica(data,office)
        races.extend(part['races'])
        if data.get('as_of'):timestamps.append(data['as_of'])
        counting=counting or data.get('counting',False);stale=stale or data.get('stale',False)
    payload={'election_date':config.ELECTION_DATE,'demo':False,'races':races,'source_updated_at':max(timestamps) if timestamps else None,
        'refresh_after':60 if counting else 600,'provider_stale':stale,
        'coverage_note':'Free multi-state counts via Open America: provider documents 22 states, plus direct Florida coverage here. No race calls. Missing contests and seats are unprovided, not zero. Full nationwide coverage is not guaranteed.'}
    return validate_results(payload)

JSON_CACHE={}
def cached_json(url):
    previous=JSON_CACHE.get(url,{})
    headers={'User-Agent':'ElectionWatch/2.0 (personal read-only watch-party dashboard)','Accept-Encoding':'gzip'}
    if previous.get('etag'):headers['If-None-Match']=previous['etag']
    request=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=config.HTTP_TIMEOUT) as response:
            raw=response.read(config.MAX_RESPONSE_BYTES+1)
            if len(raw)>config.MAX_RESPONSE_BYTES:raise ValueError('Feed too large')
            if response.headers.get('Content-Encoding')=='gzip':
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:raw=stream.read(config.MAX_RESPONSE_BYTES+1)
            if len(raw)>config.MAX_RESPONSE_BYTES:raise ValueError('Expanded feed too large')
            payload=json.loads(raw)
            JSON_CACHE[url]={'etag':response.headers.get('ETag'),'data':payload}
            return payload
    except urllib.error.HTTPError as exc:
        if exc.code==304 and 'data' in previous:return previous['data']
        raise

def parse_openamerica(data,office):
    if data.get('api')!=1 or data.get('year')!=2026 or data.get('office')!=office:
        raise ValueError('Unexpected national feed version, year or office; no replay may enter live mode')
    if not isinstance(data.get('races'),dict):raise ValueError('Unexpected national race layout')
    races=[]
    party_codes={'D':'DEM','R':'REP','I':'NPA','L':'LPF','G':'GRE'}
    for seat,row in data['races'].items():
        if not re.fullmatch(r'[A-Z]{2}(-(?:\d{2}|special))?',seat):raise ValueError('Invalid national seat key')
        # Florida's own file remains the authority here; never duplicate those races.
        if seat.startswith('FL'):continue
        rid='oa:'+office.lower()+':'+seat
        candidates=[{'id':stable_id(rid,c['n'],c['p']),'name':c['n'],'party':party_codes.get(c['p'],c['p'] or 'NON'),'votes':c['v']} for c in row.get('cands',[])]
        if not candidates:raise ValueError('National race missing candidate totals')
        if sum(c['votes'] for c in candidates)!=row['total']:raise ValueError('National candidate totals do not match race total')
        race={'id':rid,'seat_id':seat,'name':f'U.S. {office} — {seat}','jurisdiction':seat[:2],'scope':'national','chamber':office.lower(),
            'source_name':'Official state offices via Open America','source_url':'https://openamerica.io/elections/api/','source_updated_at':data.get('as_of'),
            'timestamp_scope':'provider-wide newest update','status':'unofficial' if row['total'] else 'awaiting','is_complete':False,
            'precinct_percent':row.get('pct_in'),'candidates':candidates,'coverage_note':'Counts from official state offices via Open America. Newest source timestamp covers the provider, not necessarily this race. All precincts reporting does not mean certified.'}
        races.append(race)
    return validate_results({'election_date':config.ELECTION_DATE,'demo':False,'races':races,'source_updated_at':data.get('as_of')})

def polls_feed():
    if config.POLLS_JSON_URL:return validate_polls(fetch_json(config.POLLS_JSON_URL))
    seed=config.ROOT/'data'/'polls_baseline.json'
    if not seed.is_file():raise NotConfigured('No traceable polling baseline available. Add sourced polls in the host panel.')
    data=json.loads(seed.read_text(encoding='utf-8'))
    url=data['polls'][0]['source_url']
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.stetson.edu/artsci/cpor/','Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=config.HTTP_TIMEOUT) as r:raw=r.read(2_000_001)
    if len(raw)>2_000_000 or hashlib.sha256(raw).hexdigest()!=data['verification_sha256']:
        raise ValueError('Published polling release changed. Retaining the reviewed baseline; review the new release before replacing figures.')
    return validate_polls(data)

def list_value(value):
    if isinstance(value,str):value=json.loads(value)
    if not isinstance(value,list):raise ValueError('Expected array of outcomes/prices')
    return value

def market_record(provider,mid,question,outcome,bid,ask,last,meta,volume,liquidity,url,rules,status,group):
    bid=number(bid,0,1) if bid is not None else None;ask=number(ask,0,1) if ask is not None else None
    last=number(last,0,1) if last is not None else None
    valid=bid is not None and ask is not None and bid<=ask
    price=(bid+ask)/2 if valid else last
    if price is None:raise ValueError('No market price')
    spread=round((ask-bid)*100,2) if valid else None
    flags=['Quote timestamp unavailable; check time is not trade time']
    if not valid:flags.append('No valid two-sided quote; showing last trade')
    if spread is not None and spread>5:flags.append('Wide spread')
    if volume is not None and float(volume)<1000:flags.append('Low volume')
    if status!='open':flags.append('Trading closed or suspended')
    return {'id':provider+':'+str(mid),'provider':provider,'contract_id':str(mid),'question':question,'outcome':outcome,
        'probability':round(price*100,2),'bid':bid,'ask':ask,'spread_pp':spread,'price_convention':'bid/ask midpoint' if valid else 'last trade',
        'metadata_updated_at':meta,'quote_updated_at':None,'volume':volume,'liquidity':liquidity,'source_url':url,'rules':rules,
        'status':status,'comparison_group':group,'flags':flags}

def parse_poly(markets,group):
    records=[]
    for m in markets:
        question=m.get('question','')
        if not re.search(r'(Democratic|Republican) Party control the (House|Senate) after the 2026 Midterm elections',question,re.I):continue
        outcomes=list_value(m['outcomes']);prices=list_value(m['outcomePrices'])
        if len(outcomes)!=len(prices) or 'Yes' not in outcomes:raise ValueError('Market outcomes do not align')
        yes=outcomes.index('Yes')
        # Bid/ask on these Gamma binary contracts describes the Yes outcome.
        records.append(market_record('Polymarket',m['id'],question,'Yes — '+('Democratic' if 'Democratic' in question else 'Republican')+' control',
            m.get('bestBid'),m.get('bestAsk'),prices[yes],m.get('updatedAt'),m.get('volumeNum',m.get('volume')),m.get('liquidityNum',m.get('liquidity')),
            'https://polymarket.com/event/'+m['slug'],m.get('description',''), 'closed' if m.get('closed') else 'open',group))
    return records

def polymarket_feed():
    records=[]
    for chamber in ['house','senate']:
        slug=f'which-party-will-win-the-{chamber}-in-2026'
        events=fetch_json('https://gamma-api.polymarket.com/events?'+urlencode({'slug':slug}))
        if not isinstance(events,list):raise ValueError('Unexpected market event response')
        for e in events:
            if e.get('slug')==slug:records.extend(parse_poly(e.get('markets',[]),'control-'+chamber))
    if not records:raise ValueError('No matching 2026 party-control markets returned')
    return {'markets':records,'source_updated_at':None}

def parse_kalshi(m):
    ticker=m['ticker']
    if not re.fullmatch(r'CONTROL[SH]-2026-[DR]',ticker):raise ValueError('Wrong election market')
    party='Democratic' if ticker.endswith('-D') else 'Republican'
    chamber='senate' if ticker.startswith('CONTROLS') else 'house'
    def dollars(key):
        if m.get(key+'_dollars') is not None:return m[key+'_dollars']
        return float(m[key])/100 if m.get(key) is not None else None
    return market_record('Kalshi',ticker,m['title'],'Yes — '+party+' control',dollars('yes_bid'),dollars('yes_ask'),dollars('last_price'),
        m.get('updated_time'),m.get('volume_fp',m.get('volume')),m.get('liquidity_dollars'),
        'https://kalshi.com/markets/'+m.get('event_ticker',ticker).lower(),m.get('rules_primary','')+' '+m.get('rules_secondary',''),
        'open' if m.get('status')=='active' else m.get('status','unknown'),'control-'+chamber)

def kalshi_feed():
    markets=[]
    for series in ['CONTROLS','CONTROLH']:
        data=fetch_json('https://external-api.kalshi.com/trade-api/v2/markets?'+urlencode({'event_ticker':series+'-2026','limit':100}))
        for m in data.get('markets',[]):
            if re.fullmatch(r'CONTROL[SH]-2026-[DR]',m.get('ticker','')):markets.append(parse_kalshi(m))
    if not markets:raise ValueError('No matching 2026 Kalshi contracts returned')
    return {'markets':markets,'source_updated_at':None}

def parse_power(house_html,senate_html):
    house=Tree(house_html).root.text();senate=Tree(senate_html).root.text()
    def count(text,pattern):
        match=re.search(pattern,text,re.I)
        if not match:raise ValueError('Official party balance layout changed; keeping last verified snapshot')
        return int(match.group(1))
    hr=count(house,r'(\d+)\s+Republicans');hd=count(house,r'(\d+)\s+Democrats')
    hi=count(house,r'(\d+)\s+Independent');hv=count(house,r'(\d+)\s+Vacancies')
    sr=count(senate,r'Majority Party:\s*Republicans\s*\((\d+) seats\)')
    sd=count(senate,r'Minority Party:\s*Democrats\s*\((\d+) seats\)')
    si=count(senate,r'Other Parties:\s*Independents\s*\((\d+) seats\)')
    if hr+hd+hi+hv!=435 or sr+sd+si!=100:raise ValueError('Official chamber totals do not reconcile')
    stamp=re.search(r'Last updated\s+(\d{1,2}/\d{1,2}/\d{2,4})',house,re.I)
    published=datetime.strptime(stamp.group(1),'%m/%d/%y' if len(stamp.group(1).split('/')[-1])==2 else '%m/%d/%Y').date().isoformat() if stamp else None
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'chambers':[
      {'chamber':'senate','DEM':sd,'REP':sr,'IND':si,'vacancies':0,'total':100,'threshold':51,'source_name':'U.S. Senate','source_url':'https://www.senate.gov/senators/','published_date':None},
      {'chamber':'house','DEM':hd,'REP':hr,'IND':hi,'vacancies':hv,'total':435,'threshold':218,'source_name':'House Radio-Television Gallery','source_url':'https://radiotv.house.gov/house-data/party-breakdown','published_date':published}]}

def power_feed():
    house,_=fetch_url('https://radiotv.house.gov/house-data/party-breakdown')
    senate,_=fetch_url('https://www.senate.gov/senators/')
    return parse_power(house,senate)

ADAPTERS={'florida':florida_feed,'indian_river':irc_feed,'national':national_feed,'polls':polls_feed,'polymarket':polymarket_feed,'kalshi':kalshi_feed,'power':power_feed}
