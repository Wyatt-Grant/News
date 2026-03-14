#!/bin/bash

# Run scraper
python scraper.py -m 3

# Add all files to git
git add .

# Commit with message
git commit -m "new"

# Push to remote
git push
