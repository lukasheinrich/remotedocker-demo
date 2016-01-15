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

# HOST = 'lheinric-dockerinteractive'
# WEBSERVERHOST = 'localhost:3000'
# TUNNEL = True

HOST = 'localhost'
WEBSERVERHOST = 'localhost:5000'
TUNNEL = False


@click.command()
@click.argument('container')
@click.argument('command')
def client(container,command):
    context = zmq.Context()

    r = requests.get('http://{}/start?container={}&command={}'.format(WEBSERVERHOST,container,command))
    readfrom = r.json()['readfrom']

    click.secho('starting remote docker session', fg = 'green')

    #incoming messages
    socket = context.socket(zmq.PAIR)
    if TUNNEL:
        ssh.tunnel_connection(socket,'tcp://{}:{}'.format(HOST,readfrom),'lxplus')
    else:
        socket.connect('tcp://{}:{}'.format(HOST,readfrom))

    poller = zmq.Poller()
    poller.register(socket,zmq.POLLIN)
    sockets = [socket]

    socket.send('start')
    ack = socket.recv()


    click.secho('we\'ll be with you shortly...', fg = 'green')
    m = socket.recv()

    oldtty = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            r, w, x  = select.select([sys.stdin], [], [], 0.0)
            zr,zw,zx = zmq.select([socket],[socket],[], timeout = 0.0)

            if (sys.stdin in r) and (socket in zw):
                x = sys.stdin.read(1)
                socket.send(x)
                socket.recv()
        
            if (socket in zr):
                x = socket.recv()
                if len(x) == 0:
                    sys.stdout.write('\r\nexiting... \r\n')
                    break
                sys.stdout.write(x)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

    click.secho('Bye.', fg = 'green')
    

if __name__ == '__main__':
    client()
