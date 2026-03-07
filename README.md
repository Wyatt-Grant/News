# Star Phoenix RSS Feed Scraper

A Python script that scrapes articles from the Star Phoenix RSS feed, extracts content, and generates a CSV file with article metadata.

## Features

- **RSS Feed Parsing**: Fetches articles from the Star Phoenix RSS feed
- **Content Extraction**: Scrapes article content while removing ads and junk elements
- **Smart Image Downloading**: Downloads article images with intelligent filtering:
  - Only JPG and PNG formats
  - Minimum file size: 10KB (filters out tiny icons)
  - Minimum dimensions: 200x200 pixels
  - Filters out nearly-square images (likely logos/icons)
- **CSV Export**: Generates a CSV file with article data:
  - Article title
  - Publication date
  - Author
  - Article URL
  - Article content (cleaned)
  - Local image paths

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage
First activate the virtual environment:
```bash
source venv/bin/activate
```

Then scrape all available articles:
```bash
python scraper.py
```

### Limit Number of Articles
Make sure the virtual environment is activated, then scrape only the first 10 articles:
```bash
python scraper.py -m 10
```

### Custom Output Directory
Save results to a custom directory:
```bash
python scraper.py -o my_articles
```

### Combined Options
```bash
python scraper.py -m 20 -o my_articles
```

## Output

The script creates the following structure:
```
articles/
├── articles.csv          # CSV file with article metadata
└── images/              # Downloaded article images
    ├── image1.jpg
    ├── image2.jpg
    └── ...
```

## CSV Format

The generated `articles.csv` contains the following columns:
- **Title**: Article headline
- **Date**: Publication date
- **Author**: Article author
- **URL**: Original article URL
- **Content**: Main article content (cleaned)
- **Image_URLs**: Paths to downloaded images (separated by |)

## Notes

- The script includes a 2-second delay between requests to be respectful to the server
- Content is limited to 5000 characters per article
- Up to 3 images are downloaded per article (with quality filters)
- **Image filtering**:
  - Only JPG and PNG files are saved
  - Images must be at least 10KB
  - Images must be at least 200x200 pixels
  - Nearly square images (aspect ratio < 1.1) are skipped to avoid logos/icons
- The script handles errors gracefully and logs progress
- HTML elements like ads, sidebars, and comments are automatically removed

## Logging

The script provides detailed logging output showing:
- Articles found in the feed
- Progress of each article being scraped
- Image downloads
- Any errors encountered

## Requirements

- Python 3.7+
- Internet connection
- Write access to create output directories

## Virtual Environment

Always remember to activate the virtual environment before running the script:
```bash
source venv/bin/activate
```

To deactivate when done:
```bash
deactivate
```
