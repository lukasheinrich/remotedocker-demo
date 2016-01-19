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
    # readfrom = 5556
    
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
    
    signal.signal(signal.SIGWINCH, get_sigwinch_handler(socket))
    signal.signal(signal.SIGINT, get_sigint_handler(socket))
    signal.signal(signal.SIGHUP, get_sighup_handler(socket))
    signal.signal(signal.SIGTERM, get_sigterm_handler(socket))
    
    if istty:
        handle_tty(socket)
    else:
        handle_nontty(socket)

    click.secho('Bye.', fg = 'green')
    sys.exit(0)
    return

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
        print "caught winch"
        rows,cols = terminal_size()
        socket.send_json({'ctrl':{'term_size':{'rows':rows, 'cols':cols}}})
        sys.exit(0)
    return handler

def get_sigint_handler(socket):
    def handler(sig,data):
        print "caught int"
        socket.send_json({'ctrl':{'signal':signal.SIGINT}})
        time.sleep(1)
        raise RuntimeError('terminated due to handled signa')
    return handler

def get_sighup_handler(socket):
    def handler(sig,data):
        print "caught hup"
        socket.send_json({'ctrl':{'signal':signal.SIGHUP}})
        time.sleep(1)
        raise RuntimeError('terminated due to handled signa')
    return handler

def get_sigterm_handler(socket):
    def handler(sig,data):
        print "caught term"
        socket.send_json({'ctrl':{'signal':signal.SIGTERM}})
        time.sleep(1)
        raise RuntimeError('terminated due to handled signa')
    return handler

def handle_uncaught_exception(socket):
    click.secho('uncaught exception.. terminating', fg = 'red')
    socket.send_json({'ctrl':{'signal':signal.SIGTERM}})
    time.sleep(1)
    print sys.exc_info()
    click.secho('signal sent.', fg = 'red')
    click.Abort()
    
def handle_nontty(socket):
    click.echo('non TTY mode')
    try:
        while True:
            s = read_write_nontty(socket)
            if s > 0: break
    except RuntimeError as e:
        click.secho('exception {}'.format(e))
        click.Abort()
    except:
        handle_uncaught_exception(socket)
    finally:
        pass
    return

def handle_tty(socket):
    try:
        click.secho('we\'ll be with you shortly...', fg = 'green')
        rows,cols = terminal_size()
        socket.send_json({'ctrl':{'term_size':{'rows':rows, 'cols':cols}}})
    
        oldtty = termios.tcgetattr(sys.stdin)
        # Add O_NONBLOCK to the stdin descriptor flags 
        # flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        # fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        while True:
            s = read_write(socket)
            if s > 0: break
    except:
        handle_uncaught_exception(socket)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

def read_write(socket):
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
                    socket.send_json({'ctrl':'terminated'})
                    return 1
    return 0

def read_write_nontty(socket):
    EOF_reached = False
    try:
        r, w, x  = select.select([sys.stdin], [sys.stdout], [], 0.0)
    except select.error:
        pass
    zr,zw,zx = zmq.select([socket],[socket],[], timeout = 0.0)

    if (sys.stdin in r) and (socket in zw):
        x = sys.stdin.readline()
        if not EOF_reached:
            socket.send_json({'p':x})
        if x == '':
            EOF_reached = True

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
                    socket.send_json({'ctrl':'terminated'})
                    return 1
    return 0

if __name__ == '__main__':
    client()
