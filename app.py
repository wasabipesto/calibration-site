from flask import Flask, render_template, request, jsonify 
from waitress import serve
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import requests
import sqlite3
import peewee as pw
import numpy as np
import os

db_path = 'data/database.db'
db = pw.SqliteDatabase(db_path)

class BaseModel(pw.Model):
    class Meta:
        database = db

class Market(BaseModel):
    manifold_id = pw.CharField(unique=True)
    manifold_url = pw.CharField()
    question_text = pw.CharField()
    creator_username = pw.CharField()
    date_created = pw.DateTimeField()
    date_closed = pw.DateTimeField()
    open_days = pw.IntegerField()
    volume = pw.IntegerField()
    liquidity = pw.IntegerField()
    date_resolved = pw.DateTimeField()
    prob_resolved = pw.DecimalField()
    prob_at_close = pw.DecimalField()

app = Flask(__name__)
scheduler = BackgroundScheduler()
if not os.path.exists(db_path):
    print('Creating database file...')
    open(db_path, 'w').close()
db.connect()
if not Market.table_exists():
    db.create_tables([Market])

def get_all_markets():
    collection='markets'
    limit = 1000
    last = None
    data = []
    while True:
        if last:
            response = requests.get(
                'https://manifold.markets/api/v0/'+collection+'?limit='+str(limit)
                +'&before='+str(last)
                ).json()
        else:
            response = requests.get(
                'https://manifold.markets/api/v0/'+collection+'?limit='+str(limit)
                ).json()
        if len(response):   
            data += response
            last = response[len(response)-1]['id']
        if len(response) < limit:
            break
    return data

def get_full_market(market_id):
    return requests.get(
        'https://manifold.markets/api/v0/market/'+market_id
        ).json()

def get_timestamp(market, attr):
    return datetime.utcfromtimestamp(
        min(int(
            market.get(attr)
        )/1000,253401772800)
    )

def get_prob_resolved(market):
    if market.get('resolution') == 'NO':
        return 0
    elif market.get('resolution') == 'YES':
        return 1
    elif market.get('resolution') == 'MKT':
        try:
            return market['resolutionProbability']
        except KeyError:
            print('WARN: resolutionProbability does not exist on market', market['id'], '- using 0 instead.')
            return 0
    else:
        raise ValueError('Could not get resolved probability:', market)

def get_prob_at_close(market):
    return market['probability']

def get_open_days(market):
    return (get_timestamp(market, 'closeTime')-get_timestamp(market, 'createdTime')).days

def refresh_data():
    print('Starting cache refresh...')
    # start timer
    ts0 = datetime.now()
    # download litemarkets
    markets_raw = get_all_markets()
    # download list of all saved IDs
    cached_ids = [market['manifold_id'] for market in Market.select(Market.manifold_id).dicts().iterator()]
    print('Updated cache in', (datetime.now()-ts0).seconds, 'seconds.')
    
    print('Starting data download...')
    newly_resolved_markets = []
    for market in markets_raw:
        if not markets_raw.index(market) % 5000:
            # show progress
            print('Data download:', markets_raw.index(market), '/', len(markets_raw), '@', round(markets_raw.index(market)/(datetime.now()-ts0).seconds), 'mps')
        if market.get('isResolved') and \
            market.get('mechanism') == 'cpmm-1' and \
            market.get('outcomeType') == 'BINARY' and \
            not market.get('resolution') == 'CANCEL' and \
            not market['id'] in cached_ids:
            #fmarket = get_full_market(market['id'])
            newly_resolved_markets.append({
                'manifold_id': market['id'],
                'manifold_url': market['url'],
                'question_text': market['question'],
                'creator_username': market['creatorUsername'],
                'date_created': get_timestamp(market, 'createdTime'),
                'date_closed': get_timestamp(market, 'closeTime'),
                'open_days': get_open_days(market),
                'volume': market['volume'],
                'liquidity': market['totalLiquidity'],
                'date_resolved': get_timestamp(market, 'resolutionTime'),
                'prob_resolved': get_prob_resolved(market),
                'prob_at_close': get_prob_at_close(market),
            })
    print('Downloaded all data in', (datetime.now()-ts0).seconds, 'seconds.')

    if len(newly_resolved_markets):
        # save everything to the db
        print('Saving', len(newly_resolved_markets), 'newly resolved markets...')
        insert_batch_size = 100
        with db.atomic():
            for idx in range(0, len(newly_resolved_markets), insert_batch_size):
                Market.insert_many(
                    newly_resolved_markets[idx:idx+insert_batch_size]
                    ).execute()
        print('Complete.')
    else:
        print('No changes to be made.')


@app.route('/')
def index_base():
    return render_template('index.html')

@app.route('/manifold')
def index_manifold():
    return render_template('manifold.html')

def filter_numeric_gtlt(markets, request, attr):
    if request.form.get(attr+'_val') and request.form.get(attr+'_mod'):
        if request.form.get(attr+'_mod') == 'gt':
            markets = markets.where(getattr(Market, attr) >= request.form.get(attr+'_val'))
        elif request.form.get(attr+'_mod') == 'lt':
            markets = markets.where(getattr(Market, attr) <= request.form.get(attr+'_val'))
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

