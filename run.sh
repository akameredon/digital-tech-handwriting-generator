#!/bin/bash
# Quick start script for Digital Technologies Lesson Note Generator

echo "=============================================="
echo " Digital Technologies Lesson Note Generator"
echo " NERDC 2025 • SS1–SS3 • Production Ready"
echo "=============================================="
echo ""

cd "$(dirname "$0")"

# Create virtual environment if it does not exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing / updating dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Starting API server on http://127.0.0.1:8000"
echo "Open http://127.0.0.1:8000/docs for interactive documentation"
echo "Press Ctrl+C to stop"
echo ""

python main.py
