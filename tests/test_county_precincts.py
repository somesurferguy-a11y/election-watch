import unittest
from feeds import parse_irc
from roster import merge_race
HEAD='<h1>2026 General Election</h1><h2>Election Date: 11/3/2026</h2>'
def race(rid,reported,total):
 return f'<div class="Race" id="{rid}"><div class="RaceName"><label>Race {rid}</label></div><span class="numPrecinctsReported">{reported}</span><span class="numPrecinctsReported">{reported}</span><span class="numPrecinctsParticipating">{total}</span><span class="numPrecinctsParticipating">{total}</span><div class="ResultsRow"><span class="ChoiceColumn">A (NON)</span><span class="ResultsColumn">100%</span><span class="ResultsColumn">10</span></div></div>'
class CountyPrecinctTests(unittest.TestCase):
 def parse(self,html):return parse_irc(HEAD+html,'https://enr.electionsfl.org/IND/4096/Summary/')
 def test_contest_precincts_not_global_county_total(self):
  p=self.parse('<div class="PrecinctsValue">35 / 35</div>'+race('county',35,35)+race('city',3,3));self.assertEqual([(r['precincts_reporting'],r['precincts_total']) for r in p['races']],[(35,35),(3,3)])
 def test_zero_is_a_real_reporting_value(self):
  r=self.parse(race('r',0,5))['races'][0];self.assertEqual(r['precincts_reporting'],0);self.assertEqual(r['status'],'unofficial');self.assertFalse(r['is_complete'])
 def test_missing_precincts_remain_unknown(self):
  html=race('r',1,3)
  import re
  html=re.sub(r'<span class="numPrecincts(?:Reported|Participating)">.*?</span>','',html)
  r=self.parse(html)['races'][0];self.assertNotIn('precincts_total',r)
 def test_conflicting_or_invalid_reporting_keeps_votes_but_suppresses_stats(self):
  for html in [race('r',4,3),race('r','?',3),race('r',1,3).replace('>1</span>','>2</span>',1)]:
   r=self.parse(html)['races'][0];self.assertNotIn('precincts_total',r);self.assertIn('precinct_reporting_warning',r);self.assertEqual(r['candidates'][0]['votes'],10)
 def test_all_precincts_can_still_have_partial_ballot_types(self):
  stats='<div class="row"><div class="PrecinctsLabel">Election Day:</div><div class="PrecinctsValue">Partially Reported</div></div><div class="row"><div class="PrecinctsLabel">Early Votes:</div><div class="PrecinctsValue">Completely Reported</div></div>'
  r=self.parse(stats+race('r',3,3))['races'][0];self.assertEqual(r['county_vote_status']['election_day'],'Partially Reported');self.assertFalse(r['is_complete']);self.assertEqual(r['status'],'unofficial')
  merged=merge_race({'id':r['id'],'name':r['name'],'candidates':[{'id':r['candidates'][0]['id'],'name':'A','votes':0}]},r);self.assertEqual(merged['precincts_total'],3);self.assertEqual(merged['county_vote_status']['early_voting'],'Completely Reported')
