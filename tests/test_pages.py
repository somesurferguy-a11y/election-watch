import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PagesTests(unittest.TestCase):
 def test_public_build_keeps_real_roster_and_relative_assets(self):
  folder=ROOT/'public'
  if not folder.exists():self.skipTest('Run export_pages.py first')
  data=json.loads((folder/'state.json').read_text(encoding='utf-8'))
  self.assertFalse(data['demo']);self.assertGreater(len(data['races']),100)
  html=(folder/'index.html').read_text(encoding='utf-8')
  self.assertNotIn('/host',html);self.assertNotIn('src="/static',html)
  app=(folder/'static/js/app.js').read_text(encoding='utf-8')
  self.assertNotIn("fetch('/api/",app);self.assertIn("fetch('./state.json?t='",app)
  for race in data['races']:
   for candidate in race['candidates']:
    if candidate.get('photo'):self.assertTrue((folder/candidate['photo']['path'].lstrip('/')).is_file())
 def test_workflow_retains_source_cache_and_has_election_cutoff(self):
  text=(ROOT/'.github/workflows/pages.yml').read_text()
  self.assertIn('actions/cache@v4',text);self.assertIn('20261110',text)
