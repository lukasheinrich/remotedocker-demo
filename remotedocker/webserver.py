import flask
import multiprocessing
import random

app = flask.Flask('app')
app.debug = True

import multiprocessing
pool = multiprocessing.Pool(4)

from runserver import start_server

@app.route('/start')
def start():
    print "starting "
    container = flask.request.args['container']
    command =  flask.request.args['command']
    publishport = random.randint(5000,6000) 
    result = pool.apply_async(start_server,(publishport,container,command))
    return flask.jsonify({'readfrom':publishport}) 

@app.route('/')
def home():
    return 'OK!'
    
if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 5000)
