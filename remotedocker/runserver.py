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
import docker

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
    socket.send_json({'ctrl':'ackstart'.format(start['ctrl'])})

    istty = socket.recv_json()['ctrl']['tty']

    print 'is tty: {}'.format(istty)


    try:
        container_id = start_container(container,command,afsdirmount,istty)
    except RuntimeError:
        print "starting container failed"
	socket.send_json({'ctrl':'terminated'})
        return
    if istty:
        handle_tty(socket,container_id)
    else:
        handle_nontty(socket,container_id)

def start_container(container,command,afsdirmount,istty):
    volumes = []
    binds = []
    if afsdirmount:
        volumes = ['/output']
        binds   = ['{}:/output'.format(afsdirmount)]

    try:
        c = docker.Client()
        container_id = c.create_container(
            image = container, command = command,
            stdin_open = True,
            tty = istty,
            volumes=volumes,
            host_config=c.create_host_config(binds=binds)
        )
        print "starting docker: container: {} command: {} mount: {} ".format(container,command, afsdirmount)

        c.start(container_id['Id'])
        print 'ID is {}'.format(container_id['Id'])
	return container_id
    except:
        print 'could not start container'
        raise RuntimeError

def handle_nontty(socket,container_id):
    print 'handling non tty docker session'

    while True:
        zr,zw,zx = zmq.select([socket], [socket],[socket], timeout = 0.0)

        if (socket in zr):
            message = socket.recv_json()
            print("Received request: {} length: {}".format(message,len(message)))
	    if 'ctrl' in message:
                if message['ctrl'] == 'terminate': break

    print "stop container"
    dockerclient = docker.Client()
    dockerclient.stop(container_id['Id'])
    print 'stopped'
    
    socket.send_json({'ctrl':'ack stopped'})
    return

def handle_tty(socket,container_id):
    print 'handling tty docker session'

    import pty
    import shlex
    master, slave = pty.openpty()

    p = subprocess.Popen(shlex.split('docker attach {}'.format(container_id['Id'])), stdin = slave, stdout = slave, stderr = slave)
    print 'attached to container with pid {}'.format(p.pid)

    term_size = socket.recv_json()['ctrl']['term_size']
    set_winsize(master,term_size['rows'],term_size['cols'],p.pid)

    while True:
        #print "polling"
        r, w, x = select.select([master],[master],[master], 0.0)
        #print "master poll: r: {} w: {} x: {}".format(r,w,x)

        zr,zw,zx = zmq.select([socket], [socket],[socket], timeout = 0.0)
        #print "ZMQ poll: r: {} w: {} x: {}".format(zr,zw,zx)

        procpoll = p.poll()
        #print 'process: {}'.format(procpoll)

        if (procpoll is not None) and (socket in zw):
	    print "ending session because process ended"
            socket.send_json({'ctrl':'terminated'})
	    print "return"
            return
        
    
        if (master in r) and (socket in zw):
            #print "reading!"
            fromprocess = os.read(master,1024)
            #print 'sending {}'.format(fromprocess)
            socket.send_json({'p':fromprocess})

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
		    if 'signal' in ctrlmsg:
 		        print 'got signal: {}'.format(ctrlmsg['signal']) 
			if ctrlmsg['signal'] in [signal.SIGHUP,signal.SIGTERM,signal.SIGKILL]:
                            print 'stopping container due to SIGHUP, SIGTERM, or SIGKILL'
			    os.kill(p.pid,ctrlmsg['signal'])
			    dockerclient = docker.Client()
			    dockerclient.stop(container_id['Id'])
			    print 'container stopped'
			else:
		            os.kill(p.pid,ctrlmsg['signal'])

            #print "wrote it"

    
#        time.sleep(0.001)

if __name__ == '__main__':
    start_server(5556, 'python:2.7', 'bash','/afs/cern.ch/user/l/lheinric/testafs')
#    start_server(5556, 'python:2.7', 'bash',None)
