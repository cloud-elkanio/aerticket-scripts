FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y build-essential python3-dev \
     wget curl gnupg2 libpq-dev \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt \
  && rm -rf /requirements.txt

COPY . /app
WORKDIR /app

EXPOSE 8000