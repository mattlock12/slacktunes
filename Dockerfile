FROM python:3.7-slim
RUN apt-get update
RUN apt-get -y install gcc libpq-dev python-dev
RUN mkdir /app
RUN mkdir /etc/nginx/
COPY . /app/
WORKDIR /app
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt