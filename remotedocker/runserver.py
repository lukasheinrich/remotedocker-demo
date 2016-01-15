import termios
import struct
import fcntl
import sys

def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)



def start_server(publishport, container, command):
    print "enter function {} {} {}".format(publishport, container, command)
    import time
    import zmq
    import subprocess
    import sys

    import zmq
    import time
    context = zmq.Context()

    #outgoing messages
    socket = context.socket(zmq.PAIR)
    socket.bind("tcp://0.0.0.0:{}".format(publishport))

    poller = zmq.Poller()
    poller.register(socket,zmq.POLLIN)
    sockets = [socket]

    import pty
    master, slave = pty.openpty()
    set_winsize(master,10,150)

    import shlex
    afsdirmount = '/afs/cern.ch/user/l/lheinric/testafs'
    subprocess.call(shlex.split('cvmfs_config probe'))
    print "start docker"
    # p = subprocess.Popen(shlex.split('docker run -it -v /cvmfs:/cvmfs -v {}:/output {} {}'.format(afsdirmount,container,command)), stdin = slave, stdout = slave, stderr = slave)
    p = subprocess.Popen(shlex.split('sh -i'), stdin = slave, stdout = slave, stderr = slave)

    import os
    import select

    print "starting server!"
    print "wait for start signal from client"
    start = socket.recv()

    print "acknowledge!"
    socket.send('ack '.format(start))

    print "first publish"
    socket.send('hi there... ')

    sockets = [socket]

    while True:
        #print "polling"
        r, w, x = select.select([master],[master],[master], 0.0)
        #print "master poll: r: {} w: {} x: {}".format(r,w,x)

        #print "sockets: pub {} sub {}".format(*sockets)
        zr,zw,zx = zmq.select(sockets, sockets,sockets, timeout = 0.0)
        #print "ZMQ poll: r: {} w: {} x: {}".format(zr,zw,zx)

        procpoll = p.poll()
        #print 'process: {}'.format(procpoll)

        if procpoll is not None:
	    print "ending session because process ended"
            socket.send('')
            return
        
        if (master in r) and (socket in zw):
            #print "reading!"
            fromprocess = os.read(master,1024)
            #print 'sending {}'.format(fromprocess)
            socket.send(fromprocess)

        if (master in w) and (socket in zr):
            #  Wait for next request from client
            #print "recv"
            message = socket.recv()
            socket.send('')
            #print("Received request: %s" % repr(message))
            os.write(master,message)
            #print "wrote it"

if __name__ == '__main__':
    start_server(5556, 5557, 'container', 'command')
