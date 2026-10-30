# Election Watch

A local television dashboard for the November 3, 2026 election. Six views, saved watchlist, background source checks, a persistent rotating headline ticker, host controls, source-health diagnostics, and unmistakably labeled fictional demo mode.

## Verified ballot roster — corrected October 26

The app now ships a persistent **ballot roster independent of vote-return availability**: 177 Florida contests from the state file, **26 Indian River November contests**, and a separate list of **8 earlier-decided or unopposed county offices**. The roster is visible even on a fresh install with no network connection. Pending totals display dashes and “Awaiting,” not 0% results.

The local November list includes commission districts 2 and 4; Mosquito Control seat 2; Vero Beach, Sebastian and Fellsmere city councils; Sebastian referendum questions 1–3; and the 17 federal/state/judicial/amendment/special-district county portions already provided by Florida. Local contests appear first. Click **Earlier decisions (8)** to see school-board and other offices recorded as elected/unopposed; these are not falsely presented as unresolved November races.

Full governor/lieutenant-governor ticket names are populated from the state's qualified-candidate listing. Withdrawn/defeated candidates are excluded from the local November fields. The Vero Beach field has eight candidates for three seats, Sebastian five for two, and Fellsmere four for three. Multi-seat cards show seat counts and rotate through all candidates; details list the complete field. A lead does not declare any of those seats won.

`data/ballot_roster.json` preserves each roster source, verification time, stable identity and reviewed result-name aliases. Governor poll IDs remain unchanged. Result counts attach to canonical races using IDs or reviewed exact aliases, never fuzzy guessing, and providers are never added together. A partial county feed cannot erase known races. Missing candidate counts remain unknown. Sebastian's three referendum numbers are verified; full ballot wording is deliberately not paraphrased or invented.

Roster evidence: the county's October 13 ballot release and candidate filings; Vero Beach's official eight-candidate list; Sebastian's official handbook and candidate-forum reporting; and TCPalm's Fellsmere candidate questionnaires. The transcript spelling “Zammaripa” was rejected after checking **Jose M. Zamarripa** against the questionnaires and election listing. See the per-race evidence links and SOURCE-INVENTORY.md.

## Start

Double-click **Start-ElectionWatch.cmd**, then open **http://127.0.0.1:5000/**. Host controls are at **http://127.0.0.1:5000/host**. Use fullscreen and connect or mirror this computer to the television. Leave the server window running. Stop it with Ctrl+C.

If the dashboard is already running, use the existing link instead of launching a second server. The completed installation was left running in the background; a Windows restart stops it. After restarting Windows, the launcher starts it again. Use the television browser's own fullscreen command if fullscreen is restricted inside an embedded browser.

Python 3.10+ is the only runtime requirement. There is no pip install, Node build, account, subscription, or paid dependency. The launcher first uses an explicitly configured `ELECTION_PYTHON`, then this computer's bundled Codex Python, then `py -3`.

Manual launch: `python server.py`. Optional arguments: `--port 5050`, `--host 127.0.0.1`, `--no-feeds` (offline testing only). The ordinary application starts with background refresh enabled. Live mode is the default on a fresh installation; the host's saved choice is remembered.

## TV and host controls

- Six views: National, Florida, Indian River, Watchlist, Polls & markets, Source health.
- Arrow keys change views; Page Up/Down change pages; Space pauses rotation; F toggles fullscreen.
- Dense views paginate. Pages advance every 12 seconds during rotation, and retain their place across view cycles.
- Pin races from the TV or searchable full roster in the host panel. Pins survive restarts.
- Set live/demo mode, initial view, rotation interval, text size, ticker visibility, ticker pause and headline interval in the host panel. Changes reach connected TVs within five seconds.
- The ticker uses stationary headline cards, deduplicated change events, local/pinned priority, and 30-minute expiration. Its no-news message is explicitly a standing summary. Demo headlines always identify fictional data.
- Details show all candidates, vote counts, source links and attributed calls where supplied. No lead or percentage automatically produces a call.
- Export the displayed snapshot from host controls for review. Demo exports are named DEMO.

## Current free sources and actual coverage

See SOURCE-INVENTORY.md for exact endpoints and evidence.

