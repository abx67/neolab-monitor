#!/usr/bin/env python3
"""
Multi-Company AI Jobs Scraper - Research Engineer Positions

This script scrapes multiple AI company careers pages (Anthropic, OpenAI) and extracts 
research engineer related job postings, combining them into a unified report.
Can send results via email and run on a daily schedule.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
import time
import smtplib
import schedule
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urljoin

# Load environment variables from .env file (for local development)
# On Heroku, environment variables are automatically available
load_dotenv()

# Import GitHub Gist storage for persistent job history
try:
    from simple_storage import get_simple_storage
    SIMPLE_STORAGE_AVAILABLE = True
except ImportError:
    print("⚠️ Simple storage not available. Using file-based storage.")
    SIMPLE_STORAGE_AVAILABLE = False


class JobScraper:
    """Base class for job scrapers."""
    
    def __init__(self, company_name: str, base_url: str):
        self.company_name = company_name
        self.base_url = base_url
        self.session = requests.Session()
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def fetch_page(self) -> Optional[BeautifulSoup]:
        """Fetch the jobs page and return BeautifulSoup object."""
        try:
            print(f"Fetching jobs from {self.company_name}: {self.base_url}")
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
            
        except requests.RequestException as e:
            print(f"Error fetching {self.company_name} page: {e}")
            return None
    
    def extract_jobs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract job listings from the page. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement extract_jobs method")
    
    def scrape_jobs(self) -> List[Dict[str, str]]:
        """Main method to scrape jobs from this company."""
        soup = self.fetch_page()
        if not soup:
            return []
        
        jobs = self.extract_jobs(soup)
        
        # Add company name to each job
        for job in jobs:
            job['company'] = self.company_name
        
        return jobs


class AnthropicScraper(JobScraper):
    """Scraper for Anthropic job listings."""
    
    def __init__(self):
        super().__init__("Anthropic", "https://www.anthropic.com/jobs")
    
    def extract_jobs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract job listings from Anthropic page."""
        jobs = []
        debug_mode = os.getenv("SCRAPER_DEBUG", "").lower() in ("1", "true", "yes", "on")
        max_debug_samples = 5
        
        # New site renders job cards as Greenhouse links inside anchor tags
        job_elements = soup.find_all('a', href=re.compile(r'job-boards\.greenhouse\.io/anthropic/jobs'))

        print(f"   Found {len(job_elements)} job elements to process")
        if debug_mode:
            print(f"   Debug mode on: showing up to {max_debug_samples} raw elements")
        for idx, job_element in enumerate(job_elements):
            if debug_mode and idx < max_debug_samples:
                # Debug: show the raw element so we can update selectors after site changes
                raw_element = job_element.prettify() if hasattr(job_element, "prettify") else str(job_element)
                snippet = raw_element[:600].replace("\n", " ")
                print(f"   Raw job element #{idx}: {snippet}{'...' if len(raw_element) > 600 else ''}")

            # Title lives in the role block inside the anchor
            title_elem = job_element.find(class_=re.compile('jobRole'))
            job_title = title_elem.get_text(strip=True) if title_elem else job_element.get_text(strip=True)
            if debug_mode:
                print(f"   Processing job title: {job_title}")
            
            # Skip if it's not a proper job title
            if not job_title or len(job_title) < 5:
                continue
                
            # Location block inside the anchor
            location = ""
            location_elem = job_element.find(class_=re.compile('jobLocation'))
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                location = location_text
            
            # The anchor itself is the apply link
            apply_link = job_element.get('href', '')
            
            jobs.append({
                'title': job_title,
                'location': location,
                'apply_link': apply_link
            })
        print(f"   Extracted {len(jobs)} jobs from Anthropic page")
        return jobs


