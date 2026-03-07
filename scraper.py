#!/usr/bin/env python3
"""
Star Phoenix RSS Feed Scraper
Scrapes articles from Star Phoenix RSS feed, extracts content, and exports to CSV
"""

import feedparser
import requests
import csv
import json
import os
import time
import signal
import re
import shutil
import random
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define RSS sources
SOURCES = {
    'star_phoenix': {
        'name': 'Star Phoenix',
        'url': 'http://thestarphoenix.com/feed'
    },
    'cbc': {
        'name': 'CBC News - World',
        'url': 'https://www.cbc.ca/webfeed/rss/rss-world'
    },
    'nyt': {
        'name': 'New York Times - World',
        'url': 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml'
    },
    'smashing': {
        'name': 'Smashing Magazine',
        'url': 'https://www.smashingmagazine.com/feed'
    },
    'laravel': {
        'name': 'Laravel News',
        'url': 'http://laravel-news.com/feed'
    },
    'saskatoon_police': {
        'name': 'Saskatoon Police News',
        'url': 'https://saskatoonpolice.ca/rss/news/'
    },
    'bbc': {
        'name': 'BBC News - World',
        'url': 'https://feeds.bbci.co.uk/news/world/rss.xml'
    },
    'nasdaq_tech': {
        'name': 'Nasdaq - Technology',
        'url': 'https://www.nasdaq.com/feed/rssoutbound?category=Technology'
    },
    'nasdaq_original': {
        'name': 'Nasdaq - Original',
        'url': 'https://www.nasdaq.com/feed/nasdaq-original/rss.xml'
    },
    'techcrunch': {
        'name': 'TechCrunch',
        'url': 'https://techcrunch.com/feed/'
    },
    'polygon': {
        'name': 'Polygon',
        'url': 'https://www.polygon.com/feed/'
    },
    'filmjabber': {
        'name': 'Film Jabber',
        'url': 'https://www.filmjabber.com/rss/rss-current.php'
    },
    'politico': {
        'name': 'Politico - Picks',
        'url': 'http://www.politico.com/rss/politicopicks.xml'
    },
    'hockey_writers': {
        'name': 'The Hockey Writers',
        'url': 'https://thehockeywriters.com/feed'
    },
    'espn_nfl': {
        'name': 'ESPN NFL News',
        'url': 'https://www.espn.com/espn/rss/nfl/news?null'
    },
    'xxlhiphop': {
        'name': 'XXL Hip Hop',
        'url': 'https://www.xxlmag.com/feed/'
    }
}


