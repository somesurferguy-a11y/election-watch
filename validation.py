"""Validate imported and fetched data before it can enter the display."""
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit
from config import ELECTION_DATE

def iso_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def iso_time(value):
    if not isinstance(value, str):
        raise ValueError('A timestamp with an explicit timezone is required')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include Z or a UTC offset')
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

def number(value, low=0, high=1e12):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a number')
    n = float(value)
    if not math.isfinite(n) or not low <= n <= high:
        raise ValueError('Number out of range')
    return n

def text(value, maxlen=300):
    if not isinstance(value, str) or not value.strip() or len(value) > maxlen:
        raise ValueError('Missing or oversized text field')
    return value.strip()

def source_url(value):
    u = urlsplit(text(value, 2000))
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('Source link must be a public HTTPS URL')
    return value

def validate_results(payload):
    if not isinstance(payload, dict) or payload.get('election_date') != ELECTION_DATE or payload.get('demo') is not False:
        raise ValueError('Live results require election_date 2026-11-03 and demo: false')
    races = payload.get('races')
    if not isinstance(races, list) or len(races) > 3000:
        raise ValueError('races must be an array (maximum 3000)')
    ids = set()
    for race in races:
        rid = text(race.get('id'), 200)
        if rid in ids:
            raise ValueError('Duplicate race ID')
        ids.add(rid)
        text(race.get('name'))
        text(race.get('jurisdiction'))
        if race.get('chamber') not in [None,'house','senate']:raise ValueError('Unknown chamber')
        if race.get('is_complete') is not None and type(race['is_complete']) is not bool:raise ValueError('is_complete must be boolean')
        if race.get('coverage_note') is not None:text(race['coverage_note'],2000)
        if race.get('scope') not in ['national','florida','indian_river']:
            raise ValueError('Unknown race scope')
        if race.get('status') not in ['awaiting','unofficial','projected','certified','recount','runoff']:
            raise ValueError('Unknown race status')
        text(race.get('source_name'))
        source_url(race.get('source_url'))
        race['source_updated_at'] = iso_time(race['source_updated_at']) if race.get('source_updated_at') else None
        candidates = race.get('candidates')
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 100:
            raise ValueError('Each race needs candidates/outcomes')
        cids = set()
        for c in candidates:
            cid = text(c.get('id'),200)
            if cid in cids: raise ValueError('Duplicate candidate ID')
            cids.add(cid)
            text(c.get('name'))
            text(c.get('party','NON'),30)
            if c.get('caucus') is not None and c['caucus'] not in ['DEM','REP','OTHER']:raise ValueError('Invalid caucus')
            votes = number(c.get('votes'))
            if votes != int(votes): raise ValueError('Vote counts must be whole numbers')
            c['votes'] = int(votes)
        total=sum(c['votes'] for c in candidates)
        if total and datetime.now(timezone.utc).date().isoformat()<ELECTION_DATE:
            raise ValueError('Nonzero pre-election counts may be test data; refusing to present them as returns')
        # Derive shares from counts; never trust inconsistent imported shares.
        for c in candidates: c['percentage'] = round(c['votes']/total*100, 3) if total else 0
        if race['status'] in ['projected','certified']:
            if race.get('winner_id') not in cids: raise ValueError('Attributed winner ID required')
            text(race.get('call_source'))
            race['call_at'] = iso_time(race.get('call_at'))
        for field in ['precincts_reporting','precincts_total']:
            if race.get(field) is not None: race[field]=int(number(race[field],0,1000000))
        if race.get('precincts_reporting') is not None and race.get('precincts_total') is not None and race['precincts_reporting']>race['precincts_total']:
            raise ValueError('Reporting precincts exceed total')
        if race.get('passage_threshold') is not None:
            number(race['passage_threshold'],0,100)
            text(race.get('threshold_source'))
        if race.get('precinct_percent') is not None:race['precinct_percent']=number(race['precinct_percent'],0,100)
    payload['source_updated_at'] = iso_time(payload['source_updated_at']) if payload.get('source_updated_at') else None
    return payload

def validate_polls(payload):
    if not isinstance(payload, dict) or payload.get('demo') is not False or payload.get('election_date') != ELECTION_DATE:
        raise ValueError('Polls require election_date 2026-11-03 and demo: false')
    polls=payload.get('polls')
    if not isinstance(polls,list) or len(polls)>2000: raise ValueError('polls must be an array')
    for p in polls:
        for key in ['id','race_id','pollster','sponsor','population','method']:
            text(p.get(key))
        source_url(p.get('source_url'))
        start=datetime.strptime(p['field_start'],'%Y-%m-%d').date()
        end=datetime.strptime(p['field_end'],'%Y-%m-%d').date()
        if start>end or str(end)>ELECTION_DATE: raise ValueError('Invalid polling field dates')
        n=number(p.get('sample_size'),1,1e7)
        if n!=int(n):raise ValueError('Sample size must be whole')
        p['retrieved_at']=iso_time(p.get('retrieved_at'))
        shares=p.get('shares')
        if not isinstance(shares,list) or not shares:raise ValueError('Poll shares required')
        seen=set()
        for s in shares:
            cid=text(s.get('candidate_id'))
            if cid in seen:raise ValueError('Duplicate poll candidate')
            seen.add(cid)
            s['share']=number(s.get('share'),0,100)
        if sum(s['share'] for s in shares)>100.1:raise ValueError('Poll shares exceed 100%')
        if p.get('baseline_at'):p['baseline_at']=iso_time(p['baseline_at'])
    return payload
