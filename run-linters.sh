#!/bin/sh

echo "Running black"
black --target-version py38 .

echo "Running flake8"
flake8 --exclude .venv

echo "Running isort"
isort .