class RSSNewsScraper:
    def __init__(self, source_key, output_dir='docs'):
        if source_key not in SOURCES:
            raise ValueError(f"Unknown source: {source_key}. Available sources: {list(SOURCES.keys())}")
        
        self.source_key = source_key
        self.source_name = SOURCES[source_key]['name']
        self.rss_url = SOURCES[source_key]['url']
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, 'images')
        self.articles = []
        self.image_counter = 0  # Counter for sequential image IDs
        
        # OpenAI Configuration
        self.openai_enabled = False
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                self.openai_enabled = True
                logger.info(f"✓ OpenAI API enabled (using {self.openai_model})")
            except Exception as e:
                logger.warning(f"OpenAI initialization failed: {e}. Using local summarization.")
        else:
            logger.info("OPENAI_API_KEY not set. Using local summarization.")
        
        # Create output directories
        os.makedirs(self.images_dir, exist_ok=True)
        
        # Headers to avoid being blocked
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def fetch_rss_feed(self):
        """Fetch and parse the RSS feed"""
        try:
            logger.info(f"Fetching RSS feed from {self.rss_url}")
            
            # Fetch the feed with a timeout
            response = requests.get(self.rss_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            logger.info("RSS feed downloaded, parsing entries...")
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"RSS feed parsing warning: {feed.bozo_exception}")
            
            logger.info(f"Found {len(feed.entries)} articles in feed")
            return feed.entries
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching RSS feed from {self.rss_url}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
            return []
    
    def download_image(self, image_url, article_title):
        """Download image and return local path"""
        if not image_url:
            return None
        
        try:
            response = requests.get(image_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Check file size (skip if less than 10KB)
            if len(response.content) < 10240:
                logger.debug(f"Skipped small image {image_url} ({len(response.content)} bytes)")
                return None
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            parsed_url = urlparse(image_url)
            filename = os.path.basename(parsed_url.path)
            
            # Only allow jpg, png, avif, and webp
            allowed_extensions = ('.jpg', '.jpeg', '.png', '.avif', '.webp')
            file_ext = os.path.splitext(filename)[1].lower()
            
            # Validate based on content-type and extension
            if not file_ext:
                if 'jpeg' in content_type or 'jpg' in content_type:
                    file_ext = '.jpg'
                elif 'png' in content_type:
                    file_ext = '.png'
                elif 'avif' in content_type:
                    file_ext = '.avif'
                else:
                    # Try to detect from magic bytes (file signature) as fallback
                    magic_bytes = response.content[:12]
                    if magic_bytes.startswith(b'\xff\xd8\xff'):  # JPEG
                        file_ext = '.jpg'
                    elif magic_bytes.startswith(b'\x89PNG'):  # PNG
                        file_ext = '.png'
                    elif b'ftyp' in magic_bytes[:12] and b'avif' in response.content[:32]:  # AVIF
                        file_ext = '.avif'
                    elif magic_bytes.startswith(b'RIFF') and b'WEBP' in response.content[8:12]:  # WEBP
                        file_ext = '.webp'
                    else:
                        logger.debug(f"Skipped unidentified image file: {image_url}")
                        return None
            
            if file_ext not in allowed_extensions:
                logger.debug(f"Skipped non-jpg/png/avif image: {filename}")
                return None
            
            # Validate image dimensions to avoid icons
            width, height = None, None
            validation_skipped = False
            try:
                from PIL import Image
                from io import BytesIO
                img = Image.open(BytesIO(response.content))
                width, height = img.size
                
                # Skip images that are too small (likely icons)
                if width < 200 or height < 200:
                    logger.debug(f"Skipped small image dimensions {width}x{height}: {image_url}")
                    return None
                
                # Skip very square images (likely icons/logos)
                aspect_ratio = max(width, height) / min(width, height)
                if aspect_ratio < 1.1:  # Nearly square
                    logger.debug(f"Skipped square image (likely icon): {image_url}")
                    return None
            except Exception as e:
                # For formats like AVIF that PIL might not support, skip validation
                if file_ext == '.avif':
                    logger.debug(f"Skipping dimension validation for AVIF file (PIL may not support): {e}")
                    validation_skipped = True
                else:
                    logger.debug(f"Could not validate image dimensions: {e}")
                    return None
            
            # Create valid filename using source key and sequential ID
            self.image_counter += 1
            filename = f"{self.source_key}_{self.image_counter}{file_ext}"
            file_path = os.path.join(self.images_dir, filename)
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # Log with dimensions if available, otherwise note validation was skipped
            size_kb = len(response.content)/1024
            if width and height:
                logger.info(f"✓ Downloaded image: {self.source_key}_{self.image_counter}{file_ext} ({size_kb:.1f}KB, {width}x{height})")
            elif validation_skipped:
                logger.info(f"✓ Downloaded image: {self.source_key}_{self.image_counter}{file_ext} ({size_kb:.1f}KB, AVIF - validation skipped)")
            else:
                logger.info(f"✓ Downloaded image: {self.source_key}_{self.image_counter}{file_ext} ({size_kb:.1f}KB)")
            return file_path
            return file_path
        except Exception as e:
            logger.debug(f"Error downloading image {image_url}: {e}")
            return None
    


    def clean_content(self, html_content):
        """Clean and extract main content from HTML, preserving paragraph breaks"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Remove common ad/junk elements
        junk_selectors = [
            'script', 'style', 'nav', 'aside', '.ad', '.advertisement',
            '.sidebar', '.related-articles', '.comments', '.social-share',
            '.tags', '.newsletter-signup', '.paywall', '[data-ad-slot]',
            '.sign-in', '.login', '.register', '.modal', '.popup',
            'footer', '.footer', '.header', 'header'
        ]
        
        for selector in junk_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Try to find main content area
        main_content = None
        for selector in ['article', '.article-content', '.post-content', 'main', '.content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            # Extract content while preserving structure
            content_parts = []
            
            # Process block-level elements to preserve breaks
            for element in main_content.children:
                if isinstance(element, str):
                    text = element.strip()
                    if text:
                        content_parts.append(text)
                elif element.name in ['p', 'div', 'section', 'article', 'li', 'blockquote']:
                    text = element.get_text(strip=True)
                    if text:
                        content_parts.append(text)
                elif element.name == 'h1' or element.name == 'h2' or element.name == 'h3':
                    # Include headings as they mark section breaks
                    text = element.get_text(strip=True)
                    if text and len(text) > 5:  # Skip very short headings
                        content_parts.append(text)
                elif element.name in ['ul', 'ol']:
                    # Extract list items as separate paragraphs
                    for li in element.find_all('li'):
                        text = li.get_text(strip=True)
                        if text:
                            content_parts.append(text)
            
            # Join with double newlines (paragraph breaks)
            content = '\n\n'.join(content_parts)
        else:
            content = soup.get_text()
        
        # Clean the extracted content
        content = self.filter_garbage_text(content)
        return content
    
    def filter_garbage_text(self, content):
        """Remove common garbage text patterns"""
        # Common junk patterns to remove
        junk_patterns = [
            # Sign-in/Account prompts
            r'create an account.*?continue',
            r'sign in.*?continue',
            r'sign in.*?reading',
            r'subscribe.*?get access',
            r'get unlimited access',
            r'start your.*?subscription',
            r'become a member',
            r'log in.*?account',
            r'please log in',
            r'you must.*?to read',
            r'this.*?requires.*?subscription',
            r'paywall',
            r'already have an account',
            r'forgot password',
            r'remember me',
            
            # Newsletter signup prompts
            r'get the latest headlines.*?columns',
            r'by signing up you consent.*?postmedia',
            r'a welcome email is on its way.*?junk folder',
            r'the next issue.*?will soon be in your inbox',
            r'we encountered an issue signing you up',
            r'interested in more newsletters.*?browse here',
            r'get.*?breaking news.*?columns',
            
            # Promotional/advertising text
            r'the saskatoon star phoenix has created.*?subscribe',
            r'with some online platforms blocking access.*?keep you informed',
            r'so make sure to bookmark.*?sign up for our newsletters',
            r'our website is your destination.*?up to date',
            r'bookmark.*?and sign up for',
            r'click.*?to subscribe',
            r'clickhere',
            r'click here',
            
            # Community guidelines/policy
            r'postmedia is committed.*?community guidelines',
            r'please keep comments relevant',
            r'comments may take up to.*?appear on the site',
            r'you will receive an email if there is a reply',
            r'visit our.*?guidelines',
            r'visit ourCommunity',
            
            # Standard policy text
            r'by continuing.*?agree',
            r'terms of service',
            r'privacy policy',
            r'cookie policy',
            r'consent.*?newsletter',
            
            # Leftover fragments and orphaned text
            r'network inc\.',
            r'\. please try again',
            r'for more information\.',
            r'browse here',
            r'click here to subscribe',
            
            # Website references and embedded links
            r'learn more at\s*[\w./-]+',
            r'learn more at\w+\.\w+',
            r'visit\s*[\w./-]+',
            r'check out\s*[\w./-]+',
            r'see\s*[\w./-]+',
            r'go to\s*[\w./-]+',
            
            # Comments and discussion sections
            r'comments\s+you must be logged in',
            r'you must be logged in.*?discussion',
            r'create an account.*?conversation',
            r'join the conversation',
            r'read more comments',
            r'must be logged in',
            
            # Featured/promoted content
            r'featured.*?local savings',
            r'featured local',
            r'local savings',
            
            # Sign in / view offers
            r'sign in or.*?view more offers',
            r'sign in or',
            r'view more offers',
            
            # Read more links (these are internal article links with titles)
            r'read more[\'"].*?(?:hubskies|national|titles|poll|local news)',
            r'read more.*?thomaidis',
            r'read more.*?huskies',
            
            # Trending/sidebar sections
            r'trending\s+.*?local news',
            r'trending\s+carney approval.*?georgeward pool',
            r'complex repairs needed.*?media',
            r'local news.*?despite off-night',
            r'future community corridor.*?local news',
            
            # Newsletter signup errors
            r'afternoon headlines\.there was an error.*?thanks for signing up',
            r'there was an error.*?valid email',
            r'thanks for signing up.*?\.…',
            
            # Video/media placeholders
            r'we apologize.*?video.*?failed to load',
            r'try refreshing your browser.*?videos from our team',
            r'this video has failed to load',
            
            # CMS formatting artifacts
            r'article content',
            r'article\s+content',
            
            # Additional garbage patterns
            r'video player failed',
            r'video unavailable',
            r'ad choice',
            r'advertisement',
            r'sponsored content',
            r'promoted by',
            r'continue reading',
            r'more articles',
            r'related stories',
            r'similar news',
            r'share this story',
            r'email this article',
            r'print this page',
        ]
        
        text = content
        
        # Remove junk patterns (case insensitive)
        for pattern in junk_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Split into lines and clean
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip very short lines (likely garbage)
            if len(line) < 15:
                continue
            
            # Skip lines that are mostly numbers or special characters
            if len([c for c in line if c.isalnum()]) < len(line) * 0.3:
                continue
            
            # Skip lines that are just punctuation remnants
            if all(c in '.,;:!? \n\t\'' for c in line):
                continue
            
            # Skip lines that look like incomplete sentences (orphaned fragments)
            if line.startswith('.') or line.startswith(',') or line.startswith(';'):
                continue
            
            # Skip lines that start with metadata-like markers
            if any(line.lower().startswith(marker) for marker in ['updated:', 'published:', 'by:', 'link:', 'image:', 'photo:', 'video:']):
                continue
            
            # Skip duplicate lines
            if line in cleaned_lines:
                continue
            
            # Skip common navigation/UI text
            if any(nav in line.lower() for nav in ['home', 'about us', 'contact us', 'privacy', 'terms', 'subscribe', 'sign up', 'log in', 'follow us', 'share', 'comments', 'guidelines', 'postmedia', 'network inc', 'trending', 'featured', 'read more', 'local news', 'article content']):
                if len(line) < 100:  # Allow longer lines with these keywords
                    continue
            
            cleaned_lines.append(line)
        
        # Join and clean up extra whitespace
        final_text = '\n\n'.join(cleaned_lines)
        final_text = re.sub(r'\n\n+', '\n\n', final_text)  # Remove excessive newlines
        final_text = re.sub(r' +', ' ', final_text)  # Remove excessive spaces
        
        # Clean up mangled text like "anAfternoon" -> "an Afternoon", "bookmarkthestarphoenix" -> "bookmark the star phoenix"
        final_text = re.sub(r'an([A-Z])', r'an \1', final_text)
        final_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', final_text)
        
        # Clean orphaned punctuation at line starts/ends
        final_text = re.sub(r'^\s*[.,;:!?]+\s*', '', final_text, flags=re.MULTILINE)
        final_text = re.sub(r'\s*[,.;:]+\s*$', '', final_text, flags=re.MULTILINE)
        
        return final_text.strip()
    
    def generate_summary(self, content, num_sentences=3):
        """Generate a summary using the journalistic lede approach (first sentences contain key info)"""
        if not content or len(content) < 100:
            return content[:200]
        
        try:
            # Import nltk sentence tokenizer
            import nltk
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                nltk.download('punkt', quiet=True)
            
            # Split into sentences
            from nltk.tokenize import sent_tokenize
            sentences = sent_tokenize(content)
            
            if len(sentences) < 2:
                return content[:200]
            
            # Keep sentences that are reasonable length and not garbage
            valid_sentences = []
            for s in sentences:
                s_stripped = s.strip()
                # Filter out very short/long sentences and ones with too few words
                if 10 < len(s_stripped) < 500 and len(s_stripped.split()) > 3:
                    # Skip if looks like garbage (all caps, too many numbers, etc)
                    cap_ratio = sum(1 for c in s_stripped if c.isupper()) / len(s_stripped) if s_stripped else 0
                    if cap_ratio < 0.5:  # Not all caps
                        valid_sentences.append(s_stripped)
            
            if not valid_sentences:
                return content[:200]
            
            # Use journalistic lede approach: first 2-3 sentences typically contain the summary
            # This is more reliable than TF scoring
            num_sentences = min(num_sentences, len(valid_sentences))
            summary_sentences = valid_sentences[:num_sentences]
            
            summary = ' '.join(summary_sentences)
            
            # Limit to ~60 words
            words_list = summary.split()
            if len(words_list) > 60:
                summary = ' '.join(words_list[:60]) + '...'
            
            # Ensure proper ending
            if not summary.endswith(('.', '!', '?')):
                summary += '.'
            
            return summary if summary else content[:200]
        except Exception as e:
            logger.warning(f"Error generating summary: {e}")
            return content[:200]
    
    def cleanup_content_with_openai(self, content):
        """Use OpenAI to remove remaining garbage and polish content"""
        if not self.openai_enabled or not content:
            return content
        
        try:
            logger.info("  Cleaning content with OpenAI...")
            time.sleep(0.5)  # Rate limiting: 0.5 second delay between calls
            
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional news editor. Remove any remaining promotional text, metadata, newsletter signups, login prompts, comments sections, or non-editorial content. Keep only the core news story. Maintain paragraph structure. Return only the cleaned content without explanations."
                    },
                    {
                        "role": "user",
                        "content": f"Clean up this article content:\n\n{content[:3000]}"  # Limit to 3000 chars to manage costs
                    }
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            cleaned = response.choices[0].message.content.strip()
            logger.info("  ✓ OpenAI cleanup complete")
            return cleaned
        except Exception as e:
            logger.warning(f"OpenAI cleanup failed: {e}. Using original content.")
            return content
    
    def generate_summary_with_openai(self, content):
        """Generate a high-quality summary using OpenAI"""
        if not self.openai_enabled or not content:
            return self.generate_summary(content)
        
        try:
            logger.info("  Generating summary with OpenAI...")
            time.sleep(0.5)  # Rate limiting: 0.5 second delay between calls
            
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional news editor. Create a concise summary of the article in 50-70 words, capturing only the key facts. Be very brief and concise. Do not add your own commentary."
                    },
                    {
                        "role": "user",
                        "content": f"Summarize this article:\n\n{content[:3000]}"  # Limit to 3000 chars to manage costs
                    }
                ],
                temperature=0.5,
                max_tokens=150
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("  ✓ OpenAI summary complete")
            return summary
        except Exception as e:
            logger.warning(f"OpenAI summary failed: {e}. Falling back to local summarization.")
            return self.generate_summary(content)
    
    def cleanup_and_summarize_with_openai(self, content):
        """Legacy method - kept for backwards compatibility"""
        cleaned = self.cleanup_content_with_openai(content)
        summary = self.generate_summary_with_openai(cleaned)
        return cleaned, summary
    
    def scrape_article(self, entry):
        """Scrape individual article content"""
        article_url = entry.get('link')
        if not article_url:
            return None
        
        try:
            logger.info(f"Scraping article: {article_url}")
            response = requests.get(article_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Extract metadata
            title = entry.get('title', 'No Title')
            
            # Parse publication date
            pub_date = None
            if entry.get('published'):
                pub_date = entry.get('published')
            elif entry.get('updated'):
                pub_date = entry.get('updated')
            
            # Use today's date if no date found
            if not pub_date:
                pub_date = datetime.now().strftime('%Y-%m-%d')
            
            # Extract author (from RSS entry or HTML)
            author = entry.get('author', 'Unknown')
            if not author or author == 'Unknown':
                soup = BeautifulSoup(response.content, 'html.parser')
                # Try to find author in article
                author_elem = soup.find(class_=lambda x: x and 'author' in x.lower())
                if author_elem:
                    author = author_elem.get_text(strip=True)[:100]
                else:
                    author = 'Unknown'
            
            # Extract main content
            content = self.clean_content(response.content)
            content = content[:5000]  # Limit content length
            
            # Clean content with OpenAI if available
            if self.openai_enabled:
                content = self.cleanup_content_with_openai(content)
            
            # Generate summary
            if self.openai_enabled:
                summary = self.generate_summary_with_openai(content)
            else:
                summary = self.generate_summary(content, num_sentences=3)
            
            # Extract images
            soup = BeautifulSoup(response.content, 'html.parser')
            image_urls = []
            
            # Find main image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_urls.append(og_image['content'])
            
            # Find images in article content
            for img in soup.find_all('img', limit=5):
                img_src = img.get('src')
                if img_src and img_src not in image_urls:
                    img_src = urljoin(article_url, img_src)
                    image_urls.append(img_src)
                
                # Also try srcset for responsive images (picture elements)
                srcset = img.get('srcset')
                if srcset:
                    # Parse srcset format: "url1 1x, url2 2x" or "url1 640w, url2 1280w"
                    for srcset_entry in srcset.split(','):
                        srcset_url = srcset_entry.strip().split()[0]  # Get URL before size descriptor
                        if srcset_url and srcset_url not in image_urls:
                            srcset_url = urljoin(article_url, srcset_url)
                            image_urls.append(srcset_url)
            
            # Also extract from <source> elements inside <picture> tags
            for picture in soup.find_all('picture'):
                for source in picture.find_all('source'):
                    # Check srcset attribute on source elements
                    srcset = source.get('srcset')
                    if srcset:
                        # Parse srcset format
                        for srcset_entry in srcset.split(','):
                            srcset_url = srcset_entry.strip().split()[0]
                            if srcset_url and srcset_url not in image_urls:
                                srcset_url = urljoin(article_url, srcset_url)
                                image_urls.append(srcset_url)
            
            # Download images
            image_data = []  # List of (path, size) tuples
            for img_url in image_urls[:3]:  # Limit to 3 images
                local_path = self.download_image(img_url, title)
                if local_path:
                    try:
                        file_size = os.path.getsize(local_path)
                        image_data.append((local_path, file_size))
                    except Exception as e:
                        logger.debug(f"Could not get file size for {local_path}: {e}")
            
            
            # Keep only the largest image if multiple were downloaded
            if len(image_data) > 1:
                largest = max(image_data, key=lambda x: x[1])
                for path, size in image_data:
                    if path != largest[0]:
                        try:
                            os.remove(path)
                        except Exception as e:
                            logger.debug(f"Could not delete {path}: {e}")
                image_data = [largest]
            
            local_image_paths = [path for path, size in image_data]
            
            article_data = {
                'Source': self.source_name,
                'Title': title,
                'Date': pub_date,
                'Author': author,
                'URL': article_url,
                'Summary': summary,
                'Content': content,
                'Image_URLs': '|'.join(local_image_paths)
            }
            
            return article_data
        except requests.exceptions.Timeout:
            logger.warning(f"⏱ Timeout scraping {article_url} (taking too long)")
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning(f"🚫 Access blocked (403 Forbidden): {article_url}")
                logger.info("   Tip: This site has anti-scraping protection. Consider adding delays or using different headers.")
            elif e.response.status_code == 404:
                logger.warning(f"❌ Article not found (404): {article_url}")
            else:
                logger.warning(f"HTTP error {e.response.status_code} scraping {article_url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error scraping {article_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {article_url}: {e}")
            return None
    
    def save_to_csv(self, filename='articles.csv'):
        """Save articles to CSV file"""
        if not self.articles:
            logger.warning("No articles to save")
            return
        
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['Source', 'Title', 'Date', 'Author', 'URL', 'Summary', 'Content', 'Image_URLs']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.articles)
            
            logger.info(f"Saved {len(self.articles)} articles to {filepath}")
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def generate_html(self, filename='index.html'):
        """Generate a standalone HTML file with embedded article data"""
        if not self.articles:
            logger.warning("No articles to generate HTML")
            return
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Embed article data as JSON
        articles_json = json.dumps(self.articles)
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Star Phoenix Articles</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .line-clamp-2 {{
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
    </style>
</head>
<body class="bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <h1 class="text-3xl font-bold text-gray-900">🗞️ Star Phoenix News</h1>
            <p class="text-gray-600 mt-1">Latest articles from Star Phoenix RSS feed</p>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Articles Grid -->
        <div id="articles-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- Articles will be rendered here -->
        </div>
    </main>

    <!-- Article Detail Modal -->
    <div id="modal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 overflow-y-auto" onclick="closeOnOverlayClick(event)">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <!-- Modal Header -->
                <div class="sticky top-0 bg-white border-b p-4 sm:p-6 flex justify-between items-start">
                    <div class="flex-1">
                        <h2 id="modal-title" class="text-2xl sm:text-3xl font-bold text-gray-900 break-words"></h2>
                        <div id="modal-meta" class="flex flex-wrap gap-4 mt-2 text-sm text-gray-600">
                            <span id="modal-author"></span>
                            <span id="modal-date"></span>
                        </div>
                    </div>
                    <button onclick="closeModal()" class="text-gray-600 hover:text-gray-900 hover:bg-gray-100 font-bold text-4xl p-3 rounded-lg transition-colors flex-shrink-0">
                        ✕
                    </button>
                </div>

                <!-- Modal Image -->
                <div id="modal-image-container" class="bg-gray-100">
                    <!-- Images will be inserted here -->
                </div>

                <!-- Modal Content -->
                <div class="p-6 sm:p-8">
                    <div id="modal-summary" class="mb-6 p-4 bg-blue-50 border-l-4 border-blue-600 rounded"></div>
                    <div id="modal-content" class="max-w-none prose-base"></div>
                    <a id="modal-link" href="#" target="_blank" class="inline-block mt-6 text-blue-600 hover:text-blue-800 font-semibold underline">
                        Read on Star Phoenix →
                    </a>
                </div>

                <!-- Modal Footer -->
                <div class="border-t p-4 text-center">
                    <button onclick="closeModal()" class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold py-3 px-8 rounded text-lg">
                        Close
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Embedded article data
        const articles = {articles_json};

        // Render articles
        function renderArticles() {{
            const container = document.getElementById('articles-container');
            container.innerHTML = '';

            articles.forEach((article, index) => {{
                const dateFormatted = formatDate(article.Date);
                
                // Get first image if available
                let imagePath = '';
                if (article.Image_URLs) {{
                    const imagePaths = article.Image_URLs.split('|').filter(p => p.trim());
                    if (imagePaths.length > 0) {{
                        imagePath = imagePaths[0];
                        if (!imagePath.startsWith('http')) {{
                            imagePath = imagePath.replace(/^docs\\//, './').replace(/^articles\\//, './');
                        }}
                    }}
                }}

                const imageHtml = imagePath ? 
                    `<img src="${{escapeHtml(imagePath)}}" alt="Article image" class="w-full h-48 object-cover bg-gray-200" onerror="this.parentElement.style.backgroundColor='#d1d5db'; this.style.display='none';">` :
                    '';

                const card = document.createElement('div');
                card.className = 'bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer overflow-hidden';
                
                // Build author span conditionally
                const authorSpan = article.Author && article.Author !== 'Unknown' 
                    ? `<span>${{escapeHtml(article.Author)}}</span>` 
                    : '';
                
                card.innerHTML = `
                    ${{imageHtml}}
                    <div class="p-4">
                        <h3 class="font-bold text-lg text-gray-900 mb-2 line-clamp-2">${{escapeHtml(article.Title)}}</h3>
                        <p class="text-gray-600 text-sm mb-3 line-clamp-2 leading-relaxed">${{escapeHtml(article.Summary ? article.Summary.substring(0, 125) : 'No summary available')}}</p>
                        <div class="flex justify-between items-center text-xs text-gray-500">
                            ${{authorSpan}}
                            <span>${{dateFormatted}}</span>
                        </div>
                    </div>
                `;
                card.onclick = () => openModal(index);
                container.appendChild(card);
            }});
        }}

        // Escape HTML to prevent XSS
        function escapeHtml(text) {{
            if (!text) return '';
            const map = {{
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            }};
            return text.replace(/[&<>"']/g, m => map[m]);
        }}

        // Open modal with article details
        function openModal(index) {{
            const article = articles[index];
            const modal = document.getElementById('modal');

            // Set content
            document.getElementById('modal-title').textContent = article.Title;
            const authorSpan = document.getElementById('modal-author');
            const authorText = (article.Author || '').trim();
            if (authorText && authorText !== 'Unknown') {{
                authorSpan.textContent = 'By ' + authorText;
                authorSpan.style.display = 'inline';
            }} else {{
                authorSpan.textContent = '';
                authorSpan.style.display = 'none';
            }}
            document.getElementById('modal-date').textContent = formatDate(article.Date);
            document.getElementById('modal-link').href = article.URL;

            // Show summary if available
            if (article.Summary && article.Summary.trim()) {{
                document.getElementById('modal-summary').innerHTML = `<p class="font-semibold text-gray-800 leading-relaxed m-0">${{escapeHtml(article.Summary)}}</p>`;
            }} else {{
                document.getElementById('modal-summary').innerHTML = '';
            }}

            // Format content with line breaks and styling
            const formattedContent = article.Content
                .split('\\n\\n')
                .filter(p => p.trim())
                .map((p) => {{
                    const escaped = escapeHtml(p);
                    return `<p class="mb-4 leading-relaxed text-gray-700">${{escaped}}</p>`;
                }})
                .join('');
            document.getElementById('modal-content').innerHTML = formattedContent;

            // Add images if available
            const imageContainer = document.getElementById('modal-image-container');
            imageContainer.innerHTML = '';
            if (article.Image_URLs) {{
                const imagePaths = article.Image_URLs.split('|').filter(p => p.trim());
                if (imagePaths.length > 0) {{
                    imagePaths.forEach(imagePath => {{
                        if (!imagePath.startsWith('http')) {{
                            imagePath = imagePath.replace(/^docs\\//, './').replace(/^articles\\//, './');
                        }}
                        
                        const img = document.createElement('img');
                        img.src = imagePath;
                        img.alt = article.Title;
                        img.className = 'w-full h-auto';
                        img.onerror = () => {{
                            console.warn('Failed to load image:', imagePath);
                        }};
                        imageContainer.appendChild(img);
                    }});
                }}
            }}

            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }}

        function closeModal() {{
            document.getElementById('modal').classList.add('hidden');
            document.body.style.overflow = 'auto';
        }}

        // Close modal when clicking on the overlay (dark background)
        function closeOnOverlayClick(event) {{
            // Check if the click was on the modal itself (overlay), not on the white content box
            const contentBox = event.target.closest('.bg-white');
            if (!contentBox) {{
                closeModal();
            }}
        }}

        // Format date
        function formatDate(dateStr) {{
            try {{
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', {{ 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric' 
                }});
            }} catch (e) {{
                return dateStr;
            }}
        }}

        // Initialize
        renderArticles();
    </script>
</body>
</html>
"""
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Generated standalone HTML file: {filepath}")
        except Exception as e:
            logger.error(f"Error generating HTML: {e}")
    
    def run(self, max_articles=None):
        """Run the scraper for this source"""
        logger.info(f"Starting scraper for {self.source_name}...")
        
        # Fetch RSS feed
        entries = self.fetch_rss_feed()
        
        if not entries:
            logger.error("No articles found or unable to fetch feed")
            return
        
        if max_articles:
            entries = entries[:max_articles]
        
        # Scrape each article
        try:
            for i, entry in enumerate(entries, 1):
                logger.info(f"  Processing article {i}/{len(entries)}")
                article_data = self.scrape_article(entry)
                
                # Only keep articles that have both content AND images
                if article_data and article_data.get('Content', '').strip() and article_data.get('Image_URLs', '').strip():
                    self.articles.append(article_data)
                elif article_data:
                    # Log why we're skipping this article
                    has_content = bool(article_data.get('Content', '').strip())
                    has_images = bool(article_data.get('Image_URLs', '').strip())
                    reasons = []
                    if not has_content:
                        reasons.append("no content")
                    if not has_images:
                        reasons.append("no images")
                    logger.debug(f"Skipped article: {article_data.get('Title', 'Unknown')} ({', '.join(reasons)})")
                
                # Be respectful to the server
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("\nScraping interrupted by user")
        
        logger.info(f"Scraped {len(self.articles)} articles from {self.source_name}")


def deduplicate_articles_with_openai(articles, api_key):
    """Use OpenAI to identify and remove duplicate/similar articles based on title and summary"""
    if not articles or len(articles) < 2:
        return articles
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Create a summary of articles for OpenAI to analyze
        article_list = "\n".join([
            f"{i}. [{article['Source']}] {article['Title']} - {article['Summary'][:100]}"
            for i, article in enumerate(articles)
        ])
        
        logger.info("Sending articles to OpenAI for deduplication...")
        time.sleep(0.5)  # Rate limiting
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at identifying duplicate or near-duplicate articles. Two articles are duplicates if they cover the same story/news event, even if worded differently. Return ONLY a Python list of indices of UNIQUE articles to keep (e.g., [0, 2, 5, 7]). Do not include explanations."
                },
                {
                    "role": "user",
                    "content": f"Identify duplicate articles and return indices of unique ones to keep:\n\n{article_list}"
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse the response to get indices
        response_text = response.choices[0].message.content.strip()
        logger.debug(f"OpenAI deduplication response: {response_text}")
        
        # Extract list of indices from response
        import ast
        try:
            unique_indices = ast.literal_eval(response_text)
            if isinstance(unique_indices, list) and all(isinstance(i, int) for i in unique_indices):
                # Filter articles to keep only unique ones
                deduped_articles = [articles[i] for i in unique_indices if i < len(articles)]
                logger.info(f"✓ Removed {len(articles) - len(deduped_articles)} duplicate articles")
                
                # Reorder for variety while respecting dates
                deduped_articles = reorder_for_variety(deduped_articles)
                
                return deduped_articles
            else:
                logger.warning("OpenAI response not a valid list, keeping all articles")
                return articles
        except (ValueError, SyntaxError) as e:
            logger.warning(f"Could not parse OpenAI response: {e}, keeping all articles")
            return articles
            
    except Exception as e:
        logger.warning(f"OpenAI deduplication failed: {e}. Keeping all articles.")
        return articles


def reorder_for_variety(articles):
    """Reorder articles for source variety while respecting date order"""
    if len(articles) < 2:
        return articles
    
    # Sort by date first (newest first)
    sorted_articles = sorted(articles, key=lambda a: a.get('Date') or '', reverse=True)
    
    # Shuffle within sliding windows to mix sources while maintaining rough chronological order
    import random
    result = []
    window_size = max(3, len(articles) // 5)  # Shuffle within small windows
    
    for i in range(0, len(sorted_articles), window_size):
        window = sorted_articles[i:i+window_size]
        random.shuffle(window)
        result.extend(window)
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape RSS feeds from multiple news sources')
    parser.add_argument('-m', '--max', type=int, default=None, 
                        help='Maximum number of articles to scrape from each source')
    parser.add_argument('-o', '--output', default='docs', 
                        help='Output directory (default: docs)')
    parser.add_argument('-s', '--sources', nargs='+', default=None,
                        help=f'Sources to scrape (default: all). Available: {list(SOURCES.keys())}')
    
    args = parser.parse_args()
    
    # Determine which sources to scrape
    sources_to_scrape = args.sources if args.sources else list(SOURCES.keys())
    
    # Validate sources
    for source in sources_to_scrape:
        if source not in SOURCES:
            logger.error(f"Unknown source: {source}. Available: {list(SOURCES.keys())}")
            return
    
    # Clear old images directory before scraping
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, 'images')
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)
        logger.info(f"✓ Cleared old images directory")
    os.makedirs(images_dir, exist_ok=True)
    
    # Collect articles from all sources
    all_articles = []
    scrapers = []
    
    for source_key in sources_to_scrape:
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping: {SOURCES[source_key]['name']}")
        logger.info(f"{'='*60}")
        
        try:
            scraper = RSSNewsScraper(source_key, output_dir=args.output)
            scraper.run(max_articles=args.max)
            all_articles.extend(scraper.articles)
            scrapers.append(scraper)
        except Exception as e:
            logger.error(f"Error scraping {SOURCES[source_key]['name']}: {e}")
            continue
    
    if not all_articles:
        logger.error("No articles were scraped from any source")
        return
    
    # Deduplicate articles using OpenAI if available
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if openai_api_key:
        logger.info(f"\nDeduplicating {len(all_articles)} articles using OpenAI...")
        all_articles = deduplicate_articles_with_openai(all_articles, openai_api_key)
        logger.info(f"✓ Deduplication complete: {len(all_articles)} unique articles remaining")
    
    # Save combined results
    logger.info(f"\n{'='*60}")
    logger.info(f"Combining {len(all_articles)} articles from {len(sources_to_scrape)} sources")
    logger.info(f"{'='*60}\n")
    
    # Randomize articles with the same date
    all_articles = randomize_articles_by_date(all_articles)
    
    # Save combined CSV
    csv_path = os.path.join(output_dir, 'articles.csv')
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['Source', 'Title', 'Date', 'Author', 'URL', 'Summary', 'Content', 'Image_URLs']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_articles)
        logger.info(f"✓ Saved {len(all_articles)} articles to {csv_path}")
    except Exception as e:
        logger.error(f"Error saving CSV: {e}")
    
    # Generate combined HTML
    html_path = os.path.join(output_dir, 'index.html')
    try:
        generate_html_file(all_articles, html_path)
        logger.info(f"✓ Generated HTML file: {html_path}")
    except Exception as e:
        logger.error(f"Error generating HTML: {e}")



