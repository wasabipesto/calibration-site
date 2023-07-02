from flask import Flask, render_template, request, jsonify 
from waitress import serve
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import requests
import sqlite3
import uuid
import peewee as pw
import numpy as np
import os

db_path = 'data/database.db'
db = pw.SqliteDatabase(db_path)

class BaseModel(pw.Model):
    class Meta:
        database = db

class Market(BaseModel):
    manifold_id      = pw.CharField(unique=True)
    last_updated     = pw.DateTimeField(default=datetime.now)
    creator_username = pw.CharField()
    created_date     = pw.DateTimeField()
    closed_date      = pw.DateTimeField()
    resolved_date    = pw.DateTimeField()

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

def clean_timestamp(ts):
    if ts:
        return datetime.utcfromtimestamp(min(int(ts)/1000,253401772800))
    else:
        return None

def refresh_data():
    print('Starting data refresh...')
    markets_raw = get_all_markets()
    
    print('Starting data download...')
    newly_resolved_markets = []
    for market in markets_raw:
        if not markets_raw.index(market) % 1000:
            print('Data download:', markets_raw.index(market), '/', len(markets_raw))
        if market.get('isResolved') and market.get('outcomeType') == 'BINARY' and market.get('mechanism') == 'cpmm-1':
            try:
                market_from_db = Market.get(Market.manifold_id == market['id'])
            except Market.DoesNotExist:
                newly_resolved_markets.append({
                    'manifold_id': market['id'],
                    'creator_username': market['creatorUsername'],
                    'created_date': clean_timestamp(market.get('createdTime')),
                    'closed_date': clean_timestamp(market.get('closeTime')),
                    'resolved_date': clean_timestamp(market.get('resolutionTime')),
                })

    if len(newly_resolved_markets):
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
def index_page():
    return render_template('index.html')

@app.route('/get_data', methods=['POST'])
def get_data():
    print('Fulfilling request for data...')

    # Get filter parameters from the request
    filters = request.form.getlist('filter')
    print(filters)

    # TODO: Query the database and calculate plot

    # Placeholder data
    data1 = {
        "x": [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1],
        "y": [0,0.09,0.18,0.31,0.42,0.5,0.59,0.69,0.78,0.85,0.92]
    }
    data2 = {
        "x": [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1],
        "y": [0,0.04,0.09,0.15,0.21,0.27,0.46,0.71,0.83,0.84,0.85]
    }
    if filters == ['default']:
        data = data1
    else:
        data = data2

    return jsonify(data)

if __name__ == "__main__":
    scheduler.add_job(
        refresh_data, 
        'interval', 
        minutes=5, 
        start_date=(datetime.now()+timedelta(seconds=5))
        )
    scheduler.start()
    serve(app, listen='*:80')