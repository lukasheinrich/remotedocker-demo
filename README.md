# remotedocker-demo

this is a proof-of-concept code for a remote interactive docker sessions for environments without a local docker installation and full access to a remote docker host. The client's TTY is connected to a `docker attach ...` process on the server via a ZeroMQ socket to a port that the server publishes. The client does not need to have any access to the machine running the server or the docker daemon, but just reads/writes to these ports.

On the server side, a webserver spawns interactive docker session for a specified container/command pair upon a corresponding HTTP request by the client.  the interactive docker session is connected to a pseudo-terminal which itself talks to ZeroMQ on random ports to interact with the remote client.

client code:

    remotedocker <container> <command>

since the demo machine is behind a cern firewall you need to setup a SSH tunnel to the webserver at 'localhost:3000', i.e. 
    ssh -fNL 3000:<demo-machine>:5000 lxplus

for the same reason the client will ask twice (for input and output) for the password for LXPLUS for now, but if the port range selected by the server (now: 5000,6000) should be accessible by the outside, this will not be needed. 

this is also more restrictive than completely exposing the docker unix socket to the outside world. this only allows the remote client to connect to a  'docker run -it <container> <command>' call and not to remove containers/images etc.

#### installing

    git clone https://github.com/lukasheinrich/remotedocker-demo.git
    cd remotedocker-demo
    pip install -e .

#### screencast

from outside CERN (tunneling via `lxplus`)
[![asciicast](https://asciinema.org/a/9kkugc45wlz16sdivm5e20h6s.png)](https://asciinema.org/a/9kkugc45wlz16sdivm5e20h6s)

from inside CERN
[![asciicast](https://asciinema.org/a/4n7bjiffdn393m9t746rf1y6s.png)](https://asciinema.org/a/4n7bjiffdn393m9t746rf1y6s)

