"""Conservative, explicitly partial sums of directory-linked official county ENR."""
import copy
import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urlsplit

import config
from feeds import fetch_url, parse_irc, NotPublished
from roster import load_roster, names_for, normalized
from validation import validate_results

DIRECTORY_URL = 'https://floridaelectionwatch.gov/CountyReportingStatus'
SOURCE_NAME = 'Official Florida county reports (partial)'


def county_report_links(content):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.current = None; self.rows = []
        def handle_starttag(self, tag, attrs):
            if tag != 'a': return
            value = dict(attrs).get('href', '')
            try:
                u = urlsplit(value)
                if u.scheme not in ('http', 'https') or u.hostname != 'enr.electionsfl.org' or u.username or u.password or u.port not in (None, 80, 443) or u.query or u.fragment: return
                m = re.fullmatch(r'/([A-Z]{3})/(?:(\d+)/Summary|Summary/(\d+))(?:/Scrolling/Banner)?/?', u.path)
                if m: self.current = {'code': m[1], 'name': '', 'report_url': f'https://enr.electionsfl.org/{m[1]}/{m[2] or m[3]}/Summary/'}
            except ValueError: pass
        def handle_data(self, data):
            if self.current is not None: self.current['name'] += data
        def handle_endtag(self, tag):
            if tag == 'a' and self.current is not None:
                self.current['name'] = ' '.join(self.current['name'].split()) or self.current['code']
                self.rows.append(self.current); self.current = None
    parser = Links(); parser.feed(content)
    by_code = {}
    for row in parser.rows:
        previous = by_code.get(row['code'])
        if previous and previous['report_url'] != row['report_url']:
            raise ValueError('Conflicting directory election IDs for county')
        by_code[row['code']] = row
    return list(by_code.values())


def florida_county_feed(previous=None, roster=None):
    """Never combine state totals; a lost previously included county rejects the cycle."""
    directory, _ = fetch_url(DIRECTORY_URL)
    links = county_report_links(directory)
    bases = [r for r in (roster or load_roster())['races'] if r['scope'] == 'florida']
    def read(row):
        try:
            html, stamp = fetch_url(row['report_url'])
            parsed = parse_irc(html, row['report_url'], stamp)
            return row, parsed, None
        except Exception as exc: return row, None, str(exc)
    with ThreadPoolExecutor(max_workers=10) as pool:
        reports = list(pool.map(read, links))
    groups = {}; errors = []
    for county, payload, error in reports:
        if error: errors.append({'code': county['code'], 'error': error}); continue
        seen = set()
        for result in payload['races']:
            matches = [b for b in bases if normalized(result['name']) in names_for(b)]
            if len(matches) != 1: continue
            base = matches[0]; rid = base['id']
            if rid in seen: raise ValueError('Duplicate county contest; refusing double count')
            seen.add(rid)
            if not any(c['votes'] for c in result['candidates']): continue
            mapped = {}; writein = 0; has_writein = False; unmatched = False
            for candidate in result['candidates']:
                if normalized(candidate['name']) in ('writein', 'writeins'):
                    writein += candidate['votes']; has_writein = True; continue
                choices = [c for c in base['candidates'] if normalized(candidate['name']) in names_for(c)]
                if len(choices) != 1:
                    errors.append({'code': county['code'], 'race_id': rid, 'error': 'Unreviewed candidate; county contest omitted: ' + candidate['name']})
                    unmatched = True
                    break
                cid = choices[0]['id']
                if cid in mapped: raise ValueError('Duplicate county candidate')
                mapped[cid] = candidate['votes']
            if unmatched: continue
            g = groups.setdefault(rid, {'base': base, 'counts': {}, 'presence': {}, 'counties': []})
            for cid, votes in mapped.items():
                g['counts'][cid] = g['counts'].get(cid, 0) + votes
                g['presence'][cid] = g['presence'].get(cid, 0) + 1
            if has_writein:
                cid = rid + ':aggregate-write-in'
                g['counts'][cid] = g['counts'].get(cid, 0) + writein
                g['presence'][cid] = g['presence'].get(cid, 0) + 1
            g['counties'].append(dict(county, published_at=payload.get('source_updated_at')))
    races = []
    for rid, g in groups.items():
        race = copy.deepcopy(g['base']); counties = sorted(g['counties'], key=lambda c: c['code'])
        candidates = copy.deepcopy(race['candidates'])
        if rid + ':aggregate-write-in' in g['counts']:
            candidates.append({'id': rid + ':aggregate-write-in', 'name': 'Write-in totals', 'party': 'WRI'})
        for c in candidates:
            c.update(votes=g['counts'].get(c['id'], 0), votes_available=g['presence'].get(c['id'], 0) == len(counties))
        stamps = [c['published_at'] for c in counties if c['published_at']]
        race.update(candidates=candidates, status='unofficial', is_complete=False,
                    source_name=SOURCE_NAME, source_url=DIRECTORY_URL,
                    source_updated_at=min(stamps) if stamps else None,
                    timestamp_scope='Oldest known included county report HTTP Last-Modified; unknown times listed individually.',
                    partial_coverage=True, counties_included=counties,
                    precincts_total=None, precincts_reporting=None, precinct_percent=None,
                    coverage_note=f'PARTIAL: {len(counties)} county reports included. Eligible county denominator for this contest is unknown; other counties are missing. Not a complete statewide total. {len(counties)-len(stamps)} included report timestamps unknown.')
        for key in ('winner_id', 'call_source', 'call_at'): race.pop(key, None)
        races.append(race)
    if previous:
        current = {r['id']: {c['code'] for c in r['counties_included']} for r in races}
        for r in previous.get('races', []):
            old = {c['code'] for c in r.get('counties_included', [])}
            if not old.issubset(current.get(r['id'], set())):
                raise ValueError('Previously included county coverage lost; retain previous complete aggregate')
    if not races: raise NotPublished('No nonzero reviewed county contest totals available')
    stamps = [r['source_updated_at'] for r in races if r['source_updated_at']]
    out = validate_results({'election_date': config.ELECTION_DATE, 'demo': False, 'races': races,
                            'source_updated_at': min(stamps) if stamps else None,
                            'partial_coverage': True, 'county_errors': errors})
    for r in out['races']:
        if any(not c['votes_available'] for c in r['candidates']):
            for c in r['candidates']: c['percentage'] = None
            r['result_incomplete'] = True
    return out
