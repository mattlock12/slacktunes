FROM python:3.7-slim
RUN apt-get update
RUN apt-get -y install gcc
COPY . /app/
WORKDIR /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt