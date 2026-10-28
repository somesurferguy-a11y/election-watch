"""Keep verified ballot identities independent of results-feed availability."""
import copy
import json
import re
import unicodedata
from pathlib import Path
import config
from validation import validate_results,source_url,iso_time

def normalized(value):
    value=unicodedata.normalize('NFKD',str(value).casefold().replace('&',' and '))
    return re.sub(r'[^a-z0-9]','',value)

def load_roster():
    path=config.ROOT/'data'/'ballot_roster.json'
    if not path.is_file():return {'races':[],'settled_races':[],'verified_at':None}
    payload=json.loads(path.read_text(encoding='utf-8'))
    if payload.get('schema_version')!=1 or payload.get('election_date')!=config.ELECTION_DATE or payload.get('demo') is not False:
        raise ValueError('Ballot roster election/version mismatch')
    iso_time(payload['verified_at'])
    validate_results({k:payload[k] for k in ['election_date','demo','races']})
    ids=set()
    for r in payload['races']+payload.get('settled_races',[]):
        if r['id'] in ids:raise ValueError('Duplicate ballot contest')
        ids.add(r['id'])
        source_url(r['roster_source_url'])
        if not 1<=r.get('seats_to_elect',1)<=20:raise ValueError('Invalid number of seats')
        if r.get('on_ballot') is False and r['status'] not in ['unopposed','elected_earlier']:raise ValueError('Invalid settled office status')
        # The ballot roster is not a covert source of election-night votes.
        if any(c['votes']!=0 for c in r['candidates']):raise ValueError('Ballot roster must not contain reported votes')
    return payload

def names_for(obj):
    return {normalized(x) for x in [obj['name'],*obj.get('result_names',[])]}

def merge_race(base,result):
    out=copy.deepcopy(base)
    if result is None:return out
    available=result['candidates'];used=set();candidates=[]
    for original in base['candidates']:
        matches=[(i,c) for i,c in enumerate(available) if c['id']==original['id'] or normalized(c['name']) in names_for(original)]
        c=copy.deepcopy(original)
        if len(matches)==1 and matches[0][0] not in used:
            i,row=matches[0];used.add(i);c.update(votes=row['votes'],votes_available=True)
            if row.get('caucus'):c['caucus']=row['caucus']
        else:c.update(votes=0,percentage=None,votes_available=False)
        candidates.append(c)
    extras=[copy.deepcopy(c) for i,c in enumerate(available) if i not in used]
    for c in extras:c['votes_available']=True
    candidates.extend(extras)
    complete=all(c['votes_available'] for c in candidates)
    total=sum(c['votes'] for c in candidates)
    for c in candidates:c['percentage']=round(c['votes']/total*100,3) if complete and total else 0 if complete else None
    for field in ['source_name','source_url','source_updated_at','precincts_reporting','precincts_total','precinct_percent','timestamp_scope','call_source','call_at','is_complete']:
        if field in result:out[field]=result[field]
    out.update(candidates=candidates,has_results=total>0,results_pending=total==0,status=result['status'],result_incomplete=not complete)
    if extras:out['roster_warning']='Results source includes a candidate not matched to the reviewed roster; source spelling is shown.'
    if base.get('seats_to_elect',1)>1 and result['status'] in ['projected','certified']:
        out['status']='unofficial'
        out['roster_warning']='Multi-seat contest: this adapter has no complete attributed winner list; individual leads are not declared winners.'
    if result.get('winner_id'):
        called=next((c for c in result['candidates'] if c['id']==result['winner_id']),None)
        mapped=next((c for c in candidates if called and (c['id']==called['id'] or normalized(called['name']) in names_for(c))),None)
        if mapped:out['winner_id']=mapped['id']
        else:out['status']='unofficial';out['roster_warning']='Winner identity does not match the reviewed ballot; no call displayed.'
    return out

def compose_roster(roster,results):
    """Map stable IDs and reviewed aliases only; never fuzzy-match or sum providers."""
    # Current official candidate status can supersede an older results-file shell.
    # Suppress only reviewed settled offices by stable ID or exact reviewed alias.
    settled=[r for r in roster.get('settled_races',[]) if r.get('on_ballot') is False]
    used={i for i,r in enumerate(results) if any(r.get('scope')==s['scope'] and
        (r['id']==s['id'] or normalized(r['name']) in names_for(s)) for s in settled)}
    out=[]
    for base in roster['races']:
        aliases=names_for(base)
        matches=[(i,r) for i,r in enumerate(results) if r.get('scope')==base['scope'] and (r['id']==base['id'] or normalized(r['name']) in aliases)]
        for i,_ in matches:used.add(i)
        # A county-specific return is preferred over a county portion in the state file.
        matches.sort(key=lambda pair:(pair[1]['id'].startswith('irc:enr:'),pair[1].get('source_name')!='Florida Division of Elections',pair[1]['id']==base['id']),reverse=True)
        out.append(merge_race(base,matches[0][1] if matches else None))
    for i,r in enumerate(results):
        if i not in used:
            r=copy.deepcopy(r);r['has_results']=any(c['votes'] for c in r['candidates']);r['on_ballot']=True
            out.append(r)
    return out
