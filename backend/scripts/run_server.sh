#!/bin/bash
echo "Starting backend service..."
cd "$(dirname "$0")/.."
python main.py
