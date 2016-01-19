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

    cmd, cidfile = docker_command(container,command,afsdirmount,istty)
    if istty:
        handle_tty(cmd, cidfile, socket)
    else:
        handle_nontty(cmd, cidfile, socket)
        
def docker_command(container,command,afsdirmount,istty):
    readstdin = True

    import tempfile
    f = tempfile.NamedTemporaryFile()
    f.close()
    cidfile = f.name

    print 'cidfile is: {}'.format(cidfile)

    cmd = 'docker run --cidfile {}'.format(cidfile)
    if readstdin:
        cmd += ' -i'
    if istty:
        cmd += ' -t'
    if afsdirmount:
        cmd += ' -v {}:/output'.format(afsdirmount)

    cmd += ' {} {}'.format(container,command)    

    import shlex
    print 'command is {}'.format(cmd)
    return cmd, cidfile

def stop_container(container_id):
    print 'stopping container with id {}'.format(container_id)
    dockerclient = docker.Client()
    dockerclient.stop(container_id)
    print 'container stopped'

def get_container_id(cid):
    while not os.path.exists(cid) or (os.stat(cid).st_size == 0):
        time.sleep(0.01)
    container_id = open(cid).read()
    return container_id
    


def handle_nontty(cmd,cid,socket):
    print 'handling non tty docker session'

    import shlex
    p = subprocess.Popen(shlex.split(cmd), stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    print 'started container with pid: {}'.format(p.pid)

    while True:
        if p.poll() is not None:
            print "ending session because process ended"
            socket.send_json({'ctrl':'terminated'})
            print 'wait for ack from client'
            ack = socket.recv_json()
            print "return"
            return

        writefds = []
        if not p.stdin.closed:
            writefds.append(p.stdin)

        r,w,x = select.select([p.stdout],writefds,[],0.0)
        zr,zw,zx = zmq.select([socket], [socket],[socket], timeout = 0.0)
        if (socket in zr) and (p.stdin in w):
            message = socket.recv_json()
            try:
                if message['p'] == '':
                    print 'EOF of input'
                    p.stdin.close()
                else:
                    p.stdin.write(message['p'])
            except KeyError:
		if 'ctrl' in message:
		    ctrlmsg = message['ctrl']
                    if 'signal' in ctrlmsg:
                        print 'got signal: {}'.format(ctrlmsg['signal'])
                        os.kill(p.pid,ctrlmsg['signal'])
			if ctrlmsg['signal'] in [signal.SIGHUP,signal.SIGTERM,signal.SIGKILL]:
			    stop_container(get_container_id())
                            return
        if (p.stdout in r) and (socket in zw):
            x = os.read(p.stdout.fileno(),1024)
            socket.send_json({'p':x})

    print 'read reamining stdout buffer'
    for x in  p.stdout.readlines():
        socket.send_json({'p':x}) 
    return

def handle_tty(cmd,cid,socket):
    print 'handling tty docker session'

    import pty
    import shlex
    master, slave = pty.openpty()

    p = subprocess.Popen(shlex.split(cmd), stdin = slave, stdout = slave, stderr = slave)
    print 'started container with pid: {}'.format(p.pid)

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
            print 'wait for ack from client'    
	    ack = socket.recv_json()
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
                        os.kill(p.pid,ctrlmsg['signal'])
			if ctrlmsg['signal'] in [signal.SIGHUP,signal.SIGTERM,signal.SIGKILL]:
                            stop_container(get_container_id(cid))
                            return
            #print "wrote it"

    
#        time.sleep(0.001)

if __name__ == '__main__':
    start_server(5556, 'python:2.7', 'bash','/afs/cern.ch/user/l/lheinric/testafs')
#    start_server(5556, 'python:2.7', 'bash',None)