1. **Florida:** the official November 3 tab-delimited file is published and was fetched successfully. It currently has zero votes. The verified parser produces 177 distinct statewide/district/multi-county contests plus 17 Indian River County portions (194 records total). These are current published roster records, not a claim to every county/municipal contest. The file updates automatically every 45 seconds. Candidate tickets use the source's paired surnames.
2. **Indian River:** all 26 reviewed November contests and their known candidates are populated from the persistent ballot roster. The county-linked results archive currently exposes the August primary, not the November general election. The dashboard checks that archive automatically and accepts only a November 3 general-election ID. Until then, state-file county portions can receive totals; municipal/local vote-return coverage remains pending. `FL_ENR_GENERAL_IRC_ID` can select an ID once independently verified; the page's date and title are still checked. The results-feed gap does not hide known races or candidates.
3. **Other states:** Open America's documented free API passes through official state counts and documents coverage of 22 states. It is explicitly a partial multi-state source, not a complete national service. The 2026 House and Senate responses currently return empty races before counting. Florida is excluded from this adapter because Florida's own file is already connected. No races are called by this provider. The application polls every 10 minutes before counting and every minute during counting, with ETag/304 and gzip. Missing races/seats remain unprovided. The 2024 replay cannot enter live mode.
4. **Polls:** two reviewed Stetson CPOR snapshots cover governor and Senate, fielded October 1–9, published October 13. They are dated baselines, not a claim to the newest poll or an aggregate. The publication reports 826 adults interviewed, electoral estimates from 716 registered voters modeled for turnout, and an opt-in online panel weighted and calibrated to 2024 presidential results. Each baseline includes leaners and links to the source release. The release's SHA-256 is checked every two hours. A changed release produces a review-needed error while retaining the reviewed baseline; numbers are never guessed from changed documents. New sourced polls can be imported. A first-seen pre-election baseline is frozen per poll ID.
5. **Markets:** public Polymarket and Kalshi APIs currently supply eight 2026 House/Senate party-control contracts, refreshed every minute. The screen shows the exact Yes outcome and party, bid/ask midpoint, spread in percentage points, metadata timestamp, volume, settlement text, source link and first-observed pre-election baseline. Provider metadata timestamps are never labeled quote timestamps. Quote time is explicitly unavailable. Cross-provider contracts are not averaged or treated as necessarily equivalent.

**Remaining coverage limits:** no guaranteed all-50-state results, no automatic national winner-call service, no fully verified November Indian River municipal feed yet, and no local polls where none have been verified. The software exposes these limits instead of inventing data. No paid API is required or activated.

## Freshness and failure behavior

Every source tracks attempt, successful retrieval, source-publication time and observed data change separately. Unchanged responses and HTTP 304 do not advance source-publication or observed-change times. Results without source timestamps say unavailable. Before election day an old roster file is normal; during counting, an old results-publication timestamp is flagged separately from a failed retrieval.

Each source refreshes independently, with a timeout, bounded response, exponential backoff and numeric Retry-After handling. A slow or failed source cannot block the others. Last valid snapshots persist across restarts. Outages stay visible in the footer and ticker. The browser checks the server every five seconds and recovers after network loss, sleep or tab resume.

All times shown on screen use America/New_York. Stored times use UTC with explicit timezone offsets. A source's Last-Modified is a file-publication time, not proof that votes changed. Open America's newest timestamp covers its payload, not each individual race. Counts marked as tests, wrong-election files and nonzero pre-election totals are rejected.

The SQLite database stores current source snapshots, preferences, ticker events, first-observed baselines and up to 120 changed snapshots per source. This is bounded recovery history, not an exhaustive vote-by-vote archive. Back it up with the server stopped if moving computers.

## Optional sourced imports and provider feeds

Host imports are allowed for `national`, `indian_river`, or `polls`; import data replaces that source snapshot and is labeled **Host-imported snapshot**, never connected live. Imports must use `demo: false` and the exact election date. Never import fictional samples as live data. Nonzero vote counts are rejected before election day.

An authorized normalized JSON endpoint can optionally be supplied through `ELECTION_NATIONAL_JSON_URL` or `ELECTION_POLLS_JSON_URL`. URLs are server-side configuration, not browser-submitted fetch targets. No provider has been purchased or subscribed to.

Results schema (replace every example field with sourced data; this zero-vote shape is illustrative):

```json
{
  "election_date": "2026-11-03",
  "demo": false,
  "source_updated_at": null,
  "races": [{
    "id": "provider:stable-race-id",
    "seat_id": "AZ-01",
    "name": "Official contest name",
    "jurisdiction": "Arizona",
    "scope": "national",
    "chamber": "house",
    "status": "awaiting",
    "source_name": "Name of actual reporting source",
    "source_url": "https://example.org/official-results",
    "source_updated_at": null,
    "is_complete": false,
    "candidates": [{"id": "stable-candidate-id", "name": "Candidate name", "party": "DEM", "votes": 0}]
  }]
}
```

Scopes: `national`, `indian_river`, `florida` (the last is reserved for the direct Florida adapter). Status: `awaiting`, `unofficial`, `projected`, `certified`, `recount`, `runoff`. A `projected` or `certified` record requires `winner_id`, `call_source`, and `call_at` with timezone. Vote shares are derived from the complete candidate counts. Optional `precincts_reporting`/`precincts_total` are precinct counts, never estimated votes counted. Optional `precinct_percent` is explicitly precinct percentage. Measures can supply `passage_threshold` and a supporting `threshold_source` link. A completed-count comparison requires both `is_complete: true` and certified status.

