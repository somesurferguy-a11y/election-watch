import copy,unittest
from datetime import datetime
from watch_features import competitive_races,night_guide
from store import Engine
import tempfile

def race(**updates):
 r={'id':'test','name':'Test race','scope':'national','status':'unofficial','source_name':'Test source','candidates':[{'id':'a','name':'A','votes':51},{'id':'b','name':'B','votes':49}]};r.update(updates);return r

class NightTests(unittest.TestCase):
 def test_close_race_uses_votes_not_poll_probability(self):
  result=competitive_races([race()]);self.assertEqual(result[0]['margin_pp'],2);self.assertEqual(result[0]['margin_votes'],2)
 def test_low_vote_count_is_excluded(self):self.assertEqual(competitive_races([race(candidates=[{'votes':5},{'votes':4}])]),[])
 def test_multi_seat_and_called_and_incomplete_are_excluded(self):
  for change in [{'seats_to_elect':3},{'status':'certified'},{'result_incomplete':True},{'office_code':'AMD'}]:self.assertEqual(competitive_races([race(**change)]),[])
 def test_exact_five_point_boundary(self):
  self.assertEqual(len(competitive_races([race(candidates=[{'votes':105},{'votes':95}])])),1)
  self.assertEqual(competitive_races([race(candidates=[{'votes':106},{'votes':94}])]),[])
 def test_tie_is_close_not_a_winner(self):self.assertEqual(competitive_races([race(candidates=[{'votes':50},{'votes':50}])])[0]['margin_votes'],0)
 def test_missing_candidate_count_excluded(self):self.assertEqual(competitive_races([race(candidates=[{'votes':51,'votes_available':False},{'votes':49}])]),[])
 def test_closings_cover_fifty_states_and_dc(self):
  states={a.split(' (')[0] for group in night_guide()['closings'] for a in group['areas']}
  self.assertEqual(len(states),51);self.assertIn('District of Columbia',states)
 def test_florida_and_midnight_offsets(self):
  groups=night_guide()['closings'];e=next(g for g in groups if 'Florida (Eastern)' in g['areas']);c=next(g for g in groups if 'Florida (Central)' in g['areas'])
  self.assertEqual((datetime.fromisoformat(c['closes_at'])-datetime.fromisoformat(e['closes_at'])).total_seconds(),3600)
  self.assertTrue(groups[-1]['closes_at'].startswith('2026-11-04T01:00:00-05:00'))
 def test_all_amendments_have_yes_no_and_threshold(self):
  amendments=night_guide()['amendments'];self.assertEqual([a['number'] for a in amendments],[1,2,3]);self.assertTrue(all(a['yes'] and a['no'] and a['threshold']==60 for a in amendments))
 def test_first_totals_and_numeric_delta_are_recorded(self):
  with tempfile.TemporaryDirectory() as d:
   engine=Engine(d)
   try:
    engine.make_events('national',{}, {'races':[race()]});self.assertIn('first reported',engine.events[-1]['text']);self.assertIsNone(engine.events[-1]['vote_delta'])
    old=race();new=race(candidates=[{'id':'a','name':'A','votes':52},{'id':'b','name':'B','votes':50}]);engine.make_events('national',{'races':[old]},{'races':[new]});self.assertEqual(engine.events[-1]['vote_delta'],2)
   finally:engine.close();engine.db.conn.close()
 def test_local_rotation_preference_is_validated(self):
  with tempfile.TemporaryDirectory() as d:
   engine=Engine(d)
   try:
    self.assertTrue(engine.settings['local_spotlight']);self.assertFalse(engine.update_settings({'local_spotlight':False})['local_spotlight'])
    with self.assertRaises(ValueError):engine.update_settings({'local_spotlight':'yes'})
   finally:engine.close();engine.db.conn.close()
