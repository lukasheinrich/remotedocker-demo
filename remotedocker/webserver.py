import flask
import multiprocessing
import random

app = flask.Flask('app')
app.debug = True


POOLSIZE = 10

import multiprocessing
pool = multiprocessing.Pool(POOLSIZE)

from runserver import start_server

resultsobjs = []

def spot_available():
    global resultsobjs
    print '# of results {}'.format(len(resultsobjs))
    for i,x in enumerate(resultsobjs):
        if x.ready():
            resultsobjs.pop(i)
            print 'freeing ready object'
    return len(resultsobjs) < POOLSIZE
        
@app.route('/start')
def start():
    print "starting "
    container = flask.request.args['image']
    command =  flask.request.args['command']
    dirmount = flask.request.args.get('dirmount',None)



    if not spot_available():
        return '',404


    publishport = random.randint(5000,5099)
    print 'spot available: {}'.format(spot_available())
    print (publishport,container,command,dirmount)
    result = pool.apply_async(start_server,(publishport,container,command,dirmount))
    global resultsobjs
    resultsobjs += [result]
    return flask.jsonify({'readfrom':publishport}) 

@app.route('/')
def home():
    return 'OK!'
    
if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 4000)
