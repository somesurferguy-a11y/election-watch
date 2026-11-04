import unittest
from unittest.mock import patch
import florida_counties as fc


BASE = {'id': 'fl:gov', 'name': 'Governor', 'scope': 'florida', 'jurisdiction': 'Florida',
        'candidates': [{'id': 'a', 'name': 'Alice', 'party': 'REP', 'votes': 0},
                       {'id': 'b', 'name': 'Bob', 'party': 'DEM', 'votes': 0}]}
DIRECTORY = "<a href='https://enr.electionsfl.org/ALA/1/Summary/'>Alachua</a><a href='http://enr.electionsfl.org/BAK/Summary/2'>Baker</a>"


def report(votes=5):
    return {'source_updated_at': None, 'races': [{'name': 'Governor', 'candidates': [
        {'name': 'Alice', 'votes': votes}, {'name': 'Write-in', 'votes': 2}]}]}


class CountyTests(unittest.TestCase):
    def run_feed(self, reports=None, previous=None):
        reports = reports or [report(), report(7)]
        with patch.object(fc, 'fetch_url', side_effect=[(DIRECTORY, None), ('first', None), ('second', None)]), patch.object(fc, 'parse_irc', side_effect=reports):
            return fc.florida_county_feed(previous, {'races': [BASE]})

    def test_links_filter_and_deduplicate(self):
        links = fc.county_report_links(DIRECTORY + DIRECTORY + "<a href='https://evil.test/IND/123/Summary/'>bad</a><a href='https://enr.electionsfl.org/ind/123/Summary/'>bad</a>")
        self.assertEqual(len(links), 2)
        self.assertTrue(all(x['report_url'].startswith('https://enr.electionsfl.org/') for x in links))

    def test_sums_and_aggregate_writein_missing_candidate(self):
        race = self.run_feed()['races'][0]
        self.assertEqual([c['votes'] for c in race['candidates']], [12, 0, 4])
        self.assertFalse(race['candidates'][1]['votes_available'])
        self.assertEqual(race['status'], 'unofficial')
        self.assertIsNone(race['precincts_total'])
        self.assertTrue(race['partial_coverage'])
        self.assertEqual(len(race['counties_included']), 2)

    def test_duplicate_race_rejected(self):
        duplicate = report(); duplicate['races'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate county contest'):
            self.run_feed([duplicate, report()])

    def test_lost_coverage_retains_previous(self):
        old = self.run_feed()
        with self.assertRaisesRegex(ValueError, 'coverage lost'):
            self.run_feed([report(), ValueError('offline')], old)

    def test_unreviewed_candidate_omits_only_affected_county_contest(self):
        unknown = report(); unknown['races'][0]['candidates'].append({'name': 'Unreviewed', 'votes': 2})
        payload = self.run_feed([unknown, report()])
        self.assertEqual(len(payload['races'][0]['counties_included']), 1)
        self.assertIn('Unreviewed candidate', payload['county_errors'][0]['error'])

    def test_duplicate_candidate_rejected(self):
        duplicate = report(); duplicate['races'][0]['candidates'].append({'name': 'Alice', 'votes': 2})
        with self.assertRaisesRegex(ValueError, 'Duplicate county candidate'):
            self.run_feed([duplicate, report()])

    def test_oldest_known_report_time(self):
        a = report(); a['source_updated_at'] = '2026-11-03T23:00:00Z'
        b = report(); b['source_updated_at'] = '2026-11-04T00:00:00Z'
        payload = self.run_feed([a, b])
        self.assertEqual(payload['source_updated_at'], a['source_updated_at'])

    def test_replay_is_rejected_by_parser(self):
        with self.assertRaisesRegex(ValueError, 'November 3'):
            fc.parse_irc('<p>Election Date: 8/18/2026 Primary Election</p>', 'https://enr.electionsfl.org/ALA/1/Summary/')


if __name__ == '__main__': unittest.main()
