# smart-money-watch

Watches SEC EDGAR for new 13F filings from a fixed group of institutional managers and publishes `status.json`.
A desktop app reads that file to show a "new filings available" badge. Only public SEC data is stored here.

* `managers.json` - the managers to watch (names, public SEC CIK numbers, alias filers)
* `watch.py` - the checker (Python standard library only)
* `.github/workflows/watch.yml` - runs daily in the filing window (days 30-47 after each quarter end) and on Mondays otherwise
* `status.json` - the result: per manager, recent 13F filings; per quarter, how many managers have filed

Setup: add a repository secret named `SEC_EMAIL` (SEC requires a contact email in the User-Agent), and under
Settings > Actions > General set Workflow permissions to "Read and write".
