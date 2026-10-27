"""Local configuration. No credentials or invented source-verification claims."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('ELECTION_DATA_DIR', str(ROOT / 'data'))).resolve()
ELECTION_DATE = '2026-11-03'
HOST = os.environ.get('ELECTION_HOST', '127.0.0.1')
PORT = int(os.environ.get('ELECTION_PORT', '5000'))
DEFAULT_MODE = 'demo' if os.environ.get('ELECTION_DEMO_MODE', 'false').lower() == 'true' else 'live'
HOST_PASSWORD = os.environ.get('ELECTION_HOST_PASSWORD', '')
FL_FILE_URL = 'https://flelectionfiles.floridados.gov/enightfilespublic/20261103_ElecResultsFL.txt'
IRC_ARCHIVE_URL = 'https://www.voterfocus.com/enr_php/enrarchive.php?county=indianriver'
IRC_GENERAL_ID = os.environ.get('FL_ENR_GENERAL_IRC_ID', '')
# Optional authorized provider: documented normalized schema in README.md.
NATIONAL_JSON_URL = os.environ.get('ELECTION_NATIONAL_JSON_URL', '')
POLLS_JSON_URL = os.environ.get('ELECTION_POLLS_JSON_URL', '')
HTTP_TIMEOUT = 12
MAX_RESPONSE_BYTES = 12_000_000
SOURCES = {
 'power': {'name':'Current Congress party balance','url':'https://radiotv.house.gov/house-data/party-breakdown','interval':21600,'kind':'context','note':'Official House membership and Senate party division. Checks every six hours; source publication dates remain distinct from retrieval times.'},
 'florida': {'name':'Florida Division of Elections', 'url':FL_FILE_URL, 'interval':45, 'kind':'results', 'note':'Official statewide tab-delimited file. November file may not be published yet; never substitutes the primary.'},
 'indian_river': {'name':'Indian River County elections', 'url':'https://www.voteindianriver.gov/election_information/election_results_archive.php', 'interval':60, 'kind':'results', 'note':'Discovers the exact November 3 general-election ENR ID from the county-linked archive. Optional FL_ENR_GENERAL_IRC_ID override is date-validated.'},
 'national': {'name':'Open America multi-state results', 'url':'https://openamerica.io/elections/api/', 'interval':600, 'kind':'results', 'note':'Free counts from official state feeds: provider documents 22 states, not full national coverage. No calls. Polls every 10 minutes before counting, every minute while counting; uses ETag and gzip.'},
 'polls': {'name':'Stetson polling baseline', 'url':'https://www.stetson.edu/artsci/cpor/', 'interval':7200, 'kind':'polls', 'note':'Reviewed October 1–9 governor/Senate poll, published October 13. Every two hours checks the release hash; changed releases require review. Not an aggregate or an assertion this is the latest poll.'},
 'polymarket': {'name':'Polymarket', 'url':'https://polymarket.com/', 'interval':60, 'kind':'markets', 'note':'Public Gamma API, exact House/Senate 2026 party-control contracts. Midpoint of valid bid/ask; metadata time is not quote time.'},
 'kalshi': {'name':'Kalshi', 'url':'https://kalshi.com/', 'interval':60, 'kind':'markets', 'note':'Public market data API; exact CONTROLS-2026 and CONTROLH-2026 tickers. No trading or account access.'},
}
