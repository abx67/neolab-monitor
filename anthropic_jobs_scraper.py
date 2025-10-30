#!/usr/bin/env python3
"""
Anthropic Jobs Scraper - Research Engineer Positions

This script scrapes the Anthropic careers page and extracts all research engineer 
related job postings, displaying them in a clean, organized format.
Can send results via email and run on a daily schedule.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict
import time
import smtplib
import schedule
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class AnthropicJobsScraper:
    """Scraper for Anthropic job listings focusing on research engineer positions."""
    
    def __init__(self):
        self.base_url = "https://www.anthropic.com/jobs"
        self.session = requests.Session()
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # Email configuration - load from environment variables
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')  # App password for Gmail
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # File to store previous job listings for comparison
        self.jobs_history_file = "anthropic_jobs_history.json"
        
    def fetch_page(self) -> BeautifulSoup:
        """Fetch the jobs page and return BeautifulSoup object."""
        try:
            print(f"Fetching jobs from: {self.base_url}")
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
            
        except requests.RequestException as e:
            print(f"Error fetching the page: {e}")
            return None
    
    def extract_jobs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract all job listings from the page."""
        jobs = []
        
        # Look for job titles - they appear to be in h3 tags with job titles
        job_elements = soup.find_all('h3')
        
        for job_element in job_elements:
            job_title = job_element.get_text(strip=True)
            
            # Skip if it's not a proper job title (filter out section headers)
            if not job_title or len(job_title) < 5:
                continue
                
            # Find the location (usually right after the title)
            location = ""
            location_element = job_element.find_next_sibling()
            if location_element:
                location_text = location_element.get_text(strip=True)
                # Check if this looks like a location (contains city/state patterns)
                if any(pattern in location_text.lower() for pattern in ['ca', 'ny', 'wa', 'uk', 'dc', 'remote', 'japan', 'germany', 'france']):
                    location = location_text
            
            # Find the application link
            apply_link = ""
            # Look for "Apply Now" links in the vicinity
            apply_element = job_element.find_next('a', string=re.compile(r'Apply Now', re.I))
            if apply_element and apply_element.get('href'):
                apply_link = apply_element['href']
            
            jobs.append({
                'title': job_title,
                'location': location,
                'apply_link': apply_link
            })
        
        return jobs
    
    def filter_research_engineer_jobs(self, jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter jobs to find research engineer related positions."""
        research_keywords = [
            'research engineer',
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
            'human-ai collaboration research engineer'
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
    
    def display_jobs(self, jobs: List[Dict[str, str]]) -> None:
        """Display the filtered jobs in a clean format."""
        if not jobs:
            print("No research engineer jobs found.")
            return
        
        print(f"\n{'='*80}")
        print(f"RESEARCH ENGINEER JOBS AT ANTHROPIC ({len(jobs)} positions found)")
        print(f"{'='*80}")
        
        for i, job in enumerate(jobs, 1):
            print(f"\n{i}. {job['title']}")
            print(f"   📍 Location: {job['location'] if job['location'] else 'Not specified'}")
            if job['apply_link']:
                print(f"   🔗 Apply: {job['apply_link']}")
            print("-" * 80)
    
    def run(self, send_email: bool = False) -> None:
        """Main method to run the scraper."""
        print("🔍 Anthropic Jobs Scraper - Research Engineer Positions")
        print("=" * 60)
        
        # Fetch the page
        soup = self.fetch_page()
        if not soup:
            print("Failed to fetch the jobs page. Exiting.")
            return
        
        # Extract all jobs
        print("📋 Extracting job listings...")
        all_jobs = self.extract_jobs(soup)
        print(f"Found {len(all_jobs)} total job listings")
        
        # Filter for research engineer positions
        print("🔬 Filtering for research engineer positions...")
        research_jobs = self.filter_research_engineer_jobs(all_jobs)
        
        # Check for new jobs
        previous_jobs = self.load_previous_jobs()
        new_jobs = self.find_new_jobs(research_jobs, previous_jobs)
        
        if new_jobs:
            print(f"🆕 Found {len(new_jobs)} new job(s)!")
        else:
            print("ℹ️ No new jobs since last check.")
        
        # Display results
        self.display_jobs(research_jobs)
        
        # Save to file
        self.save_to_file(research_jobs)
        
        # Save job history
        self.save_jobs_history(research_jobs)
        
        # Send email if requested
        if send_email:
            self.send_email(research_jobs, new_jobs if new_jobs else None)
    
    def save_to_file(self, jobs: List[Dict[str, str]], filename: str = "anthropic_research_jobs.txt") -> None:
        """Save the results to a text file."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Anthropic Research Engineer Jobs - {len(jobs)} positions\n")
                f.write("=" * 60 + "\n\n")
                
                for i, job in enumerate(jobs, 1):
                    f.write(f"{i}. {job['title']}\n")
                    f.write(f"   Location: {job['location'] if job['location'] else 'Not specified'}\n")
                    if job['apply_link']:
                        f.write(f"   Apply: {job['apply_link']}\n")
                    f.write("-" * 60 + "\n")
            
            print(f"\n💾 Results saved to: {filename}")
            
        except Exception as e:
            print(f"Error saving to file: {e}")
    
    def load_previous_jobs(self) -> List[Dict[str, str]]:
        """Load previously found jobs from history file."""
        try:
            if os.path.exists(self.jobs_history_file):
                with open(self.jobs_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading job history: {e}")
        return []
    
    def save_jobs_history(self, jobs: List[Dict[str, str]]) -> None:
        """Save current jobs to history file."""
        try:
            with open(self.jobs_history_file, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving job history: {e}")
    
    def find_new_jobs(self, current_jobs: List[Dict[str, str]], previous_jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Find new jobs that weren't in the previous list."""
        previous_titles = {job['title'] for job in previous_jobs}
        new_jobs = [job for job in current_jobs if job['title'] not in previous_titles]
        return new_jobs
    
    def create_email_content(self, jobs: List[Dict[str, str]], new_jobs: List[Dict[str, str]] = None) -> str:
        """Create HTML email content with job listings."""
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db;">
                🔬 Anthropic Research Engineer Jobs Update
            </h2>
            <p style="color: #7f8c8d;">
                <strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                <strong>Total Positions:</strong> {len(jobs)}
            </p>
        """
        
        if new_jobs:
            html_content += f"""
            <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #27ae60; margin-top: 0;">🆕 New Jobs ({len(new_jobs)})</h3>
            """
            
            for i, job in enumerate(new_jobs, 1):
                html_content += f"""
                <div style="background-color: #ffffff; padding: 10px; margin: 10px 0; border-radius: 3px; border-left: 4px solid #27ae60;">
                    <h4 style="color: #2c3e50; margin: 0 0 5px 0;">{job['title']}</h4>
                    <p style="margin: 5px 0; color: #7f8c8d;">📍 {job['location'] if job['location'] else 'Not specified'}</p>
                    {f'<a href="{job["apply_link"]}" style="color: #3498db; text-decoration: none;">🔗 Apply Now</a>' if job['apply_link'] else ''}
                </div>
                """
            
            html_content += "</div>"
        
        html_content += f"""
            <h3 style="color: #2c3e50;">📋 All Research Engineer Positions ({len(jobs)})</h3>
        """
        
        for i, job in enumerate(jobs, 1):
            html_content += f"""
            <div style="background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #3498db;">
                <h4 style="color: #2c3e50; margin: 0 0 8px 0;">{i}. {job['title']}</h4>
                <p style="margin: 5px 0; color: #7f8c8d;">📍 Location: {job['location'] if job['location'] else 'Not specified'}</p>
                {f'<a href="{job["apply_link"]}" style="color: #3498db; text-decoration: none; font-weight: bold;">🔗 Apply Now</a>' if job['apply_link'] else ''}
            </div>
            """
        
        html_content += """
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #bdc3c7;">
            <p style="color: #95a5a6; font-size: 12px; text-align: center;">
                This email was automatically generated by the Anthropic Jobs Scraper<br>
                If you no longer wish to receive these updates, please update your configuration.
            </p>
        </body>
        </html>
        """
        
        return html_content
    
    def send_email(self, jobs: List[Dict[str, str]], new_jobs: List[Dict[str, str]] = None) -> bool:
        """Send email with job listings."""
        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            print("❌ Email configuration incomplete. Please set up environment variables.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔬 Anthropic Research Engineer Jobs - {len(jobs)} positions"
            if new_jobs:
                msg['Subject'] += f" ({len(new_jobs)} new!)"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Create HTML content
            html_content = self.create_email_content(jobs, new_jobs)
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


def run_daily_scraper():
    """Function to run the scraper with email notifications."""
    print(f"\n🕐 Running scheduled job scraper at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    scraper = AnthropicJobsScraper()
    scraper.run(send_email=True)


def main():
    """Main function with options for running once or scheduling."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--schedule':
        print("🔄 Starting scheduled job scraper (runs daily at 9:00 AM)")
        print("📧 Email notifications enabled")
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
        print("📧 Running scraper with email notification")
        scraper = AnthropicJobsScraper()
        scraper.run(send_email=True)
    
    else:
        # Default: run once without email
        print("🔍 Running scraper once (no email)")
        print("💡 Use --email to send results via email")
        print("💡 Use --schedule to run daily with email notifications")
        scraper = AnthropicJobsScraper()
        scraper.run(send_email=False)


if __name__ == "__main__":
    main()