def filter_text_equals(markets, request, attr):
    if request.form.get(attr):
        markets = markets.where(getattr(Market, attr) == request.form.get(attr))
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

def filter_text_conatins(markets, request, attr):
    if request.form.get(attr):
        markets = markets.where(getattr(Market, attr).contains(request.form.get(attr)))
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

@app.route('/manifold/get_data', methods=['POST'])
def get_data():
    print('POST /manifold/get_data')
    
    # get all markets
    markets = Market.select()

    # filter by each criterion
    #markets = filter_bool(markets, request, 'is_predictive')
    markets = filter_text_equals(markets, request, 'creator_username')
    markets = filter_text_conatins(markets, request, 'question_text')
    #markets = filter_text_conatins(markets, request, 'group_string')
    markets = filter_numeric_gtlt(markets, request, 'volume')
    markets = filter_numeric_gtlt(markets, request, 'liquidity')
    #markets = filter_numeric_gtlt(markets, request, 'payout')
    #markets = filter_numeric_gtlt(markets, request, 'num_traders')
    #markets = filter_numeric_gtlt(markets, request, 'num_comments')
    markets = filter_numeric_gtlt(markets, request, 'date_created')
    markets = filter_numeric_gtlt(markets, request, 'date_closed')
    markets = filter_numeric_gtlt(markets, request, 'open_days')

    if len(markets) == 0:
        return jsonify({
            'status': 'error',
            'error_description': 'No markets in sample!',
        })

    # set x-axis method
    xbin_data = {
        'prob_at_close': {
            'xlabel': 'Probability at Close',
        },
        #'prob_at_midpoint': {
        #    'xlabel': 'Probability at Midpoint',
        #},
        #'prob_time_weighted': {
        #    'xlabel': 'Time-Weighted Probability',
        #},
    }
    if request.form.get('xbin_modifier') in xbin_data.keys():
        xaxis_attr = request.form.get('xbin_modifier')
    else:
        xaxis_attr = 'prob_at_close'

    # set y-axis weight
    ybin_data = {
        'none': {
            'ylabel': 'Average Resolution Value',
        },
        'volume': {
            'ylabel': 'Resolution Value, Weighted by Volume',
        },
        #'payout': {
        #    'ylabel': 'Resolution Value, Weighted by Payout',
        #},
        #'traders': {
        #    'ylabel': 'Resolution Value, Weighted by Traders',
        #},
    }
    if request.form.get('ybin_modifier') in ybin_data.keys():
        yaxis_attr = request.form.get('ybin_modifier')
    else:
        yaxis_attr = 'none'

    # generate x-axis bins
    xbins = {}
    if request.form.get('xbin_size') and \
        round(float(request.form.get('xbin_size')),3) in [round(i,3) for i in np.arange(0.005, 1, 0.005)]:
        xbin_size = round(float(request.form.get('xbin_size')),3)
    else:
        xbin_size = 0.01
    xb = xbin_size/2
    while xb < 1:
        xbins.update({round(xb,4):{'forecast':[],'resolved':[],'weight':[]}})
        xb+=xbin_size
    
    for market in markets.dicts().iterator():
        # calculate appropriate xaxis bins
        xb = round(int((float(market[xaxis_attr]) - xbin_size/2) / xbin_size) * xbin_size + xbin_size/2, 4)
        # calculate appropriate yaxis weight
        if yaxis_attr == 'none':
            yaxis_weight = 1
        else:
            yaxis_weight = market[yaxis_attr]
        # save data
        xbins[xb]['forecast'].append(market[xaxis_attr])
        xbins[xb]['resolved'].append(market['prob_resolved'])
        xbins[xb]['weight'].append(yaxis_weight)

    # assemble data to return
    data = {
        'status': 'success',
        'x': [],
        'y': [],
        'title': 'Calibration Plot',
        'xlabel': xbin_data[xaxis_attr]['xlabel'],
        'ylabel': ybin_data[yaxis_attr]['ylabel'],
        'num_markets': [],
        'num_markets_total': 0,
        'brier_score': 0, # TODO
    }
    # average everything out
    brier_cumsum = 0
    brier_weight = 0
    for xv in xbins:
        xb = xbins[xv]
        if len(xb['resolved']):
            sumproduct = sum([xb['resolved'][i]*xb['weight'][i] for i in range(len(xb['resolved']))])
            weight_sum = sum(xb['weight'])
            data['x'].append(xv)
            data['y'].append(sumproduct / weight_sum)
            brier_cumsum += sum([(xb['resolved'][i]-xb['forecast'][i])**2 * xb['weight'][i] for i in range(len(xb['resolved']))])
            brier_weight += sum([xb['weight'][i] for i in range(len(xb['resolved']))])
            data['brier_score'] = round(brier_cumsum / brier_weight,4)
            data['num_markets'].append(len(xb['resolved']))
            data['num_markets_total'] += len(xb['resolved'])
    return jsonify(data)

if __name__ == "__main__":
    print('App started.')
    scheduler.add_job(
        refresh_data, 'interval', minutes=60, 
        start_date=(datetime.now()+timedelta(seconds=10))
        )
    scheduler.start()
    serve(app, listen='*:80')