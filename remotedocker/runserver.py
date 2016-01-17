import termios
import struct
import fcntl
import sys
import time
import zmq
import subprocess
import sys
import os
import select
import zmq
import time
import signal

def set_winsize(fd, row, col, pid):
    print 'setting window size to rows: {} cols: {} file: {} pid: {}'.format(row,col,fd,pid)
    winsize = struct.pack("HHHH", row, col, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    os.kill(pid,signal.SIGWINCH)

def start_server(publishport, container, command, afsdirmount):
    print "enter function {} {} {}".format(publishport, container, command)
    context = zmq.Context()

    #outgoing messages
    socket = context.socket(zmq.PAIR)
    socket.bind("tcp://0.0.0.0:{}".format(publishport))

    poller = zmq.Poller()
    poller.register(socket,zmq.POLLIN)

    print "starting server on port ",publishport


    print "wait for start signal from client"
    start = socket.recv_json()

    print "acknowledge!"
    socket.send('ack '.format(start['ctrl']))

    istty = socket.recv_json()['ctrl']['tty']

    print 'is tty: {}'.format(istty)

    if istty:
        handle_tty(socket,container,command,afsdirmount)


def handle_tty(socket,container,command,afsdirmount):
    import pty
    master, slave = pty.openpty()

    term_size = socket.recv_json()['ctrl']['term_size']

    print term_size

	



    import shlex
    print "start docker: container: {} command: {} mount: {} ".format(container,command, afsdirmount)

    cmd  = 'docker run -it'
    if afsdirmount:
        cmd += ' -v {}:/output'.format(afsdirmount)
    cmd += ' {} {}'.format(container,command)

    print 'cmd {}'.format(cmd)
   
    p = subprocess.Popen(shlex.split(cmd), stdin = slave, stdout = slave, stderr = slave)
    #p = subprocess.Popen(shlex.split('sh -i'), stdin = slave, stdout = slave, stderr = slave)

    set_winsize(master,term_size['rows'],term_size['cols'],p.pid)

    while True:
        #print "polling"
        r, w, x = select.select([master],[master],[master], 0.0)
        #print "master poll: r: {} w: {} x: {}".format(r,w,x)

        zr,zw,zx = zmq.select([socket], [socket],[socket], timeout = 0.0)
        #print "ZMQ poll: r: {} w: {} x: {}".format(zr,zw,zx)

        procpoll = p.poll()
        #print 'process: {}'.format(procpoll)

        if procpoll is not None:
	    print "ending session because process ended"
            socket.send('')
            print "wait for client to end"
            b = socket.recv_json()['ctrl']
            print b
            return
        
    
        if (master in r) and (socket in zw):
            #print "reading!"
            fromprocess = os.read(master,1024)
            #print 'sending {}'.format(fromprocess)
            socket.send(fromprocess)

        if (master in w) and (socket in zr):
            #  Wait for next request from client
            #print "recv"
            message = socket.recv_json()
            #print("Received request: {} length: {}".format(message,len(message)))
	    try:
                os.write(master,message['p'])
            except KeyError:
		if 'ctrl' in message:
		    ctrlmsg = message['ctrl']
        	    if 'term_size' in ctrlmsg:
		        set_winsize(master,ctrlmsg['term_size']['rows'],ctrlmsg['term_size']['cols'],p.pid)
            #print "wrote it"

    
#        time.sleep(0.001)

if __name__ == '__main__':
    start_server(5556, 'python:2.7', 'bash','/afs/cern.ch/user/l/lheinric/testafs')
#    start_server(5556, 'python:2.7', 'bash',None)
