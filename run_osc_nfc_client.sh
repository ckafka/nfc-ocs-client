#! /bin/bash

cd /home/eldermother/nfc_controller/nfc-ocs-client/
source .venv/bin/activate
python ./nfc_osc_client.py --ip=192.168.0.11 --port=7777