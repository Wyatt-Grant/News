# News Aggregator - Multi-Source RSS Scraper

A powerful Python-based news aggregator that scrapes articles from 11 different RSS feeds, deduplicates them using AI, and presents them in an interactive HTML dashboard or CSV export.

## Features

**Multi-Source Aggregation**:
- 11 diverse news sources:
  - Star Phoenix (Local news)
  - CBC News (World)
  - New York Times (World)
  - Smashing Magazine (Tech/Design)
  - Laravel News (Development)
  - Saskatoon Police (Local)
  - Thomson Reuters (Business/News)
  - BBC News (World)
  - Dow Jones (Market news)
  - The Hockey Writers (Sports)
  - ESPN NFL News (Sports)

**Intelligent Processing**:
- **Smart Content Extraction**: Removes ads, junk, paywall prompts, and newsletter signups
- **Article Deduplication**: Uses OpenAI to identify and remove duplicate stories across sources
- **Variety Optimization**: Reorders articles to mix sources while respecting chronological order
- **NLTK Summarization**: Generates journalistic lede-style summaries (first 3 sentences, ~60 words)
- **Quality Image Filtering**: Only includes images that are:
  - JPG or PNG format
  - At least 300×300 pixels
  - At least 10KB in size
  - Aspect ratio > 1.1 (filters logos/icons)

**Multiple Export Formats**:
- **Interactive HTML**: Beautiful Tailwind CSS UI with modals, filtering, and responsive design
- **CSV Export**: Complete article data with links and metadata
- **Source-Specific Badges**: Color-coded badges for each news source

## Installation

### 1. Clone or download this repository

### 2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies:
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables (optional):
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo
```

> **Note**: OpenAI API is optional. The scraper works without it but won't deduplicate articles or use AI-powered summaries. Deduplication requires `OPENAI_API_KEY` to be set.

## Usage

### Activate virtual environment:
```bash
source venv/bin/activate
```

### Scrape all sources (2 articles each):
```bash
python scraper.py -m 2
```

### Scrape specific sources:
```bash
python scraper.py -m 5 -s star_phoenix cbc bbc
```

### Custom output directory:
```bash
python scraper.py -m 3 -o my_news -s nyt bbc espn_nfl
```

### Available sources:
```
star_phoenix, cbc, nyt, smashing, laravel, saskatoon_police,
thomson_reuters, bbc, dow_jones, hockey_writers, espn_nfl
```

## Output

The script creates:
```
articles/                    # Default output directory
├── articles.csv            # All articles in CSV format
├── articles.html           # Interactive dashboard (view in browser)
└── images/                 # Downloaded article images
    ├── image1.jpg
    ├── image2.jpg
    └── ...
```

## Viewing Results

### HTML Dashboard:
```bash
open articles/articles.html
```

The HTML file includes:
- Grid layout with article cards
- Color-coded source badges
- Click-to-expand modals with full article content
- Article images
- Sorting by date (newest first)
- Search-friendly structure

### CSV File:
Open `articles.csv` in Excel, Google Sheets, or your preferred spreadsheet tool.

## GitHub Pages Setup

To host your news dashboard on GitHub Pages:

### 1. Commit and push to GitHub:
```bash
git add .
git commit -m "Initial commit: news aggregator"
git push origin main
```

### 2. Generate your first articles:
```bash
source venv/bin/activate
python scraper.py -m 5 -o docs
```

This creates articles in the `docs/` folder (which GitHub Pages serves).

### 3. Enable GitHub Pages:
- Go to your repository on GitHub
- Settings → Pages
- Select "Deploy from branch"
- Choose "main" branch, "/docs" folder
- Save

### 4. Access your dashboard:
```
https://YOUR_USERNAME.github.io/news-scaper/
```

### 5. Update regularly:
```bash
source venv/bin/activate
python scraper.py -m 5 -o docs
git add docs/
git commit -m "Updated articles"
git push
```

## Configuration

### Environment Variables:
- `OPENAI_API_KEY`: Your OpenAI API key for deduplication and AI summaries
- `OPENAI_MODEL`: OpenAI model to use (default: `gpt-3.5-turbo`)

### Command-line Arguments:
- `-m`, `--max`: Maximum articles per source (default: unlimited)
- `-o`, `--output`: Output directory (default: `articles`)
- `-s`, `--sources`: Specific sources to scrape (default: all)

## How It Works

1. **Fetch**: Downloads RSS feeds from all selected sources
2. **Scrape**: Extracts article content from each source's webpage
3. **Clean**: Removes ads, popups, paywall text, and junk content
4. **Summarize**: Generates concise summaries using NLTK or OpenAI
5. **Deduplicate**: Uses OpenAI to identify and remove duplicate stories
6. **Reorder**: Shuffles articles in time windows for natural variety
7. **Export**: Generates HTML dashboard, CSV file, and downloads images

## Performance Notes

- Default 2-second delay between requests (respects server limits)
- Up to 3 images downloaded per article
- Deduplication happens after scraping but before export
- Total runtime: ~1-5 minutes depending on article count and network

## Troubleshooting

**OpenAI errors**: Make sure `OPENAI_API_KEY` is set in your `.env` file. Without it, the script still works but skips AI features.

**Access blocked (403)**: Some sites have anti-scraping protection. Try adding delays or different headers.

**Image download failures**: The script skips failed images and continues scraping.

**Encoding errors**: Make sure your terminal uses UTF-8 encoding.

## License

MIT

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
