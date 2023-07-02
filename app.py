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
    creator_username = pw.CharField()
    created_date = pw.DateTimeField()
    closed_date = pw.DateTimeField()
    volume = pw.IntegerField()
    resolved_date = pw.DateTimeField()
    resolved_prob = pw.DecimalField()
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

def get_resolved_prob(market):
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

def prob_at_close(market):
    return market['probability']

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
            print('Data download:', markets_raw.index(market), '/', len(markets_raw))
        if market.get('isResolved') and \
            market.get('mechanism') == 'cpmm-1' and \
            market.get('outcomeType') == 'BINARY' and \
            not market.get('resolution') == 'CANCEL' and \
            not market['id'] in cached_ids:
            #fmarket = get_full_market(market['id'])
            newly_resolved_markets.append({
                'manifold_id': market['id'],
                'creator_username': market['creatorUsername'],
                'created_date': get_timestamp(market, 'createdTime'),
                'closed_date': get_timestamp(market, 'closeTime'),
                'volume': market['volume'],
                'resolved_date': get_timestamp(market, 'resolutionTime'),
                'resolved_prob': get_resolved_prob(market),
                'prob_at_close': prob_at_close(market),
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

@app.route('/manifold/get_data', methods=['POST'])
def get_data():
    print('Fulfilling request for data...')
    
    # get all markets
    markets_filtered = Market.select()
    # filter by each criteria
    if request.form.get('min_volume'):
        markets_filtered = markets_filtered.where(
            Market.volume >= request.form.get('min_volume')
        )
    if request.form.get('min_open_days'):
        markets_filtered = markets_filtered.where(
            (Market.created_date - Market.closed_date).days >= request.form.get('min_open_days')
        )

    # set x-axis method
    if request.form.get('xbin_modifier') in [
        'prob_at_close',
        #'prob_at_midpoint',
        #'prob_time_weighted',
    ]:
        xaxis_attr = request.form.get('xbin_modifier')
    else:
        xaxis_attr = 'prob_at_close'

    # set y-axis weight
    if request.form.get('ybin_modifier') in [
        'none',
        'volume',
        #'value',
        #'traders',
    ]:
        yaxis_attr = request.form.get('ybin_modifier')
    else:
        yaxis_attr = 'none'

    # generate x-axis bins
    xbins = {}
    if request.form.get('xbin_size') and \
        float(request.form.get('xbin_size')) in [
            0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1
        ]:
        xbin_size = float(request.form.get('xbin_size'))
    else:
        xbin_size = 0.01
    xb = xbin_size/2
    while xb < 1:
        xbins.update({round(xb,4):{'v':[],'w':[]}})
        xb+=xbin_size
    
    for market in markets_filtered.dicts().iterator():
        # calculate appropriate xaxis bins
        xb = round(int((float(market[xaxis_attr]) - xbin_size/2) / xbin_size) * xbin_size + xbin_size/2, 4)
        # calculate appropriate yaxis weight
        if yaxis_attr == 'none':
            yaxis_weight = 1
        else:
            yaxis_weight = market[yaxis_attr]
        # save data
        xbins[xb]['v'].append(market['resolved_prob'])
        xbins[xb]['w'].append(yaxis_weight)

    # average everything out
    data = {
        'x': list(xbins.keys()),
        'y': [],
    }
    for xb in xbins.values():
        value_sumproduct = sum([xb['v'][i]*xb['w'][i] for i in range(len(xb['v']))])
        weight_sum = sum(xb['w'])
        data['y'].append(value_sumproduct / weight_sum)
    return jsonify(data)

if __name__ == "__main__":
    print('App started.')
    scheduler.add_job(
        refresh_data, 
        'interval', 
        minutes=5, 
        start_date=(datetime.now()+timedelta(seconds=15))
        )
    scheduler.start()
    serve(app, listen='*:80')