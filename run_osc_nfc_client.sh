#! /bin/bash

cd /home/nfc/nfc-osc-client/
source .venv/bin/activate
python3 ./nfc_osc_client.py --ip=10.0.0.10 --port=7777