Chamber summaries count only attributed projected/certified records supplied by the provider, using stable `seat_id` values to deduplicate. To show the full Senate composition a provider must explicitly supply seats not up for election as well. Missing seats and vacancies are unprovided, never assumed Democratic or Republican. Independent winners can carry `caucus: "DEM"` or `"REP"` when sourced. An outright Senate majority requires 51; a 50–50 chamber additionally depends on the vice president. The free default results source supplies no calls, so it cannot establish chamber control.

Poll schema:

```json
{
  "election_date": "2026-11-03", "demo": false,
  "polls": [{
    "id": "publisher-stable-poll-id", "race_id": "exact-race-id-from-host-roster",
    "pollster": "Actual pollster", "sponsor": "Actual sponsor or explicitly not reported",
    "field_start": "2026-10-01", "field_end": "2026-10-09",
    "sample_size": 716, "population": "Describe the actual sample",
    "method": "Describe collection and weighting",
    "source_url": "https://example.org/published-poll",
    "retrieved_at": "2026-10-26T20:00:00Z",
    "shares": [{"candidate_id": "exact-candidate-id-from-host-roster", "share": 49}]
  }]
}
```

Stable race and candidate IDs are visible in the host roster. Unknown IDs are not guessed. Polls remain separate; no unsupported average is calculated. Margin-shift controls are illustrations, and partial-return differences are explicitly provisional. Pre-election market snapshots measure price-based win probability, never vote share.

## Local access

Default binding is loopback, suitable for a computer attached to a TV. No firewall or network permissions are changed. If you deliberately enable LAN access, set `ELECTION_HOST_PASSWORD` and use `--host 0.0.0.0`; the server refuses that binding without a password. The host username can be any nonempty name and the password is the configured value. Only the TV read view is unauthenticated. Host changes require authentication, a same-origin request and a random CSRF token. The built-in server is intended for a trusted local watch party, not public Internet hosting.

## Verification and project structure

- `python -m unittest discover -s tests -v`: parser, freshness, error retention, correction, call, import and HTTP-control regression tests.
- `python live_check.py`: explicit read-only check of actual configured feeds; saves valid snapshots to local app data.
- `python make_demo.py`: regenerate entirely fictional demonstration fixtures.
- `templates/`: actual server pages. `static/css/tv.css`, `static/js/app.js`, `static/js/host.js`: TV and host UI.
- `feeds.py`: provider adapters and strict election-date checks. `store.py`: scheduler, health and snapshots. `validation.py`: import/feed schema validation.
- `AUDIT_REPORT.md`: current validation, known limitations and handoff. Older files are preserved in the install backup.

On election night, verify mode, source dates, coverage, ticker and fullscreen before guests arrive. A functioning automatic refresh proves a retrieval, not that an upstream provider has published new totals.


## Election history addition — October 26, 2026

The TV History view and race Details > Past election results now show reviewed historical results independently of live votes. The bundle contains 240 candidate-result records matched to 205 current race/candidate identities. Each result retains election date, phase, electorate/geography, original candidate name, party, votes, calculated share, vote rank, full opponent field, and official source link. Same-name reviewed aliases are explicit; generic write-in/Yes/No labels never identify a candidate. History is hidden in fictional demo mode.

Coverage: statewide Florida August 18, 2026 primary and November 5, 2024 general election; Indian River 2026 primary, 2022/2024 general, 2023/2025 municipal elections. County ENR archives use IDs 4032, 3309, 3739, 3451 and 3881 at https://enr.electionsfl.org/IND/{ID}/Summary/. State text archives use https://flelectionfiles.floridados.gov/enightfilespublic/YYYYMMDD_ElecResultsFL.txt. The 2022 state text file contained only zero placeholders and was excluded. This is selected archive coverage, not a complete candidate career history; a missing result is explicitly unknown, not zero or proof of a first candidacy. Primary electorates, offices and district boundaries can differ. Multi-seat vote shares use total candidate votes, not turnout. Rank is not an inferred winner call.

U.S. Senate history shows 2020, 2022 and 2024 wins for distinct seats (including cycle runoffs) separately from the 100-seat composition after each cycle. Source: Inter-Parliamentary Union Parline election records at https://data.ipu.org/parliament/US/US-UC01/election/US-UC01-E20201103/ , https://data.ipu.org/parliament/US/US-UC01/election/US-UC01-E20221108/ and https://data.ipu.org/parliament/US/US-UC01/election/US-UC01-E20241105/ . Democratic-aligned totals explicitly include caucusing independents. Full/short-term contests for the same California seat are counted once; this differs from the FEC's election-contest totals. Florida's 2024 Senate winner and margin use official state counts; the page explicitly distinguishes that seat from the 2026 special election.

