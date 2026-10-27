import unittest
from feeds import parse_power

HOUSE='<p>218 Republicans 214 Democrats 1 Independent 2 Vacancies</p><p>Last updated 9/2/26</p>'
SENATE='<p>Majority Party: Republicans (53 seats)</p><p>Minority Party: Democrats (45 seats)</p><p>Other Parties: Independents (2 seats)</p>'

class PowerTests(unittest.TestCase):
 def test_current_membership_is_not_an_election_result(self):
  result=parse_power(HOUSE,SENATE)
  self.assertNotIn('races',result)
  self.assertEqual(result['chambers'][0]['REP'],53)
  self.assertEqual(result['chambers'][1]['vacancies'],2)
  self.assertEqual(result['chambers'][1]['published_date'],'2026-09-02')
 def test_inconsistent_total_is_rejected(self):
  with self.assertRaises(ValueError):parse_power(HOUSE.replace('218','219'),SENATE)
 def test_layout_change_is_rejected(self):
  with self.assertRaises(ValueError):parse_power('<p>Unavailable</p>',SENATE)
 def test_unknown_publisher_date_is_not_retrieval_date(self):
  result=parse_power(HOUSE.split('<p>Last updated')[0],SENATE)
  self.assertIsNone(result['chambers'][1]['published_date'])
  self.assertIsNotNone(result['checked_at'])