class OpenAIScraper(JobScraper):
    """Scraper for OpenAI job listings."""
    
    def __init__(self):
        super().__init__("OpenAI", "https://jobs.ashbyhq.com/openai")
        # Add more headers to bypass anti-bot protection
        self.session.headers.update({
            'Referer': 'https://jobs.ashbyhq.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def fetch_page(self) -> Optional[BeautifulSoup]:
        """Fetch the OpenAI jobs page with additional retry logic."""
        try:
            print(f"Fetching jobs from {self.company_name}: {self.base_url}")
            
            # Try multiple times with delays
            for attempt in range(3):
                try:
                    # Add a delay between attempts
                    if attempt > 0:
                        time.sleep(2 * attempt)
                    
                    response = self.session.get(self.base_url, timeout=15)
                    
                    if response.status_code == 403:
                        print(f"   Attempt {attempt + 1}: Access forbidden (403). OpenAI may be blocking scrapers.")
                        if attempt < 2:
                            continue
                        else:
                            print("   🔄 Trying alternative approach...")
                            # Try to get some job data from our cached webpage fetch
                            return self._get_cached_openai_jobs()
                    
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    return soup
                    
                except requests.RequestException as e:
                    if attempt < 2:
                        print(f"   Attempt {attempt + 1} failed: {e}. Retrying...")
                        continue
                    else:
                        print(f"   All attempts failed. Using cached data...")
                        return self._get_cached_openai_jobs()
            
        except Exception as e:
            print(f"Error fetching {self.company_name} page: {e}")
            return self._get_cached_openai_jobs()
    
    def _get_cached_openai_jobs(self) -> Optional[BeautifulSoup]:
        """Handle OpenAI scraping failure gracefully."""
        print("   ⚠️ OpenAI jobs could not be fetched due to access restrictions.")
        print("   💡 Check their job board manually: https://jobs.ashbyhq.com/openai")
        return None
    
    def extract_jobs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract job listings from OpenAI Ashby page."""
        jobs = []
        
        # Try to find JSON data in the page (Ashby uses client-side rendering)
        script_tags = soup.find_all('script')
        job_data = None
        
        print(f"   Found {len(script_tags)} script tags to search")
        
        for i, script in enumerate(script_tags):
            script_content = script.string
            if script_content:
                print(f"   Script {i}: Length {len(script_content)}, Contains appData: {'window.__appData' in script_content}")
                if 'window.__appData' in script_content:
                    print("   Found window.__appData in script tag")
                # Look for the window.__appData object
                try:
                    # Find the start of the JSON object
                    start = script_content.find('window.__appData = ')
                    if start == -1:
                        start = script_content.find('window.__appData=')
                        pattern = 'window.__appData='
                    else:
                        pattern = 'window.__appData = '
                    
                    if start != -1:
                        start += len(pattern)
                        # Find the end of the JSON object (ends with })
                        bracket_count = 0
                        in_string = False
                        escape_next = False
                        end = start
                        
                        print(f"   Starting bracket counting from position {start}")
                        
                        for i, char in enumerate(script_content[start:], start):
                            if i == start + 50:  # Just check first 50 chars for debugging
                                print(f"   First 50 chars: {script_content[start:start+50]}")
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                                
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                                
                            if not in_string:
                                if char == '{':
                                    bracket_count += 1
                                elif char == '}':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        end = i + 1
                                        print(f"   Found end of JSON at position {end}")
                                        break
                        
                        if bracket_count != 0:
                            print(f"   Warning: Bracket count didn't reach 0, final count: {bracket_count}")
                        
                        json_str = script_content[start:end]
                        print(f"   Extracted JSON string length: {len(json_str)}")
                        print(f"   JSON starts with: {json_str[:100]}...")
                        app_data = json.loads(json_str)
                        
                        print(f"   Parsed JSON with keys: {list(app_data.keys())}")
                        
                        # Extract jobs from the app data
                        job_data = []
                        if 'jobs' in app_data:
                            job_data = app_data['jobs']
                            print(f"   Found {len(job_data)} jobs in 'jobs' key")
                        elif 'jobBoard' in app_data:
                            print(f"   Examining jobBoard structure: {type(app_data['jobBoard'])}")
                            job_board = app_data['jobBoard']
                            if isinstance(job_board, dict):
                                print(f"   jobBoard keys: {list(job_board.keys())}")
                                if 'jobs' in job_board:
                                    job_data = job_board['jobs']
                                    print(f"   Found {len(job_data)} jobs in jobBoard.jobs")
                                elif 'jobPostings' in job_board:
                                    job_data = job_board['jobPostings']
                                    print(f"   Found {len(job_data)} jobs in jobBoard.jobPostings")
                        else:
                            print("   No 'jobs' or 'jobBoard' key found in app data")
                            print(f"   Available keys: {list(app_data.keys())}")
                            job_data = []
                        break
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    print(f"   Error parsing JSON: {e}")
                    continue
        
        if job_data:
            # Process the JSON job data
            for job in job_data:
                job_title = job.get('title', '')
                location = job.get('locationName', 'San Francisco')  # Default location
                job_id = job.get('id', '')
                
                # Filter for research-related positions
                research_keywords = ['research', 'scientist', 'engineer', 'ml', 'machine learning', 'ai', 'artificial intelligence']
                if job_title and len(job_title) > 5 and any(keyword.lower() in job_title.lower() for keyword in research_keywords):
                    jobs.append({
                        'title': job_title,
                        'location': location,
                        'apply_link': f"https://jobs.ashbyhq.com/openai/{job_id}",
                        'job_url': f"https://jobs.ashbyhq.com/openai/{job_id}"
                    })
        
        # Fallback: Try to find job links in HTML if JSON parsing failed
        if not jobs:
            job_links = soup.find_all('a', href=re.compile(r'/openai/[a-f0-9-]+$'))
            
            for job_link in job_links:
                job_title = job_link.get_text(strip=True)
                
                # Skip if it's not a proper job title or not research-related
                research_keywords = ['research', 'scientist', 'engineer', 'ml', 'machine learning', 'ai', 'artificial intelligence']
                if not job_title or len(job_title) < 5 or not any(keyword.lower() in job_title.lower() for keyword in research_keywords):
                    continue
                
                # Extract location from the parent element text (Ashby format)
                location = "San Francisco, CA"  # Default for most OpenAI research roles
                href = job_link.get('href', '')
                
                # Try to extract location from the job link's parent text
                parent_text = job_link.parent.get_text() if job_link.parent else ''
                
                # Look for location patterns in the parent text
                location_indicators = [
                    'San Francisco', 'New York', 'Seattle', 'Remote', 'London', 
                    'Dublin', 'Tokyo', 'Singapore', 'Washington', 'Paris', 'Munich'
                ]
                
                for loc in location_indicators:
                    if loc in parent_text:
                        location = loc
                        break
                
                # Create apply link - Ashby format
                job_url = f"https://jobs.ashbyhq.com{href}" if href else ""
                apply_link = job_url  # Same as job URL for Ashby
                
                jobs.append({
                    'title': job_title,
                    'location': location,
                    'apply_link': apply_link,
                    'job_url': job_url
                })
        
        return jobs


class DeepMindScraper(JobScraper):
    """Scraper for DeepMind jobs from their Greenhouse API."""
    
    def __init__(self):
        super().__init__("DeepMind", "https://boards-api.greenhouse.io/v1/boards/deepmind/jobs")
    
    def scrape_jobs(self) -> List[Dict[str, str]]:
        """Override the main scrape method to use JSON API instead of HTML parsing."""
        return self.get_jobs()
    
    def extract_jobs(self, soup):
        """Not used for API-based scraping, but required by base class."""
        return []
    
    def get_jobs(self):
        """Fetch jobs from DeepMind's Greenhouse API."""
        try:
            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for job in data.get('jobs', []):
                job_title = job.get('title', '').strip()
                location = job.get('location', {}).get('name', '').strip()
                apply_url = job.get('absolute_url', '').strip()
                
                if job_title and apply_url:
                    jobs.append({
                        'title': job_title,
                        'location': location,
                        'apply_link': apply_url,
                        'company': self.company_name
                    })
            
            print(f"Found {len(jobs)} jobs from {self.company_name}")
            return jobs
            
        except requests.RequestException as e:
            print(f"Error fetching jobs from {self.company_name}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error scraping {self.company_name}: {e}")
            return []


class XAIScraper(JobScraper):
    """Scraper for X.ai jobs from their Greenhouse API."""
    
    def __init__(self):
        super().__init__("X.ai", "https://boards-api.greenhouse.io/v1/boards/xai/jobs")
    
    def scrape_jobs(self) -> List[Dict[str, str]]:
        """Override the main scrape method to use JSON API instead of HTML parsing."""
        return self.get_jobs()
    
    def extract_jobs(self, soup):
        """Not used for API-based scraping, but required by base class."""
        return []
    
    def get_jobs(self):
        """Fetch jobs from X.ai's Greenhouse API."""
        try:
            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for job in data.get('jobs', []):
                job_title = job.get('title', '').strip()
                location = job.get('location', {}).get('name', '').strip()
                apply_url = job.get('absolute_url', '').strip()
                
                if job_title and apply_url:
                    jobs.append({
                        'title': job_title,
                        'location': location,
                        'apply_link': apply_url,
                        'company': self.company_name
                    })
            
            print(f"Found {len(jobs)} jobs from {self.company_name}")
            return jobs
            
        except requests.RequestException as e:
            print(f"Error fetching jobs from {self.company_name}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error scraping {self.company_name}: {e}")
            return []


class SeedScraper(JobScraper):
    """Scraper for ByteDance Seed jobs from their team pages."""
    
    def __init__(self):
        super().__init__("ByteDance Seed", "https://seed.bytedance.com/en/career")
        # List of team pages that have job listings
        self.team_pages = [
            "https://seed.bytedance.com/en/direction/llm",
            "https://seed.bytedance.com/en/direction/vision", 
            "https://seed.bytedance.com/en/direction/speech",
            "https://seed.bytedance.com/en/direction/multimodal",
            "https://seed.bytedance.com/en/direction/ai_for_science",
            "https://seed.bytedance.com/en/direction/robotics",
            "https://seed.bytedance.com/en/direction/infrastructures",
            "https://seed.bytedance.com/en/direction/responsible_ai"
        ]
    
    def scrape_jobs(self) -> List[Dict[str, str]]:
        """Override the main scrape method to scrape from multiple team pages."""
        all_jobs = []
        
        for team_url in self.team_pages:
            try:
                response = self.session.get(team_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract jobs from this team page
                jobs = self.extract_jobs_from_team_page(soup, team_url)
                all_jobs.extend(jobs)
                
            except Exception as e:
                print(f"Error scraping {team_url}: {e}")
                continue
        
        # Remove duplicates based on apply_link
        unique_jobs = []
        seen_links = set()
        for job in all_jobs:
            if job['apply_link'] not in seen_links:
                unique_jobs.append(job)
                seen_links.add(job['apply_link'])
        
        print(f"Found {len(unique_jobs)} unique jobs from {self.company_name}")
        return unique_jobs
    
    def extract_jobs(self, soup):
        """Not used for this scraper, but required by base class."""
        return []
    
    def extract_jobs_from_team_page(self, soup, team_url):
        """Extract job listings from a specific team page."""
        jobs = []
        
        # Look for job links in the "Featured Jobs" section
        # Jobs are typically in anchor tags with specific patterns
        job_links = soup.find_all('a', href=True)
        
        for link in job_links:
            href = link.get('href', '')
            
            # Check if this is a job posting link (jobs.toutiao.com or job.toutiao.com)
            if ('job.toutiao.com' in href or 'jobs.toutiao.com' in href) and '/position/' in href:
                job_text = link.get_text(strip=True)
                
                # Extract job title and location from the text
                # Format is typically: "Job Title Location Employment_Type Apply Now"
                if job_text and 'Apply Now' in job_text:
                    # Remove "Apply Now" from the end
                    job_info = job_text.replace('Apply Now', '').strip()
                    
                    # Try to separate title and location
                    # Look for common location patterns
                    location_patterns = [
                        'San Jose', 'Seattle', 'Singapore', 'Beijing', 'Shanghai',
                        'Palo Alto', 'New York', 'London', 'Tokyo', 'San Francisco'
                    ]
                    
                    title = job_info
                    location = ""
                    
                    for loc_pattern in location_patterns:
                        if loc_pattern in job_info:
                            parts = job_info.split(loc_pattern)
                            if len(parts) >= 2:
                                title = parts[0].strip()
                                location = loc_pattern
                                # Check if there are additional location details after
                                remaining = parts[1].strip()
                                if remaining and not any(emp_type in remaining.lower() 
                                                       for emp_type in ['experienced', 'campus', 'internship']):
                                    location += remaining.split()[0] if remaining.split() else ""
                                break
                    
                    # Clean up the title by removing employment type info
                    employment_types = ['Experienced Hiring', 'Campus Recruitment', 'Internship']
                    for emp_type in employment_types:
                        title = title.replace(emp_type, '').strip()
                    
                    # Make sure we have a proper apply URL
                    apply_url = href
                    if apply_url.startswith('http://'):
                        apply_url = apply_url.replace('http://', 'https://')
                    elif not apply_url.startswith('https://'):
                        apply_url = 'https://' + apply_url.lstrip('/')
                    
                    if title and apply_url:
                        jobs.append({
                            'title': title,
                            'location': location or 'Multiple Locations',
                            'apply_link': apply_url,
                            'company': self.company_name
                        })
        
        return jobs


class ThinkingMachinesScraper(JobScraper):
    """Scraper for Thinking Machines AI jobs from their Ashby board."""
    
    def __init__(self):
        super().__init__("Thinking Machines", "https://jobs.ashbyhq.com/ThinkingMachines")
        self.session.headers.update({
            'Referer': 'https://jobs.ashbyhq.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def scrape_jobs(self) -> List[Dict[str, str]]:
        """Override the main scrape method to use Ashby JSON data from the page."""
        soup = self.fetch_page()
        if not soup:
            return []
        return self.extract_jobs(soup)
    
    def extract_jobs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract job listings from Thinking Machines Ashby page."""
        jobs = []
        
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            script_content = script.string
            if script_content and 'window.__appData' in script_content:
                try:
                    start = script_content.find('window.__appData = ')
                    if start == -1:
                        start = script_content.find('window.__appData=')
                        pattern = 'window.__appData='
                    else:
                        pattern = 'window.__appData = '
                    
                    if start != -1:
                        start += len(pattern)
                        bracket_count = 0
                        in_string = False
                        escape_next = False
                        end = start
                        
                        for i, char in enumerate(script_content[start:], start):
                            if escape_next:
                                escape_next = False
                                continue
                            if char == '\\':
                                escape_next = True
                                continue
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                            if not in_string:
                                if char == '{':
                                    bracket_count += 1
                                elif char == '}':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        end = i + 1
                                        break
                        
                        json_str = script_content[start:end]
                        app_data = json.loads(json_str)
                        
                        job_data = []
                        if 'jobBoard' in app_data and isinstance(app_data['jobBoard'], dict):
                            job_board = app_data['jobBoard']
                            if 'jobPostings' in job_board:
                                job_data = job_board['jobPostings']
                        
                        for job in job_data:
                            job_title = job.get('title', '').strip()
                            location = job.get('locationName', '').strip()
                            job_id = job.get('id', '').strip()
                            
                            if job_title and job_id:
                                jobs.append({
                                    'title': job_title,
                                    'location': location or 'San Francisco',
                                    'apply_link': f"https://jobs.ashbyhq.com/ThinkingMachines/{job_id}",
                                    'job_url': f"https://jobs.ashbyhq.com/ThinkingMachines/{job_id}"
                                })
                        break
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    print(f"   Error parsing Thinking Machines JSON: {e}")
                    continue
        
        print(f"Found {len(jobs)} jobs from {self.company_name}")
        return jobs


class MultiCompanyJobsScraper:
    """Main scraper that combines results from multiple companies."""
    
    def __init__(self):
        # Initialize company scrapers
        self.scrapers = [
            AnthropicScraper(),
            OpenAIScraper(),
            DeepMindScraper(),
            XAIScraper(),
            SeedScraper(),
            ThinkingMachinesScraper()
        ]
        
        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # Validate email configuration on initialization
        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            print("⚠️  Warning: Email configuration incomplete. Email notifications will be disabled.")
            print("   Required environment variables: SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL")
        
        # Storage configuration
        self.jobs_history_file = "ai_jobs_history.json"
        
        # Initialize storage backend (GitHub Gist or file storage)
        self.external_storage = None
        
        # Try GitHub Gist storage (free with GitHub account)
        if SIMPLE_STORAGE_AVAILABLE:
            try:
                self.external_storage = get_simple_storage()
                if self.external_storage:
                    print("✅ Using GitHub Gist storage for job history")
            except Exception as e:
                print(f"⚠️ GitHub Gist storage failed: {e}")
        
        # Fallback to file storage (will be lost on Heroku)
        if not self.external_storage:
            print("📝 Using file-based storage for job history (will be lost on Heroku restarts)")
            print("💡 For persistent storage, set up GitHub token (see GITHUB_TOKEN_GUIDE.md)")
    
    def filter_research_engineer_jobs(self, jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter jobs to find research engineer related positions."""
        research_keywords = [
            'research engineer',
            'research scientist',
            'research scientist/engineer', 
            'research scientist / engineer',
            'machine learning engineer',
            'ml engineer',
            'research manager',
            'staff research engineer',
            'senior research engineer',
            'principal research engineer',
            'ai research',
            'research operations',
            'research recruiting',
            'human-ai collaboration research engineer',
            'lead research engineer',
            'researcher engineer',
            'member of technical staff'
        ]
        
        # Blacklist words to exclude from results
        blacklist_keywords = [
            'safeguards',
            'recruit',
            'operation',
            'manager',
            'biology',
            'scaling',
            'honesty',
            'education',
            'protection',
            'investigat',
            'threat',
            'security',
            'legal',
            'business',
            'marketing',
            'sales',
            'finance',
            'people',
            'data',
            'intern',
            'comput',
            'trust',
            'deploy',
            'strate',
            'robust',
            'safe',
            'health',
            'eval',
            'environment',
            'weather',
            'energy',
            'human',
            'notif',
            'cyber',
            'integr',
            'biolog',
            'chemic',
            'community',
            'cuda',
            'optim',
            'efficien',
            'quanti',
            'inference',
            'govern',
            'compil',
            'product',
            'design',
            'university',
            'platform',
            'graduate',
            'atomistic',
            'system',
            'responsible',
            'phd',
        ]
        
        filtered_jobs = []
        
        for job in jobs:
            job_title_lower = job['title'].lower()
            
            # Check if any research engineering keywords are in the title
            if any(keyword in job_title_lower for keyword in research_keywords):
                # Check if any blacklist keywords are in the title
                if not any(blacklist_word in job_title_lower for blacklist_word in blacklist_keywords):
                    filtered_jobs.append(job)
        
        return filtered_jobs
    
    def scrape_all_companies(self) -> Dict[str, List[Dict[str, str]]]:
        """Scrape jobs from all companies."""
        all_jobs = {}
        
        # Companies to include ALL positions (no filtering)
        no_filter_companies = ["Thinking Machines"]
        
        for scraper in self.scrapers:
            print(f"\n🔍 Scraping {scraper.company_name}...")
            jobs = scraper.scrape_jobs()
            
            if jobs:
                if scraper.company_name in no_filter_companies:
                    # Include ALL jobs for smaller companies
                    all_jobs[scraper.company_name] = jobs
                    print(f"   Found {len(jobs)} total jobs, all positions included")
                else:
                    # Filter for research engineer positions for larger companies
                    filtered_jobs = self.filter_research_engineer_jobs(jobs)
                    all_jobs[scraper.company_name] = filtered_jobs
                    print(f"   Found {len(jobs)} total jobs, {len(filtered_jobs)} research engineer positions")
            else:
                all_jobs[scraper.company_name] = []
                print(f"   No jobs found")
        
        return all_jobs
    
    def load_previous_jobs(self) -> Dict[str, List[Dict[str, str]]]:
        """Load previously found jobs from GitHub Gist or local file."""
        # Try external storage first (GitHub Gist)
        if self.external_storage:
            return self.external_storage.load_previous_jobs()
        
        # Fallback to file-based storage
        else:
            try:
                if os.path.exists(self.jobs_history_file):
                    with open(self.jobs_history_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception as e:
                print(f"Error loading job history: {e}")
            return {}
    
    def save_jobs_history(self, jobs: Dict[str, List[Dict[str, str]]]) -> None:
        """Save current jobs to GitHub Gist or local file."""
        # Try external storage first (GitHub Gist)
        if self.external_storage:
            self.external_storage.save_jobs_history(jobs)
        
        # Fallback to file-based storage
        else:
            try:
                with open(self.jobs_history_file, 'w', encoding='utf-8') as f:
                    json.dump(jobs, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving job history: {e}")
    
    def find_new_jobs(self, current_jobs: Dict[str, List[Dict[str, str]]], 
                     previous_jobs: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
        """Find new jobs that weren't in the previous list."""
        new_jobs = {}
        
        for company, jobs in current_jobs.items():
            previous_company_jobs = previous_jobs.get(company, [])
            previous_titles = {job['title'] for job in previous_company_jobs}
            
            company_new_jobs = [job for job in jobs if job['title'] not in previous_titles]
            if company_new_jobs:
                new_jobs[company] = company_new_jobs
        
        return new_jobs

    def find_removed_jobs(self, current_jobs: Dict[str, List[Dict[str, str]]], 
                          previous_jobs: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
        """Find jobs that were present previously but are now removed."""
        removed_jobs: Dict[str, List[Dict[str, str]]] = {}

        # Iterate through companies that had previous jobs
        for company, prev_jobs in previous_jobs.items():
            current_company_jobs = current_jobs.get(company, [])
            current_titles = {job['title'] for job in current_company_jobs}

            company_removed = [job for job in prev_jobs if job.get('title') not in current_titles]
            if company_removed:
                removed_jobs[company] = company_removed

        return removed_jobs
    
    def display_jobs(self, all_jobs: Dict[str, List[Dict[str, str]]], 
                    new_jobs: Dict[str, List[Dict[str, str]]] = None) -> None:
        """Display the filtered jobs in a clean format."""
        total_jobs = sum(len(jobs) for jobs in all_jobs.values())
        total_new = sum(len(jobs) for jobs in new_jobs.values()) if new_jobs else 0
        
        print(f"\n{'='*80}")
        print(f"AI RESEARCH ENGINEER JOBS - {total_jobs} positions found")
        if total_new > 0:
            print(f"🆕 {total_new} new positions since last check!")
        print(f"{'='*80}")
        
        for company, jobs in all_jobs.items():
            if jobs:
                company_new = new_jobs.get(company, []) if new_jobs else []
                new_titles = {job['title'] for job in company_new}
                
                print(f"\n🏢 {company.upper()} - {len(jobs)} positions")
                print("-" * 60)
                
                for i, job in enumerate(jobs, 1):
                    is_new = job['title'] in new_titles
                    new_indicator = " 🆕" if is_new else ""
                    
                    print(f"{i}. {job['title']}{new_indicator}")
                    print(f"   📍 Location: {job['location']}")
                    if job.get('apply_link'):
                        print(f"   🔗 Apply: {job['apply_link']}")
                    print()
    
    def create_email_content(self, all_jobs: Dict[str, List[Dict[str, str]]], 
                           new_jobs: Dict[str, List[Dict[str, str]]] = None,
                           removed_jobs: Dict[str, List[Dict[str, str]]] = None) -> str:
        """Create HTML email content with job listings."""
        total_jobs = sum(len(jobs) for jobs in all_jobs.values())
        total_new = sum(len(jobs) for jobs in new_jobs.values()) if new_jobs else 0
        total_removed = sum(len(jobs) for jobs in removed_jobs.values()) if removed_jobs else 0
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db;">
                🤖 AI Research Engineer Jobs Update
            </h2>
            <p style="color: #7f8c8d;">
                <strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                <strong>Total Positions:</strong> {total_jobs}
                {f'<br><strong>🆕 New Positions:</strong> {total_new}' if total_new > 0 else ''}
                {f'<br><strong>❎ Removed Positions:</strong> {total_removed}' if total_removed > 0 else ''}
            </p>
        """
        
        # Show new jobs first if any
        if new_jobs and total_new > 0:
            html_content += f"""
            <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #27ae60; margin-top: 0;">🆕 New Jobs ({total_new})</h3>
            """
            
            for company, jobs in new_jobs.items():
                if jobs:
                    html_content += f"""
                    <h4 style="color: #2c3e50; margin: 15px 0 10px 0;">🏢 {company}</h4>
                    """
                    
                    for job in jobs:
                        html_content += f"""
                        <div style="background-color: #ffffff; padding: 10px; margin: 10px 0; border-radius: 3px; border-left: 4px solid #27ae60;">
                            <h5 style="color: #2c3e50; margin: 0 0 5px 0;">{job['title']}</h5>
                            <p style="margin: 5px 0; color: #7f8c8d;">📍 {job['location']}</p>
                            {f'<a href="{job["apply_link"]}" style="color: #3498db; text-decoration: none;">🔗 Apply Now</a>' if job.get('apply_link') else ''}
                        </div>
                        """
            
            html_content += "</div>"

        # Show removed jobs if any
        if removed_jobs and total_removed > 0:
            html_content += f"""
            <div style="background-color: #fdecea; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #c0392b; margin-top: 0;">❎ Removed Jobs ({total_removed})</h3>
            """

            for company, jobs in removed_jobs.items():
                if jobs:
                    html_content += f"""
                    <h4 style="color: #2c3e50; margin: 15px 0 10px 0;">🏢 {company}</h4>
                    """

                    for job in jobs:
                        html_content += f"""
                        <div style="background-color: #ffffff; padding: 10px; margin: 10px 0; border-radius: 3px; border-left: 4px solid #c0392b;">
                            <h5 style="color: #2c3e50; margin: 0 0 5px 0;">{job.get('title', 'Unknown Title')}</h5>
                            <p style="margin: 5px 0; color: #7f8c8d;">📍 {job.get('location', 'Unknown')}</p>
                            {f'<span style="color: #c0392b;">This role no longer appears on the board.</span>'}
                        </div>
                        """

            html_content += "</div>"
        
        # Show all jobs by company
        html_content += f"""
            <h3 style="color: #2c3e50;">📋 All Research Engineer Positions ({total_jobs})</h3>
        """
        
        for company, jobs in all_jobs.items():
            if jobs:
                company_new = new_jobs.get(company, []) if new_jobs else []
                new_titles = {job['title'] for job in company_new}
                
                html_content += f"""
                <h4 style="color: #2c3e50; margin: 25px 0 15px 0; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
                    🏢 {company} - {len(jobs)} positions
                </h4>
                """
                
                for i, job in enumerate(jobs, 1):
                    is_new = job['title'] in new_titles
                    border_color = "#27ae60" if is_new else "#3498db"
                    new_indicator = " 🆕" if is_new else ""
                    
                    html_content += f"""
                    <div style="background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid {border_color};">
                        <h5 style="color: #2c3e50; margin: 0 0 8px 0;">{i}. {job['title']}{new_indicator}</h5>
                        <p style="margin: 5px 0; color: #7f8c8d;">📍 Location: {job['location']}</p>
                        {f'<a href="{job["apply_link"]}" style="color: #3498db; text-decoration: none; font-weight: bold;">🔗 Apply Now</a>' if job.get('apply_link') else ''}
                    </div>
                    """
        
        html_content += """
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #bdc3c7;">
            <p style="color: #95a5a6; font-size: 12px; text-align: center;">
                This email was automatically generated by the AI Jobs Scraper<br>
                Monitoring: Anthropic • OpenAI • DeepMind • X.ai • ByteDance Seed • Thinking Machines<br>
                If you no longer wish to receive these updates, please update your configuration.
            </p>
        </body>
        </html>
        """
        
        return html_content
    
    def send_email(self, all_jobs: Dict[str, List[Dict[str, str]]], 
                  new_jobs: Dict[str, List[Dict[str, str]]] = None,
                  removed_jobs: Dict[str, List[Dict[str, str]]] = None) -> bool:
        """Send email with job listings."""
        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            print("❌ Email configuration incomplete. Please set up environment variables.")
            return False
        
        total_jobs = sum(len(jobs) for jobs in all_jobs.values())
        total_new = sum(len(jobs) for jobs in new_jobs.values()) if new_jobs else 0
        total_removed = sum(len(jobs) for jobs in removed_jobs.values()) if removed_jobs else 0
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            subject = f"🤖 AI Research Jobs - {total_jobs} positions"
            if total_new > 0:
                subject += f" ({total_new} new!)"
            if total_removed > 0:
                subject += f" ({total_removed} removed)"
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Create HTML content
            html_content = self.create_email_content(all_jobs, new_jobs, removed_jobs)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ Email sent successfully to {self.recipient_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False
    
    def save_to_file(self, all_jobs: Dict[str, List[Dict[str, str]]], 
                    filename: str = "ai_research_jobs.txt") -> None:
        """Save the results to a text file."""
        try:
            total_jobs = sum(len(jobs) for jobs in all_jobs.values())
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"AI Research Engineer Jobs - {total_jobs} positions\n")
                f.write("=" * 60 + "\n\n")
                
                for company, jobs in all_jobs.items():
                    if jobs:
                        f.write(f"{company.upper()} - {len(jobs)} positions\n")
                        f.write("-" * 40 + "\n")
                        
                        for i, job in enumerate(jobs, 1):
                            f.write(f"{i}. {job['title']}\n")
                            f.write(f"   Location: {job['location']}\n")
                            if job.get('apply_link'):
                                f.write(f"   Apply: {job['apply_link']}\n")
                            f.write("\n")
                        
                        f.write("\n")
            
            print(f"\n💾 Results saved to: {filename}")
            
        except Exception as e:
            print(f"Error saving to file: {e}")
    
    def run(self, send_email: bool = False) -> None:
        """Main method to run the multi-company scraper."""
        print("🤖 AI Jobs Scraper - Research Engineer Positions")
        print("🏢 Companies: Anthropic, OpenAI, DeepMind, X.ai, ByteDance Seed, Thinking Machines")
        print("=" * 60)
        
        # Scrape all companies
        all_jobs = self.scrape_all_companies()
        
        # Load previous jobs and find new ones
        previous_jobs = self.load_previous_jobs()
        new_jobs = self.find_new_jobs(all_jobs, previous_jobs)
        removed_jobs = self.find_removed_jobs(all_jobs, previous_jobs)
        
        total_new = sum(len(jobs) for jobs in new_jobs.values())
        total_removed = sum(len(jobs) for jobs in removed_jobs.values())
        if total_new > 0:
            print(f"\n🆕 Found {total_new} new job(s)!")
        else:
            print("\nℹ️ No new jobs since last check.")

        if total_removed > 0:
            print(f"❎ {total_removed} position(s) removed since last check.")
        
        # Display results
        self.display_jobs(all_jobs, new_jobs)
        
        # Save to file
        self.save_to_file(all_jobs)
        
        # Save job history
        self.save_jobs_history(all_jobs)
        
        # Send email if requested
        if send_email:
            self.send_email(all_jobs, new_jobs if new_jobs else None, removed_jobs if removed_jobs else None)


def run_daily_scraper():
    """Function to run the scraper with email notifications."""
    print(f"\n🕐 Running scheduled AI job scraper at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    scraper = MultiCompanyJobsScraper()
    scraper.run(send_email=True)


def main():
    """Main function with options for running once or scheduling."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--schedule':
        print("🔄 Starting scheduled AI job scraper (runs daily at 9:00 AM)")
        print("📧 Email notifications enabled")
        print("🏢 Monitoring: Anthropic, OpenAI, DeepMind, X.ai, ByteDance Seed, Thinking Machines")
        print("⏹️  Press Ctrl+C to stop")
        
        # Schedule the job to run daily at 9:00 AM
        schedule.every().day.at("09:00").do(run_daily_scraper)
        
        # Run once immediately for testing
        print("🏃 Running initial scan...")
        run_daily_scraper()
        
        # Keep the script running
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\n⏹️  Scheduler stopped by user")
    
    elif len(sys.argv) > 1 and sys.argv[1] == '--email':
        print("📧 Running AI job scraper with email notification")
        scraper = MultiCompanyJobsScraper()
        scraper.run(send_email=True)
    
    else:
        # Default: run once without email
        print("🤖 Running AI job scraper once (no email)")
        print("💡 Use --email to send results via email")
        print("💡 Use --schedule to run daily with email notifications")
        scraper = MultiCompanyJobsScraper()
        scraper.run(send_email=False)


if __name__ == "__main__":
    main()