Validation: 70 automated tests pass, including primary-party denominator isolation, geographic isolation, exact known local counts, rank ties, source/date validation, unknown/zero distinction, live-roster isolation and Senate wins versus seats held. JavaScript syntax checks pass. Historical snapshots are dated and sourced; they are not a prediction, live feed or automatic career-history search. Rebuild helpers and downloaded research evidence are retained in the staging workspace election-watch-build. Existing settings, saved snapshots and ticker behavior are preserved.


## Election-night desk — October 26, 2026

All six watch-party additions are implemented. Night desk has What changed (source race changes in the last 30 minutes, with numeric deltas when a previous snapshot exists), scheduled Poll closings (50 states plus D.C., split time zones, live countdowns, separate Indian River/Eastern and Central-time Florida clocks), Close races, and neutral Yes/No Amendment summaries with the 60% threshold and available reported Yes shares. Race cards and Details link directly to explanations. Above-threshold partial returns are not passage calls. Existing attributed calls remain distinct from leads.

Close-race eligibility: unofficial/recount status, single seat, complete candidate counts, at least 100 candidate votes, margin at most five percentage points. Called contests, multi-seat contests, amendments and incomplete feeds are excluded. Area selection distinguishes county portions from full contests. Missing data is never a safe-seat judgment.

The freshness strip separates the dashboard fetch time, source retrieval age, and publisher timestamp. After election day, delayed-publication flags can warn even if retrieval succeeds. Indian River gets three appearances per automatic rotation when local_spotlight is on (default); host controls can disable this preference. Night desk changes its selected section on successive automatic visits. Manual navigation and pause remain available.

Schedule reference: https://www.thegreenpapers.com/G26/closing.phtml?format=gc . Florida hours independently checked at https://dos.fl.gov/elections/contacts/frequently-asked-questions/faq-voting/ . This is a reviewed election-night schedule, not live monitoring of court-ordered extensions or a polling-place lookup. New Hampshire/North Dakota variable local hours are marked; mail-ballot rules vary. The timer reaching zero means the scheduled time was reached, not that voting ended. All timestamps encode November standard time and Alaska/Hawaii dates roll into November 4 Eastern. Amendment source: https://www.leonvotes.gov/Voting/Election-Ready/General-Election-Ballot-Questions . Summaries are concise paraphrases; official full wording is linked.

Validation: 85 Python tests pass, including split-zone/date-rollover checks, coverage of all 50 states plus D.C., close-race boundaries/exclusions, first totals and numeric deltas, and saved local-rotation preference validation. JavaScript syntax checks pass. Sources, existing settings and snapshots remain free and local. No paid services added.

## GitHub website
GitHub Actions runs export_pages.py and publishes public/ to GitHub Pages. Scheduled refresh targets about five minutes during October/November 2026 and stops after November 10. Source intervals and failure backoff remain respected. GitHub scheduling/deployment can lag; public snapshot age and source timestamps are displayed. Public watchlist changes are browser-local. Host controls remain available only in the local server. Run python export_pages.py to build; no dependencies are required.


## One-minute live service (active)
The public page reads https://election-watch-live.election-watch-github.workers.dev/state.json every 60 seconds with caching disabled. The existing Python feed engine runs on overlapping GitHub-hosted collectors; a Cloudflare lease allows one publisher. Collectors start hourly, run for 125 minutes, and publish on a 60-second cycle through November 10, 2026. This computer can be off. Each source retains its interval and backoff; official publication can lag. Source checkpoints preserve last-known data across runner handoffs. A three-minute-old snapshot is visibly flagged; outages and delayed GitHub runners can interrupt the cadence. Pages redeployment is only needed for code/design changes, not new data. GitHub repository variable ELECTION_PUBLIC_STATE_URL selects the service; ELECTION_PUBLISH_TOKEN is a GitHub secret and matching Cloudflare Worker secret. Never commit the publishing key. Deploy Worker changes with npx wrangler deploy --config cloudflare/wrangler.jsonc. Start/recover a collector with gh workflow run live.yml.


### October30 collector repair
GitHub'shourlycalendarstartsproveddelayedbyseveralhours. Livecollectorsnowrun345minutesandtheactivepublisherrequestsasuccessorinthefinalhourusinganephemeralrepository-onlyActionstoken. Standbysdonotspawnchains. Hourlycronisabackstop. Amanualrehearsal=true runlastseightminutesandrequestsanormalreplacement;useitforhandoffverification. SIGTERMrequestsgracefulstopandleaserelease. Platformorqueuedrunneroutagesremainpossible; monitoractualsnapshottageandSourcehealthratherthanworkflowgreenchecks.

