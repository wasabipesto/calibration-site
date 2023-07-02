# untitled manifold calibration project

TODO:

- [x] Scheduled tasks
    - [x] Download bulk data from the official API
    - [ ] Download individual datafiles from the official API
        - [ ] Alternatively, download bulk bets and comments
    - [x] Save all market data in sqlite
- [ ] Webserver backend
    - [ ] Serve an API with configurable filters & methods
        - [ ] Query from sqlite
    - [ ] Serve simple HTML/JS to query API and build plot
        - [ ] Select method
        - [ ] Select criteria
        - [ ] Select multiple criteria at once
        - [ ] Create multiple plots
        - [ ] Link to download sqlite file

Calculations, filters, and methods:

- Filters:
    - [ ] Creator username (text input)
    - [ ] Created date/closed date/resolved date
    - [ ] Open length (days)
    - [ ] Liquidity pool
    - [ ] Market volume
    - [ ] Total payout amount (value)
    - [ ] Question length
    - [ ] Description length
    - [ ] Number of trades
    - [ ] Number of unique traders
    - [ ] Number of unique holders (had open position at close)
    - [ ] Number of comments
    - [ ] Number of unique commenters
    - [ ] Is predictive/serious
    - [ ] Was re-resolved or resolved by admins
    - [ ] List of tags/groups
    - [ ] Resolved YES
    - [ ] Resolved NO
- Methods (x-axis):
    - [ ] Resolved probability (N/Y -> 0/100%)
    - [ ] Probability at {1,100}% through
    - [ ] Time-weighted average probability
