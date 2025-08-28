#!/bin/bash
set -o pipefail
set -e

source ~/booking/venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10
pip install -r ~/booking/eth-booking/requirements.txt
export $(cat ~/booking/booking.env | xargs)
sudo systemctl restart booking.service