def randomize_articles_by_date(articles):
    """Randomize article order within each date group"""
    from itertools import groupby
    
    # Sort articles by date first
    sorted_articles = sorted(articles, key=lambda x: x.get('Date', ''))
    
    # Group by date and randomize within each group
    result = []
    for date, group in groupby(sorted_articles, key=lambda x: x.get('Date', '')):
        group_list = list(group)
        random.shuffle(group_list)
        result.extend(group_list)
    
    return result


def generate_html_file(articles, filepath):
    """Generate a standalone HTML file with embedded article data"""
    if not articles:
        logger.warning("No articles to generate HTML")
        return
    
    # Embed article data as JSON
    articles_json = json.dumps(articles)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Articles</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .line-clamp-2 {{
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
    </style>
</head>
<body class="bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <h1 class="text-3xl font-bold text-gray-900">🗞️ News Aggregator</h1>
            <p class="text-gray-600 mt-1">Latest articles from multiple sources</p>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Articles Grid -->
        <div id="articles-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- Articles will be rendered here -->
        </div>
    </main>

    <!-- Article Detail Modal -->
    <div id="modal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 overflow-y-auto" onclick="closeOnOverlayClick(event)">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <!-- Modal Header -->
                <div class="sticky top-0 bg-white border-b p-4 sm:p-6 flex justify-between items-start">
                    <div class="flex-1">
                        <h2 id="modal-title" class="text-2xl sm:text-3xl font-bold text-gray-900 break-words"></h2>
                        <div id="modal-meta" class="flex flex-wrap gap-4 mt-2 text-sm text-gray-600">
                            <span id="modal-source" class="font-semibold text-blue-600"></span>
                            <span id="modal-author"></span>
                            <span id="modal-date"></span>
                        </div>
                    </div>
                    <button onclick="closeModal()" class="text-gray-600 hover:text-gray-900 hover:bg-gray-100 font-bold text-4xl p-3 rounded-lg transition-colors">
                        ✕
                    </button>
                </div>

                <!-- Modal Image -->
                <div id="modal-image-container" class="bg-gray-100">
                    <!-- Images will be inserted here -->
                </div>

                <!-- Modal Content -->
                <div class="p-6 sm:p-8">
                    <div id="modal-summary" class="mb-6 p-4 bg-blue-50 border-l-4 border-blue-600 rounded"></div>
                    <div id="modal-content" class="max-w-none prose-base"></div>
                    <a id="modal-link" href="#" target="_blank" class="inline-block mt-6 text-blue-600 hover:text-blue-800 font-semibold underline">
                        Read Full Article →
                    </a>
                </div>

                <!-- Modal Footer -->
                <div class="border-t p-4 text-center">
                    <button onclick="closeModal()" class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold py-3 px-8 rounded text-lg">
                        Close
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Embedded article data
        const articles = {articles_json};

        // Source color mapping
        const sourceColors = {{
            'Star Phoenix': {{ bg: 'bg-red-100', text: 'text-red-800' }},
            'CBC News - World': {{ bg: 'bg-orange-100', text: 'text-orange-800' }},
            'New York Times - World': {{ bg: 'bg-yellow-100', text: 'text-yellow-800' }},
            'Smashing Magazine': {{ bg: 'bg-pink-100', text: 'text-pink-800' }},
            'Laravel News': {{ bg: 'bg-purple-100', text: 'text-purple-800' }},
            'Saskatoon Police News': {{ bg: 'bg-indigo-100', text: 'text-indigo-800' }},
            'Thomson Reuters News': {{ bg: 'bg-cyan-100', text: 'text-cyan-800' }},
            'BBC News - World': {{ bg: 'bg-teal-100', text: 'text-teal-800' }},
            'Dow Jones - Top Stories': {{ bg: 'bg-green-100', text: 'text-green-800' }},
            'The Hockey Writers': {{ bg: 'bg-sky-100', text: 'text-sky-800' }},
            'ESPN NFL News': {{ bg: 'bg-violet-100', text: 'text-violet-800' }},
            'ESPN NFL News': {{ bg: 'bg-violet-100', text: 'text-violet-800' }}
        }};

        function getSourceColor(source) {{
            return sourceColors[source] || {{ bg: 'bg-gray-100', text: 'text-gray-800' }};
        }}

        // Render articles
        function renderArticles() {{
            const container = document.getElementById('articles-container');
            container.innerHTML = '';

            // Sort articles by date (newest first)
            const sortedArticles = articles.sort((a, b) => {{
                const dateA = new Date(a.Date) || new Date(0);
                const dateB = new Date(b.Date) || new Date(0);
                return dateB - dateA;
            }});

            sortedArticles.forEach((article, index) => {{
                const dateFormatted = formatDate(article.Date);
                const sourceColor = getSourceColor(article.Source);
                
                // Get first image if available
                let imagePath = '';
                if (article.Image_URLs) {{
                    const imagePaths = article.Image_URLs.split('|').filter(p => p.trim());
                    if (imagePaths.length > 0) {{
                        imagePath = imagePaths[0];
                        if (!imagePath.startsWith('http')) {{
                            imagePath = imagePath.replace(/^docs\\//, './').replace(/^articles\\//, './');
                        }}
                    }}
                }}

                const imageHtml = imagePath ? 
                    `<img src="${{escapeHtml(imagePath)}}" alt="Article image" class="w-full h-48 object-cover bg-gray-200" onerror="this.parentElement.style.backgroundColor='#d1d5db'; this.style.display='none';">` :
                    '';

                const card = document.createElement('div');
                card.className = 'bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer overflow-hidden';
                card.innerHTML = `
                    ${{imageHtml}}
                    <div class="p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-xs font-semibold ${{sourceColor.bg}} ${{sourceColor.text}} px-2 py-1 rounded">${{escapeHtml(article.Source)}}</span>
                        </div>
                        <h3 class="font-bold text-lg text-gray-900 mb-2 line-clamp-2">${{escapeHtml(article.Title)}}</h3>
                        <p class="text-gray-600 text-sm mb-3 line-clamp-2 leading-relaxed">${{escapeHtml(article.Summary ? article.Summary.substring(0, 125) : 'No summary available')}}</p>
                        <div class="flex justify-between items-center text-xs text-gray-500">
                            <span>${{escapeHtml(article.Author)}}</span>
                            <span>${{dateFormatted}}</span>
                        </div>
                    </div>
                `;
                card.onclick = () => openModal(index);
                container.appendChild(card);
            }});
        }}

        // Escape HTML to prevent XSS
        function escapeHtml(text) {{
            if (!text) return '';
            const map = {{
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            }};
            return text.replace(/[&<>"']/g, m => map[m]);
        }}

        // Open modal with article details
        function openModal(index) {{
            const article = articles[index];
            const modal = document.getElementById('modal');

            // Set content
            document.getElementById('modal-title').textContent = article.Title;
            document.getElementById('modal-source').textContent = article.Source;
            document.getElementById('modal-author').textContent = `${{article.Author !== 'Unknown' ? ('By ' + article.Author) : ''}}`;
            document.getElementById('modal-date').textContent = formatDate(article.Date);
            document.getElementById('modal-link').href = article.URL;

            // Show summary if available
            if (article.Summary && article.Summary.trim()) {{
                document.getElementById('modal-summary').innerHTML = `<p class="font-semibold text-gray-800 leading-relaxed m-0">${{escapeHtml(article.Summary)}}</p>`;
            }} else {{
                document.getElementById('modal-summary').innerHTML = '';
            }}

            // Format content with line breaks and styling
            const formattedContent = article.Content
                .split('\\n\\n')
                .filter(p => p.trim())
                .map((p) => {{
                    const escaped = escapeHtml(p);
                    return `<p class="mb-4 leading-relaxed text-gray-700">${{escaped}}</p>`;
                }})
                .join('');
            document.getElementById('modal-content').innerHTML = formattedContent;

            // Add images if available
            const imageContainer = document.getElementById('modal-image-container');
            imageContainer.innerHTML = '';
            if (article.Image_URLs) {{
                const imagePaths = article.Image_URLs.split('|').filter(p => p.trim());
                if (imagePaths.length > 0) {{
                    imagePaths.forEach(imagePath => {{
                        if (!imagePath.startsWith('http')) {{
                            imagePath = imagePath.replace(/^docs\\//, './').replace(/^articles\\//, './');
                        }}
                        
                        const img = document.createElement('img');
                        img.src = imagePath;
                        img.alt = article.Title;
                        img.className = 'w-full h-auto';
                        img.onerror = () => {{
                            console.warn('Failed to load image:', imagePath);
                        }};
                        imageContainer.appendChild(img);
                    }});
                }}
            }}

            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }}

        function closeModal() {{
            document.getElementById('modal').classList.add('hidden');
            document.body.style.overflow = 'auto';
        }}

        // Close modal when clicking on the overlay (dark background)
        function closeOnOverlayClick(event) {{
            // Check if the click was on the modal itself (overlay), not on the white content box
            const contentBox = event.target.closest('.bg-white');
            if (!contentBox) {{
                closeModal();
            }}
        }}

        // Format date
        function formatDate(dateStr) {{
            try {{
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', {{ 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric' 
                }});
            }} catch (e) {{
                return dateStr;
            }}
        }}

        // Initialize
        renderArticles();
    </script>
</body>
</html>
"""
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Generated HTML file: {filepath}")
    except Exception as e:
        logger.error(f"Error generating HTML: {e}")


if __name__ == '__main__':
    main()
