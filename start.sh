#!/bin/bash

# iniciar scheduler en background
python scheduler.py &

# iniciar API en foreground
uvicorn api:app --host 0.0.0.0 --port 10000
