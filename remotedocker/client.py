#!/usr/bin/env python

import select
import termios
import sys
import tty
import time
import zmq
import time
import requests
import click
from zmq import ssh

@click.command()
@click.argument('container')
@click.argument('command')
def client(container,command):
    context = zmq.Context()

    r = requests.get('http://lheinric-dockerinteractive:6000/start?container={0}&command={1}'.format(container,command))
    if not r.ok:
        e =  click.ClickException(message = click.style('sorry, there is no spot available on the server', fg = 'red'))
        e.exit_code = 1
        raise e

    readfrom = r.json()['readfrom']
    
    click.secho('starting remote docker session', fg = 'green')

    #incoming messages
    socket = context.socket(zmq.PAIR)
    socket.connect("tcp://lheinric-dockerinteractive:{0}".format(readfrom))
    # ssh.tunnel_connection(sub_socket,'tcp://lheinric-dockerinteractive:{0}'.format(readfrom),'lxplus')

    poller = zmq.Poller()
    poller.register(socket,zmq.POLLIN)
    sockets = [socket]

    socket.send('start')
    ack = socket.recv()


    click.secho('we\'ll be with you shortly...', fg = 'green')

    m = socket.recv()

    oldtty = termios.tcgetattr(sys.stdin)

    try:
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        while True:
            r, w, x  = select.select([sys.stdin], [], [], 0.0)
            zr,zw,zx = zmq.select(sockets,sockets,[], timeout = 0.0)

            if (sys.stdin in r) and (socket in zw):
                x = sys.stdin.read(1)
                socket.send(x)
        
            if (socket in zr):
                x = socket.recv()
                if len(x) == 0:
                    sys.stdout.write('\r\nexiting... \r\n')
		    socket.send('bye from client')
                    break
                sys.stdout.write(x)
                sys.stdout.flush()
            # time.sleep(0.0001)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

    click.secho('Bye.', fg = 'green')
    

if __name__ == '__main__':
    client()
