#!/bin/sh

echo "Checking black"
black --target-version py38 --check --diff .

echo "Checking flake8"
flake8 --exclude .venv

echo "Checking isort"
isort --check-only --diff .
