from flask import Flask, render_template, request, jsonify 
from waitress import serve
#import requests
#import sqlite3

import uuid

app = Flask(__name__)

@app.route('/')
def get_uuid():
    return render_template('index.html')

@app.route('/get_data', methods=['POST'])
def get_data():
    # Get filter parameters from the request
    filters = request.form.getlist('filter')

    # TODO: Query the database and calculate plot

    # Placeholder data
    data = {
        "x": [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1],
        "y": [0,0.09,0.18,0.31,0.42,0.5,0.59,0.69,0.78,0.85,0.92]
    }

    return jsonify(data)

if __name__ == "__main__":
    serve(app, listen='*:80')