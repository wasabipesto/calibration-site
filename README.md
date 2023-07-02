# Calibration Stats

A site to collect and display calibration stats for prediction markets.

TODO:

- [ ] Backend: Accept filters from frontend
- [ ] Frontend: Select filters
- [ ] Frontend: Select method (x-axis)
- [ ] Frontend: Select weight (y-axis)
- [ ] Frontend: Create multiple plots
- [ ] Frontend: Show table of markets 
- [ ] Frontend: Description/help text
- [ ] Frontend: Link to download sqlite file

Option & modifier support:

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
    - [x] Resolved probability (N/Y -> 0/100%)
    - [ ] Probability at {1,100}% through
    - [ ] Time-weighted average probability
- Weights (y-axis):
    - [x] No weighting
    - [ ] Weight markets by volume
    - [ ] Weight markets by payout (value)
    - [ ] Weight markets by number of traders
    - [ ] Weight markets by number of comments
