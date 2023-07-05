from flask import Flask, render_template, request, jsonify, send_file
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
    group_text = pw.CharField(null=True)
    is_predictive = pw.BooleanField()
    payout = pw.IntegerField()
    description_length = pw.IntegerField()
    num_trades = pw.IntegerField()
    num_traders = pw.IntegerField()
    num_comments = pw.IntegerField()
    num_commenters = pw.IntegerField()
    prob_at_q1 = pw.DecimalField()
    prob_at_q2 = pw.DecimalField()
    prob_at_q3 = pw.DecimalField()
    prob_time_weighted = pw.DecimalField()

app = Flask(__name__)
scheduler = BackgroundScheduler()
if not os.path.exists(db_path):
    print('Creating database file...')
    open(db_path, 'w').close()
db.connect()
if not Market.table_exists():
    db.create_tables([Market])

def get_all_markets():
    limit = 1000
    last = None
    data = []
    while True:
        if last:
            response = requests.get(
                'https://manifold.markets/api/v0/markets'+
                '?limit='+str(limit)+
                '&before='+str(last)
                ).json()
        else:
            response = requests.get(
                'https://manifold.markets/api/v0/markets'+
                '?limit='+str(limit)
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

def get_market_comments(market_id):
    try:
        return requests.get(
            'https://manifold.markets/api/v0/comments'+
                '?contractId='+market_id
                ).json()
    except requests.exceptions.JSONDecodeError:
        # for markets like yCZog61lRFbJZnz8UW76
        # fix when /comments gets paginated
        return []

def get_market_bets(market_id):
    limit = 1000
    last = None
    data = []
    while True:
        if last:
            response = requests.get(
                'https://manifold.markets/api/v0/bets'+
                '?contractId='+market_id+
                '&limit='+str(limit)+
                '&before='+str(last)
                ).json()
        else:
            response = requests.get(
                'https://manifold.markets/api/v0/bets'+
                '?contractId='+market_id+
                '&limit='+str(limit)
                ).json()
        if len(response):   
            data += response
            last = response[len(response)-1]['id']
        if len(response) < limit:
            break
    return data

def get_ts(item, attr):
    return datetime.utcfromtimestamp(
        min(int(
            item.get(attr)
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

def clean_bets(market, bets):
    # add items for market creation and close
    if len(bets):
        # market closeTime is user-set and can be before actual end
        close_time = max(
            get_ts(market, 'closeTime'),
            get_ts(market, 'createdTime')+timedelta(seconds=1),
            get_ts(bets[len(bets)-1], 'createdTime')+timedelta(seconds=1),
            )
        bets_clean = [{
            'id': 'market_created',
            'timestamp': get_ts(market, 'createdTime'),
            'prob_before': None,
            'prob_after': bets[0]['probBefore'],
        },{
            'id': 'market_closed',
            'timestamp': close_time,
            'prob_before': bets[len(bets)-1]['probAfter'],
            'prob_after': None,
        }]
        # copy in all bets
        for bet in bets:
            bets_clean.append({
                'id': bet['id'],
                'timestamp': get_ts(bet, 'createdTime'),
                'prob_before': bet['probBefore'],
                'prob_after': bet['probAfter'],
            })
        return sorted(bets_clean, key=lambda k: k['timestamp'])
    else:
        # megamind face: no bets?
        # ^ this joke is over a year old and still funny
        close_time = max(
            get_ts(market, 'closeTime'),
            get_ts(market, 'createdTime')+timedelta(seconds=1),
            )
        return [{
            'id': 'market_created',
            'timestamp': get_ts(market, 'createdTime'),
            'prob_before': None,
            'prob_after': market['probability'],
        },{
            'id': 'market_closed',
            'timestamp': close_time,
            'prob_before': market['probability'],
            'prob_after': None,
        }]

def get_prob_at_pct(bets, percent):
    timestamp = bets[0]['timestamp'] + (bets[len(bets)-1]['timestamp']-bets[0]['timestamp'])*percent
    for bet in bets:
        if bet['timestamp'] > timestamp:
            return bet['prob_before']

def get_prob_time_weighted(bets):
    prob_weighted = 0
    for bet in bets[1:]:
        prob_weighted += bet['prob_before'] * (bet['timestamp']-bets[bets.index(bet)-1]['timestamp']).total_seconds()
    return prob_weighted / (bets[len(bets)-1]['timestamp']-bets[0]['timestamp']).total_seconds()

def get_open_days(market):
    return (get_ts(market, 'closeTime')-get_ts(market, 'createdTime')).days

def get_description_length(market):
    return len(market['textDescription'])

def get_group_text(market):
    return str(market.get('groupSlugs'))

def get_is_predictive(market):
    if market.get('groupSlugs') and 'nonpredictive' in market.get('groupSlugs'):
        return False
    else:
        return True

def get_payout(market, bets):
    positions = {
        'YES': 0,
        'NO': 0,
    }
    # collate positions
    for bet in bets:
        positions[bet['outcome']] += bet['shares']
    # calculate payout
    if market['resolution'] in positions.keys():
        return positions[market['resolution']]
    else:
        return positions['YES'] * market['resolutionProbability'] + positions['NO'] * (1-market['resolutionProbability'])


def get_num_trades(bets):
    return len(bets)

def get_num_traders(bets):
    return len(set([i['userId'] for i in bets]))

def get_num_comments(comments):
    return len(comments)

def get_num_commenters(comments):
    return len(set([i['userId'] for i in comments]))

def save_market(market):
    print('Saving market', market['manifold_id'])
    Market.insert(market).execute()

def refresh_data():
    print('Starting cache refresh...')
    # start timer
    ts0 = datetime.now()
    # download litemarkets
    markets_raw = get_all_markets()
    # download list of all saved IDs
    cached_ids = [market['manifold_id'] for market in Market.select(Market.manifold_id).dicts()]
    print('Updated cache in', (datetime.now()-ts0).seconds, 'seconds.')
    
    print('Starting data download...')
    for market in markets_raw:
        if not markets_raw.index(market) % 5000:
            # show progress
            print('Data download:', markets_raw.index(market), '/', len(markets_raw), '@', round(markets_raw.index(market)/(datetime.now()-ts0).seconds), 'mps')
        if market.get('isResolved') and \
            market.get('mechanism') == 'cpmm-1' and \
            market.get('outcomeType') == 'BINARY' and \
            not market.get('resolution') == 'CANCEL' and \
            not market['id'] in cached_ids:
            # download all details
            full_market = get_full_market(market['id'])
            comments = get_market_comments(market['id'])
            bets = get_market_bets(market['id'])
            # save data
            save_market({
                'manifold_id': market['id'],
                'manifold_url': market['url'],
                'question_text': market['question'],
                'creator_username': market['creatorUsername'],
                'date_created': get_ts(market, 'createdTime'),
                'date_closed': get_ts(market, 'closeTime'),
                'open_days': get_open_days(market),
                'volume': market['volume'],
                'liquidity': market['totalLiquidity'],
                'date_resolved': get_ts(market, 'resolutionTime'),
                'prob_resolved': get_prob_resolved(market),
                'prob_at_close': get_prob_at_close(market),
                'group_text': get_group_text(full_market),
                'is_predictive': get_is_predictive(full_market),
                'payout': get_payout(market, bets),
                'description_length': get_description_length(full_market),
                'num_trades': get_num_trades(bets),
                'num_traders': get_num_traders(bets),
                'num_comments': get_num_comments(comments),
                'num_commenters': get_num_commenters(comments),
                'prob_at_q1': get_prob_at_pct(clean_bets(market, bets), 0.25),
                'prob_at_q2': get_prob_at_pct(clean_bets(market, bets), 0.50),
                'prob_at_q3': get_prob_at_pct(clean_bets(market, bets), 0.75),
                'prob_time_weighted': get_prob_time_weighted(clean_bets(market, bets)),
            })
    print('Downloaded all data in', (datetime.now()-ts0).seconds, 'seconds.')


@app.route('/')
def index_base():
    return render_template('index.html')

@app.route('/db')
def download_db():
    return send_file('/usr/src/data/database.db')

@app.route('/manifold')
def index_manifold():
    return render_template('manifold.html')

def filter_gtlt(markets, request, attr):
    if request.form.get(attr+'_val') and request.form.get(attr+'_mod'):
        if request.form.get(attr+'_mod') == 'gt':
            markets = markets.where(getattr(Market, attr) >= request.form.get(attr+'_val'))
        elif request.form.get(attr+'_mod') == 'lt':
            markets = markets.where(getattr(Market, attr) <= request.form.get(attr+'_val'))
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

def filter_predictive(markets, request, attr):
    if request.form.get(attr) == 'predictive':
        markets = markets.where(getattr(Market, attr) == True)
    elif request.form.get(attr) == 'nonpredictive':
        markets = markets.where(getattr(Market, attr) == False)
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

def filter_equals(markets, request, attr):
    if request.form.get(attr):
        markets = markets.where(getattr(Market, attr) == request.form.get(attr))
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

def filter_conatins(markets, request, attr):
    if request.form.get(attr):
        markets = markets.where(getattr(Market, attr).contains(request.form.get(attr)))
    #print(str(len(markets))+' markets remaining after '+attr+' filter.')
    return markets

def scale_list(input_list, output_min, output_max, output_default):
    scaled_list = []
    input_min = min(input_list)
    input_max = max(input_list)
    input_range = input_max - input_min
    output_range = output_max - output_min
    
    if input_min == input_max:
        # Handle the case when all input values are the same
        return [output_default] * len(input_list)

    for value in input_list:
        # Scale the value to the output range
        scaled_value = ((value - input_min) / input_range) * output_range + output_min
        scaled_list.append(scaled_value)
    return scaled_list

@app.route('/manifold/get_data', methods=['POST'])
def get_data():
    print('POST /manifold/get_data')
    
    # get all markets
    markets = Market.select()

    # filter by each criterion
    markets = filter_equals(markets, request, 'creator_username')
    markets = filter_conatins(markets, request, 'question_text')
    markets = filter_conatins(markets, request, 'group_text')
    markets = filter_gtlt(markets, request, 'description_length')
    markets = filter_predictive(markets, request, 'is_predictive')
    markets = filter_gtlt(markets, request, 'volume')
    markets = filter_gtlt(markets, request, 'liquidity')
    markets = filter_gtlt(markets, request, 'payout')
    markets = filter_gtlt(markets, request, 'num_trades')
    markets = filter_gtlt(markets, request, 'num_traders')
    markets = filter_gtlt(markets, request, 'date_created')
    markets = filter_gtlt(markets, request, 'date_closed')
    markets = filter_gtlt(markets, request, 'open_days')
    markets = filter_gtlt(markets, request, 'num_comments')

    num_markets_total = len(markets)
    if num_markets_total == 0:
        return jsonify({
            'status': 'error',
            'error_description': 'No markets in sample!',
        })

    # set x-axis method
    xbin_data = {
        'prob_at_close': {
            'xlabel': 'Probability at Close',
        },
        'prob_at_q1': {
            'xlabel': 'Probability at 25%',
        },
        'prob_at_q2': {
            'xlabel': 'Probability at Midpoint',
        },
        'prob_at_q3': {
            'xlabel': 'Probability at 75%',
        },
        'prob_time_weighted': {
            'xlabel': 'Time-Weighted Probability',
        },
    }
    if request.form.get('xbin_modifier') in xbin_data.keys():
        xaxis_attr = request.form.get('xbin_modifier')
    else:
        xaxis_attr = 'prob_time_weighted'

    # set y-axis weight
    ybin_data = {
        'none': {
            'ylabel': 'Average Resolution Value',
        },
        'volume': {
            'ylabel': 'Resolution Value, Weighted by Volume',
        },
        'payout': {
            'ylabel': 'Resolution Value, Weighted by Payout',
        },
        'num_traders': {
            'ylabel': 'Resolution Value, Weighted by Traders',
        },
    }
    if request.form.get('ybin_modifier') in ybin_data.keys():
        yaxis_attr = request.form.get('ybin_modifier')
    else:
        yaxis_attr = 'none'

    point_data = {
        'none': {
            'prefix': '',
            'postfix': '',
        },
        'count': {
            'prefix': '',
            'postfix': ' markets',
        },
        'volume': {
            'prefix': 'M$',
            'postfix': ' volume',
        },
        'payout': {
            'prefix': 'M$',
            'postfix': ' payout',
        },
        'num_traders': {
            'prefix': '',
            'postfix': ' traders',
        },
    }
    if request.form.get('point_modifier') in point_data.keys():
        point_attr = request.form.get('point_modifier')
    else:
        point_attr = 'none'

    # generate x-axis bins
    xbins = {}
    if request.form.get('xbin_size') and \
        round(float(request.form.get('xbin_size')),3) in [round(i,3) for i in np.arange(0.005, 1, 0.005)]:
        xbin_size = round(float(request.form.get('xbin_size')),3)
    else:
        # default to about 20 markets per bin
        xbin_size = np.clip(np.ceil(20 / num_markets_total / 0.005) * 0.005, 0.01, 0.1)
    xb = xbin_size/2
    while xb < 1:
        xbins.update({round(xb,4):{'forecast':[],'resolved':[],'yaxis_weight':[],'point_weight':[]}})
        xb+=xbin_size
    
    for market in markets.dicts().iterator():
        # calculate appropriate xaxis bins
        xb = round(int((float(market[xaxis_attr]) - xbin_size/2) / xbin_size) * xbin_size + xbin_size/2, 4)
        if not xb in xbins.keys():
            print('Error: Count not fit market', market['manifold_id'], xaxis_attr, market[xaxis_attr], '->', xb, 'to xbins', list(xbins.keys()))
            continue
        # calculate appropriate yaxis weight
        if yaxis_attr == 'none':
            yaxis_weight = 1
        else:
            yaxis_weight = market[yaxis_attr]
        # save data
        xbins[xb]['forecast'].append(market[xaxis_attr])
        xbins[xb]['resolved'].append(market['prob_resolved'])
        xbins[xb]['yaxis_weight'].append(yaxis_weight)
        if point_attr in ['none', 'count']:
            xbins[xb]['point_weight'].append(1)
        else:
            xbins[xb]['point_weight'].append(market[point_attr])

    # assemble data to return
    data = {
        'status': 'success',
        'x': [],
        'y': [],
        'title': 'Calibration Plot',
        'xlabel': xbin_data[xaxis_attr]['xlabel'],
        'ylabel': ybin_data[yaxis_attr]['ylabel'],
        'point_size': [],
        'point_desc': [],
        'num_markets_total': num_markets_total,
        'brier_score': 0,
    }

    brier_cumsum = 0
    brier_weight = 0
    for xv in xbins:
        xb = xbins[xv]
        if len(xb['resolved']):
            # calculate and save x and y values for plot
            sumproduct = sum([xb['resolved'][i]*xb['yaxis_weight'][i] for i in range(len(xb['resolved']))])
            weight_sum = sum(xb['yaxis_weight'])
            data['x'].append(xv)
            data['y'].append(sumproduct / weight_sum)
            # calculate overall brier score
            brier_cumsum += sum([(xb['resolved'][i]-xb['forecast'][i])**2 * xb['yaxis_weight'][i] for i in range(len(xb['resolved']))])
            brier_weight += sum([xb['yaxis_weight'][i] for i in range(len(xb['resolved']))])
            # calculate and save point size and hovertext
            if point_attr == 'none':
                num_markets = len(xb['resolved'])
                data['point_size'].append(10)
                data['point_desc'].append(str(num_markets)+' markets')
            elif point_attr == 'count':
                num_markets = len(xb['resolved'])
                data['point_size'].append(num_markets)
                data['point_desc'].append(str(num_markets)+' markets')
            else:
                sum_attr = sum([xb['point_weight'][i] for i in range(len(xb['resolved']))])
                data['point_size'].append(sum_attr)
                data['point_desc'].append(point_data[point_attr]['prefix']+str(sum_attr)+point_data[point_attr]['postfix'])
            
    
    # save final brier score
    data['brier_score'] = round(brier_cumsum / brier_weight, 4)
    # rescale point sizes
    data['point_size'] = scale_list(data['point_size'], 8, 32, 10)

    # return data
    return jsonify(data)

if __name__ == "__main__":
    print('App started.')
    scheduler.add_job(
        refresh_data, 'interval', minutes=60, 
        start_date=(datetime.now()+timedelta(seconds=10))
        )
    scheduler.start()
    serve(app, listen='*:80')