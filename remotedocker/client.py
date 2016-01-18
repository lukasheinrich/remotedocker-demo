#!/usr/bin/env pythonread

import select
import termios
import sys
import tty
import time
import zmq
import time
import requests
import click
import os
import struct
import fcntl
import signal

from zmq import ssh

@click.command()
@click.argument('container')
@click.argument('command')
@click.option('-o','--output',default = None)
@click.option('--tunnel/--no-tunnel',default = False)
def client(container,command,output,tunnel):
    context = zmq.Context()
    
    if tunnel:
        ssh.tunnel.openssh_tunnel(6000,6000,'lxplus','lheinric-dockerinteractive')
        webhost = 'localhost'
    else:
        webhost = 'lheinric-dockerinteractive'

    url  = 'http://{0}:6000/start?'.format(webhost)
    parameters = []
    parameters.append('container={0}'.format(container))
    parameters.append('command={0}'.format(command))
    if output:
        parameters.append('afsdirmount={0}'.format(output))

    url = url + '&'.join(parameters)
 

    r = requests.get(url)
    if not r.ok:
        e =  click.ClickException(message = click.style('sorry, there is no spot available on the server', fg = 'red'))
        e.exit_code = 1
        raise e
    readfrom = r.json()['readfrom']
    
    click.secho('starting remote docker session', fg = 'green')

    #incoming messages
    socket = context.socket(zmq.PAIR)
    if tunnel:
        ssh.tunnel_connection(socket,'tcp://lheinric-dockerinteractive:{0}'.format(readfrom),'lxplus')
    else:
        socket.connect("tcp://lheinric-dockerinteractive:{0}".format(readfrom))

    poller = zmq.Poller()
    poller.register(socket,zmq.POLLIN)
    sockets = [socket]

    socket.send_json({'ctrl':'start'})
    ack = socket.recv()

    istty = os.isatty(sys.stdin.fileno())
    
    socket.send_json({'ctrl':{'tty':istty}})
    
    if istty:
        handle_tty(socket)
    else:
        handle_nontty(socket)

    click.secho('Bye.', fg = 'green')

def terminal_size():
    # Check for buggy platforms (see pexpect.setwinsize()).
    if 'TIOCGWINSZ' in dir(termios):
        TIOCGWINSZ = termios.TIOCGWINSZ
    else:
        TIOCGWINSZ = 1074295912 # assume

    s = struct.pack ("HHHH", 0, 0, 0, 0)
    rows, cols, _, _ = struct.unpack ('HHHH', fcntl.ioctl(sys.stdout.fileno(), TIOCGWINSZ , s))
    return rows, cols


def get_sigwinch_handler(socket):
    def handler(sig,data):
        rows,cols = terminal_size()
        socket.send_json({'ctrl':{'term_size':{'rows':rows, 'cols':cols}}})
    return handler

def get_sigint_handler(socket):
    def handler(sig,data):
        socket.send_json({'ctrl':{'signal':signal.SIGINT}})
    return handler

def get_sighup_handler(socket):
    def handler(sig,data):
        socket.send_json({'ctrl':{'signal':signal.SIGHUP}})
    return handler

def handle_nontty(socket):
    click.echo('non TTY mode')
    socket.send_json({'ctrl':'nonttystart'})
    m = socket.recv_json()
    print 'received ack {0}'.format(m)
    return

def handle_tty(socket):
    click.secho('we\'ll be with you shortly...', fg = 'green')

    rows,cols = terminal_size()
    socket.send_json({'ctrl':{'term_size':{'rows':rows, 'cols':cols}}})

    signal.signal(signal.SIGWINCH, get_sigwinch_handler(socket))
    signal.signal(signal.SIGINT, get_sigint_handler(socket))
    signal.signal(signal.SIGHUP, get_sighup_handler(socket))
    oldtty = termios.tcgetattr(sys.stdin)

    try:
        # Add O_NONBLOCK to the stdin descriptor flags 
        # flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        # fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        while True:
            try:
                r, w, x  = select.select([sys.stdin], [sys.stdout], [], 0.0)
            except select.error:
                pass
            zr,zw,zx = zmq.select([socket],[socket],[], timeout = 0.0)
            
            if (sys.stdin in r) and (socket in zw):
                x = sys.stdin.read(1)
                socket.send_json({'p':x})
        
            if (socket in zr) and (sys.stdout in w):
                x = socket.recv_json()
	        try:
                    plain = x['p']
                    sys.stdout.write(plain)
                    while True:
                        r, w, x  = select.select([], [sys.stdout], [], 0.0)
                        if sys.stdout in w:
                            sys.stdout.flush()
                            break
                except KeyError:
                    if 'ctrl' in x:
                        ctrlmsg = x['ctrl']
                        if 'terminated' in ctrlmsg:
                            sys.stdout.write('\r\nexiting... \r\n')
                            break
    except:
        click.secho('uncaught exception.. terminating', fg = 'red')
	socket.send_json({'ctrl':{'signal':signal.SIGQUIT}})
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)


    

if __name__ == '__main__':
    client()
