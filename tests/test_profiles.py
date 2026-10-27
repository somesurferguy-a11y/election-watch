import unittest
from pathlib import Path
from roster import load_roster
from candidate_profiles import profiles,enrich_candidates
import config

class CandidateProfileTests(unittest.TestCase):
 def setUp(self):self.roster=load_roster();self.races=enrich_candidates(self.roster['races'])
 def test_vero_stays_one_contest_with_eight_candidates_and_three_seats(self):
  races=[r for r in self.races if r['id']=='irc:ballot:vero-council'];self.assertEqual(len(races),1);self.assertEqual(races[0]['seats_to_elect'],3);self.assertEqual(len(races[0]['candidates']),8);self.assertTrue(all(c.get('photo') for c in races[0]['candidates']))
 def test_vero_incumbents_and_completed_terms(self):
  race=next(r for r in self.races if r['id']=='irc:ballot:vero-council');inc={c['name']:c['service'] for c in race['candidates'] if c['service']['incumbent']}
  self.assertEqual(set(inc),{'Linda Moore','Aaron Vos'});self.assertEqual(inc['Linda Moore']['terms_completed'],1);self.assertEqual(inc['Linda Moore']['terms_started'],2);self.assertEqual(inc['Aaron Vos']['terms_completed'],0)
 def test_current_terms_are_not_claimed_completed(self):
  for record in profiles()['records'].values():
   service=record.get('service')
   if service and service.get('incumbent') and service.get('terms_started') is not None:self.assertLess(service['terms_completed'],service['terms_started'])
 def test_metadata_does_not_change_votes_or_candidate_ids(self):
  for original,new in zip(self.roster['races'],self.races):self.assertEqual([(c['id'],c['votes']) for c in original['candidates']],[(c['id'],c['votes']) for c in new['candidates']])
  self.assertTrue(all('service' not in c for r in self.roster['races'] for c in r['candidates']))
 def test_portraits_are_existing_local_images_with_source_records(self):
  count=0
  for record in profiles()['records'].values():
   photo=record.get('photo')
   if photo:
    count+=1;self.assertTrue(photo['path'].startswith('/static/portraits/'));self.assertTrue((config.ROOT/photo['path'].lstrip('/')).is_file());self.assertTrue(photo['source_url'].startswith('https://'));self.assertTrue(photo['subject'])
  self.assertGreater(count,50)
 def test_unknown_terms_remain_unknown_not_zero(self):
  race=next(r for r in self.races if r['id']=='irc:ballot:mosquito-2');anna=next(c for c in race['candidates'] if c['name']=='Anna J. Kirkland');self.assertTrue(anna['service']['incumbent']);self.assertIsNone(anna['service']['terms_completed'])
 def test_vero_former_members_and_newcomers_have_distinct_verified_counts(self):
  race=next(r for r in self.races if r['id']=='irc:ballot:vero-council');counts={c['name']:c['service']['terms_completed'] for c in race['candidates']}
  self.assertEqual(counts,{'Aaron Vos':0,'Linda Moore':1,'Jay Kramer':3,'Brian Heady':1,'Tracey Lockwood Zudans':1,'Robert MacCallum':0,"John O'Connor":0,'Davis Benedict':0})
 def test_appointed_moody_is_not_labeled_as_having_completed_a_senate_term(self):
  race=next(r for r in self.races if r['scope']=='florida' and r['office_code']=='USS');c=next(c for c in race['candidates'] if c['name']=='Ashley Moody');self.assertTrue(c['service']['incumbent']);self.assertEqual(c['service']['terms_completed'],0);self.assertIn('Appointed',c['service']['term_note'])
 def test_governor_ticket_does_not_inherit_house_incumbency(self):
  race=next(r for r in self.races if r['scope']=='florida' and r['office_code']=='GOV');c=next(c for c in race['candidates'] if c['name'].startswith('Byron Donalds'));self.assertFalse(c['service']['incumbent'])
