"""Dated, reviewed election history. Never merged into live result totals."""
import csv
import io
import json
import re
from datetime import date, datetime
from functools import lru_cache
import config
from feeds import Tree, stable_id


def finish(contest):
    total=sum(c['votes'] for c in contest['candidates'])
    if total<=0:raise ValueError('Historical contest has no votes')
    for c in contest['candidates']:
        if type(c['votes']) is not int or c['votes']<0:raise ValueError('Invalid historical vote count')
        c['percentage']=100*c['votes']/total
        c['rank']=1+sum(other['votes']>c['votes'] for other in contest['candidates'])
    contest['total_votes']=total
    return contest


def parse_state_history(content,election_date,phase,url):
    """Primary contests are grouped by party; county portions never mix with statewide totals."""
    if phase not in ('primary','general'):raise ValueError('Unknown election phase')
    groups={};seen=set()
    for row in csv.DictReader(io.StringIO(content.replace('\r\r\n','\n')),delimiter='\t'):
        if datetime.strptime(row['ElectionDate'],'%m/%d/%Y').date().isoformat()!=election_date:
            raise ValueError('Historical election date mismatch')
        party=row['PartyCode'].strip() or 'NON'
        key=(row['RaceCode'].strip(),row['Juris1num'].strip(),row['Juris2num'].strip(),row['RaceName'].strip(),party if phase=='primary' else '')
        parts=[row.get('CanNameFirst','').strip(),row.get('CanNameMiddle','').strip(),row['CanNameLast'].strip()]
        name=' / '.join(x for x in (parts[0],parts[2]) if x) if key[0]=='GOV' and phase=='general' else ' '.join(x for x in parts if x)
        duplicate=(key,name,party,row['CountyCode'])
        if duplicate in seen:raise ValueError('Duplicate historical county row')
        seen.add(duplicate)
        votes=int(row['CanVotes'])
        if votes<0:raise ValueError('Negative historical votes')
        for scope in (['florida','indian_river'] if row['CountyCode']=='IND' else ['florida']):
            group=groups.setdefault((scope,key),{'id':'history:'+stable_id(election_date,scope,*key),'date':election_date,'phase':phase,'party':key[-1],
                'office_code':key[0],'name':key[3],'district':key[1],'scope':scope,
                'geography':'Indian River County portion' if scope=='indian_river' else 'Florida · full contest',
                'source_name':'Florida Division of Elections','source_url':url,'candidates':{}})
            c=group['candidates'].setdefault((name,party),{'name':name,'party':party,'votes':0})
            c['votes']+=votes
    contests=[]
    for group in groups.values():
        group['candidates']=list(group['candidates'].values())
        if sum(c['votes'] for c in group['candidates']):contests.append(finish(group))
    if not contests:raise ValueError('Empty historical state file')
    return contests


def parse_county_history(content,election_date,phase,url):
    tree=Tree(content).root
    d=date.fromisoformat(election_date)
    if not re.search(r'Election Date:\s*'+f'{d.month}/{d.day}/{d.year}',tree.text()):raise ValueError('Historical county date mismatch')
    if phase not in ('primary','general','municipal') or not re.search(r'\b'+phase+r' Election',tree.text(),re.I):raise ValueError('Historical county election phase mismatch')
    contests=[]
    for node in tree.find('Race'):
        names=node.find('RaceName')
        if not names:continue
        labels=[x.text() for x in names[0].children if x.tag=='label']
        name=re.sub(r'Add or Take Out of Favorite Races','',labels[-1] if labels else names[0].text()).strip()
        candidates=[]
        for row in node.find('ResultsRow'):
            choices=row.find('ChoiceColumn');nums=row.find('ResultsColumn')
            if len(choices)!=1 or len(nums)!=2:continue
            raw=choices[0].text();match=re.search(r'\(([^()]+)\)\s*$',raw)
            candidates.append({'name':raw[:match.start()].strip() if match else raw,'party':match.group(1) if match else 'NON','votes':int(nums[-1].text().replace(',',''))})
        if candidates and sum(c['votes'] for c in candidates):
            contests.append(finish({'id':'history:'+stable_id(election_date,node.attrs.get('id'),name),'date':election_date,'phase':phase,'name':name,
                'scope':'indian_river','geography':'Indian River County · contest electorate','source_name':'Indian River County Supervisor of Elections','source_url':url,'candidates':candidates}))
    if not contests:raise ValueError('No historical county contests')
    return contests


@lru_cache(maxsize=1)
def load_history():
    path=config.ROOT/'data'/'history.json'
    if not path.exists():return {'candidates':[],'senate':[],'coverage_note':'No verified history installed.'}
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version')!=1 or data.get('kind')!='historical':raise ValueError('Invalid historical data bundle')
    for record in data['candidates']:
        if record['date']>=config.ELECTION_DATE:raise ValueError('Historical result is not earlier than current election')
        if not record['source_url'].startswith('https://'):raise ValueError('History needs a source')
        if type(record['votes']) is not int or record['votes']<0 or not 0<=record['percentage']<=100:raise ValueError('Invalid historical result')
    return data
