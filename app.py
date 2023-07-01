from flask import Flask 
from waitress import serve

import uuid

app = Flask(__name__)

@app.route('/')
def get_uuid():
    return str(uuid.uuid4())

if __name__ == "__main__":
    serve(app, listen='*:80')