FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     build-essential python3-dev \
     wget curl gnupg2 libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt \
  && rm -rf /requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

EXPOSE 8000
