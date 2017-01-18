FROM python:2.7
ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt
RUN curl https://get.docker.com/builds/Linux/x86_64/docker-1.9.1  -o /usr/bin/docker && chmod +x /usr/bin/docker
