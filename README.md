# Calibration Stats

> A site to collect and display calibration stats for prediction markets.

## Manifold

| Feature Implementation Table | |
| --- | --- |
| **Filters** |
| Creator username | ✅ Implemented |
| Question text contains | ✅ Implemented |
| Group contains | ⏳ Implementing |
| Description length | ✅ Implemented |
| Classified as predictive | ✅ Implemented |
| Market volume | ✅ Implemented |
| Liquidity pool | ✅ Implemented |
| Total payout amount (value) | ✅ Implemented |
| Number of trades | ✅ Implemented |
| Number of unique traders | ✅ Implemented |
| Number of unique holders | ⛔ Not Planned |
| Number of comments | ✅ Implemented |
| Number of unique commenters | ⛔ Not Planned |
| Created date/closed date | ✅ Implemented |
| Open length (days) | ✅ Implemented |
| Was re-resolved or resolved by admins | ⛔ Unavailable |
| **Methods (x-axis)** |
| Resolved probability (N/Y -> 0/100%) | ✅ Implemented |
| Probability at 25/50/75% through | ✅ Implemented |
| Time-weighted average probability | ✅ Implemented |
| **Weights (y-axis)** |
| No weighting | ✅ Implemented |
| Weight markets by volume | ✅ Implemented |
| Weight markets by payout (value) | ✅ Implemented |
| Weight markets by number of traders | ✅ Implemented |
| Weight markets by market length | ⏳ Not Implemented |
| Weight markets by number of comments | ⛔ Not Planned |
| **Other** |
| Adjustable x-bin size | ✅ Implemented |
| Show number of markets in each bin | ✅ Implemented |
| Show total number of markets in sample | ✅ Implemented |
| Show Brier score | ✅ Implemented |
| Create multiple plots | ⛔ Not Planned |
| Show table of all selected markets | ⛔ Not Planned |
| Show list of markets in particular bin | ⛔ Not Planned |
| Literally any documentation | ⏳ Not Implemented |
| Tooltips on methods/weights | ⏳ Not Implemented |
| Link to download db | ✅ Implemented |
| Dynamically size datapoints | ✅ Implemented |

## Running

The server runs entirely in Python with minimal dependencies. You can run it like so:

```
git clone git@github.com:wasabipesto/calibration-site.git
cd calibration-site
pip install -r requirements.txt
python app.py
```

For convenience, I run it in Docker:

```
docker build -t calibration-site .
docker run -d \
    -p 9632:80 \
    -v /opt/calibration-site/data:/usr/src/data \
    -u 1001 \
    --restart unless-stopped \
    --name calibration-site \
    calibration-site
```
