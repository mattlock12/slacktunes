FROM python:3.7-slim

RUN apt-get update
RUN apt-get -y install gcc libpq-dev python-dev

COPY requirements.txt .

RUN pip install -r ./requirements.txt

WORKDIR /app

COPY . .

EXPOSE 8000