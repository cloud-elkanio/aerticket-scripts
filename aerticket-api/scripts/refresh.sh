#!/bin/bash
set -o pipefail
set -e

source ~/api/venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10
pip install -r ~/api/api/requirements.txt
export $(cat ~/api/api.env | xargs) && python ~/api/api/manage.py migrate
sudo systemctl restart api.service
