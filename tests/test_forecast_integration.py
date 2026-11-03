import tempfile,unittest
from store import Engine
from feeds import market_record
class ForecastIntegrationTests(unittest.TestCase):
 def test_real_observation_is_not_refreshed_by_state_reads(self):
  with tempfile.TemporaryDirectory() as path:
   engine=Engine(path)
   try:
    m=market_record('Kalshi','x','House','Yes — Democratic control',.6,.8,.7,None,1000,None,'https://example.org/market','Exact contract rules','open','control-house')
    engine.accept('kalshi',{'markets':[m]})
    before=engine.db.get('market_forecasts')['latest']
    engine.state();engine.state()
    self.assertEqual(engine.db.get('market_forecasts')['latest'],before)
   finally:engine.close();engine.db.conn.close()
 def test_bad_archive_does_not_remove_live_dashboard(self):
  with tempfile.TemporaryDirectory() as path:
   engine=Engine(path)
   try:
    engine.db.put('market_forecasts',{'version':999})
    state=engine.state();self.assertTrue(state['races']);self.assertIn('registry_error',state['market_track_record']);self.assertEqual(engine.db.get('market_forecasts'),{'version':999})
   finally:engine.close();engine.db.conn.close()
