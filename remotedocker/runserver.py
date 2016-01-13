def start_server(publishport, subscribeport, container, command):
    print "enter function {} {} {} {}".format(publishport, subscribeport, container, command)
    import time
    import zmq
    import subprocess
    import sys

    import zmq
    import time
    context = zmq.Context()

    #outgoing messages
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://0.0.0.0:{}".format(publishport))


    #incoming messages
    #we will just reply every incoming message (request) with 'ack!'
    rep_socket = context.socket(zmq.REP)
    rep_socket.bind("tcp://0.0.0.0:{}".format(subscribeport))

    #incoming messages
    #sub_socket = context.socket(zmq.SUB)
    #sub_socket.connect("tcp://0.0.0.0:{}".format(subscribeport))
    #sub_socket.setsockopt(zmq.SUBSCRIBE,'')

    poller = zmq.Poller()
    poller.register(pub_socket,zmq.POLLIN)
    poller.register(rep_socket,zmq.POLLIN)
    sockets = [rep_socket,pub_socket]

    import pty
    master, slave = pty.openpty()

    import shlex
    p = subprocess.Popen(shlex.split('docker run -it {} {}'.format(container,command)), stdin = slave, stdout = slave, stderr = slave)
    #p = subprocess.Popen(shlex.split('sh -i'), stdin = slave, stdout = slave, stderr = slave)

    import os
    import select


    print "starting server!"


    print "wait for start signal from client"
    start = rep_socket.recv()

    print "acknowledge!"
    rep_socket.send('ack '.format(start))

    time.sleep(5)
    print "first publish"
    pub_socket.send('hi there... ')

    #print "wait for stop signal from client"
    #stop = rep_socket.recv()
    #print "acknowledge!"
    #rep_socket.send('ack '.format(stop))

    while True:
        #print "polling"
        r, w, x = select.select([master],[master],[master])
        #print "master poll: r: {} w: {} x: {}".format(r,w,x)

        sockets = [pub_socket,rep_socket]
        #print "sockets: pub {} sub {}".format(*sockets)
        zr,zw,zx = zmq.select(sockets, sockets,sockets, timeout = 0.01)
        #print "ZMQ poll: r: {} w: {} x: {}".format(zr,zw,zx)

        procpoll = p.poll()
        #print 'process: {}'.format(procpoll)

        if procpoll is not None:
	    print "ending session because process ended"
            pub_socket.send('')
            return
        
    
        if (master in r) and (pub_socket in zw):
            #print "reading!"
            fromprocess = os.read(master,1024)
            #print 'sending {}'.format(fromprocess)
            pub_socket.send(fromprocess)

        if (master in w) and (rep_socket in zr):
            #  Wait for next request from client
            #print "recv"
            message = rep_socket.recv()
            rep_socket.send('')
            #print("Received request: %s" % repr(message))
            os.write(master,message)
            #print "wrote it"

    
        time.sleep(0.001)

if __name__ == '__main__':
    start_server(5556, 5557, 'container', 'command')
