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

    r = requests.get('http://localhost:3000/start?container={}&command={}'.format(container,command))
    readfrom, writeto = r.json()['readfrom'],r.json()['writeto']

    click.secho('starting remote docker session', fg = 'green')

    #incoming messages
    sub_socket = context.socket(zmq.SUB)
    # sub_socket.("tcp://localhost:{}".format(readfrom))
    ssh.tunnel_connection(sub_socket,'tcp://lheinric-dockerinteractive:{}'.format(readfrom),'lxplus')
    sub_socket.setsockopt(zmq.SUBSCRIBE,'')

    #outgoing messages
    pub_socket = context.socket(zmq.REQ)
    # pub_socket.connect("tcp://localhost:{}".format(writeto))
    ssh.tunnel_connection(pub_socket,'tcp://lheinric-dockerinteractive:{}'.format(writeto),'lxplus')

    poller = zmq.Poller()
    poller.register(sub_socket,zmq.POLLIN)
    poller.register(pub_socket,zmq.POLLIN)
    sockets = [pub_socket,sub_socket]

    pub_socket.send('start')
    ack = pub_socket.recv()


    click.secho('we\'ll be with you shortly...', fg = 'green')
    m = sub_socket.recv()

    oldtty = termios.tcgetattr(sys.stdin)

    try:
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        while True:
            r, w, x  = select.select([sys.stdin], [], [], 0.0)
            zr,zw,zx = zmq.select([sub_socket],[pub_socket],[], timeout = 0.0)

            if (sys.stdin in r) and (pub_socket in zw):
                x = sys.stdin.read(1)
                pub_socket.send(x)
                pub_socket.recv()
        
            if (sub_socket in zr):
                x = sub_socket.recv()
                if len(x) == 0:
                    sys.stdout.write('\r\nexiting... \r\n')
                    break
                sys.stdout.write(x)
                sys.stdout.flush()
            # time.sleep(0.0001)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

    click.secho('Bye.', fg = 'green')
    

if __name__ == '__main__':
    client()