#!/usr/bin/env python3
"""
Simple free storage using GitHub Gist (requires GitHub account).
This is the most reliable free option since GitHub accounts are common.
"""

import os
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime


class SimpleGistStorage:
    """Simple GitHub Gist storage for job history."""
    
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.gist_id = os.getenv('GITHUB_GIST_ID')
        
        if not self.github_token:
            # Try to read from file if environment variable not set
            token_file = os.path.expanduser('~/.github_token')
            if os.path.exists(token_file):
                with open(token_file, 'r') as f:
                    self.github_token = f.read().strip()
        
        if not self.github_token:
            raise ValueError("GitHub token required. Set GITHUB_TOKEN environment variable or create ~/.github_token file")
        
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        print("✅ Using GitHub Gist free storage for job history")
    
    def save_jobs_history(self, jobs: Dict[str, List[Dict[str, str]]]) -> None:
        """Save job history to GitHub Gist."""
        data = {
            "job_history": jobs,
            "last_updated": datetime.now().isoformat(),
            "total_jobs": sum(len(company_jobs) for company_jobs in jobs.values())
        }
        
        content = json.dumps(data, indent=2, ensure_ascii=False)
        
        if not self.gist_id:
            # Create new gist
            gist_data = {
                "description": "AI Jobs Scraper - Job History",
                "public": False,
                "files": {
                    "ai_jobs_history.json": {
                        "content": content
                    }
                }
            }
            
            try:
                response = requests.post(
                    "https://api.github.com/gists",
                    json=gist_data,
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 201:
                    result = response.json()
                    self.gist_id = result['id']
                    print(f"✅ Created new gist: {self.gist_id}")
                    print(f"💡 Set GITHUB_GIST_ID={self.gist_id} to reuse this gist")
                    print(f"✅ Saved {data['total_jobs']} jobs to new gist")
                else:
                    print(f"❌ Failed to create gist: {response.status_code}")
                    print(f"   Response: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error creating gist: {e}")
        else:
            # Update existing gist
            gist_update = {
                "files": {
                    "ai_jobs_history.json": {
                        "content": content
                    }
                }
            }
            
            try:
                response = requests.patch(
                    f"https://api.github.com/gists/{self.gist_id}",
                    json=gist_update,
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"✅ Updated gist with {data['total_jobs']} jobs")
                else:
                    print(f"❌ Failed to update gist: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error updating gist: {e}")
    
    def load_previous_jobs(self) -> Dict[str, List[Dict[str, str]]]:
        """Load job history from GitHub Gist."""
        if not self.gist_id:
            print("ℹ️ No gist ID - treating as first run")
            return {}
        
        try:
            response = requests.get(
                f"https://api.github.com/gists/{self.gist_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                gist_data = response.json()
                file_content = gist_data['files']['ai_jobs_history.json']['content']
                data = json.loads(file_content)
                job_history = data.get('job_history', {})
                total_jobs = sum(len(jobs) for jobs in job_history.values())
                print(f"✅ Loaded {total_jobs} jobs from gist")
                return job_history
            else:
                print(f"⚠️ Could not load gist: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"⚠️ Error loading gist: {e}")
            return {}


def create_github_token_guide():
    """Create a simple guide for getting a GitHub token."""
    guide = """
# 🔑 How to Get a GitHub Personal Access Token (Free)

## Step 1: Go to GitHub Settings
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"

## Step 2: Configure Token
1. **Note**: "AI Jobs Scraper Token"
2. **Expiration**: "No expiration" or "1 year"
3. **Scopes**: Check only "gist" (nothing else needed)

## Step 3: Copy Token
1. Click "Generate token"
2. Copy the token (starts with `ghp_`)
3. ⚠️ Save it somewhere - you won't see it again!

## Step 4: Set Token Locally
```bash
# Option A: Environment variable
export GITHUB_TOKEN=ghp_your_token_here

# Option B: Save to file
echo "ghp_your_token_here" > ~/.github_token
```

## Step 5: Set Token on Heroku
```bash
heroku config:set GITHUB_TOKEN=ghp_your_token_here -a your-app-name
```

✅ Your token allows the scraper to create/update private gists for job storage.
🆓 GitHub gives you unlimited private gists for free!
"""
    
    with open('GITHUB_TOKEN_GUIDE.md', 'w') as f:
        f.write(guide)
    
    print("📝 Created GITHUB_TOKEN_GUIDE.md with setup instructions")


def get_simple_storage():
    """Get GitHub Gist storage or None if not available."""
    try:
        return SimpleGistStorage()
    except ValueError as e:
        print(f"⚠️ GitHub Gist storage not available: {e}")
        print("💡 Run this to create token guide: python -c \"from simple_storage import create_github_token_guide; create_github_token_guide()\"")
        return None
    except Exception as e:
        print(f"❌ Error initializing storage: {e}")
        return None


if __name__ == "__main__":
    # Test the storage
    print("🧪 Testing Simple GitHub Gist Storage...")
    
    storage = get_simple_storage()
    if not storage:
        create_github_token_guide()
        print("\n📖 Check GITHUB_TOKEN_GUIDE.md for setup instructions")
    else:
        # Test with sample data
        test_jobs = {
            "TestCompany": [
                {"title": "Test Job 1", "location": "SF", "apply_link": "https://example.com/1"}
            ]
        }
        
        print("💾 Testing save...")
        storage.save_jobs_history(test_jobs)
        
        print("📖 Testing load...")
        loaded = storage.load_previous_jobs()
        
        if loaded == test_jobs:
            print("✅ Storage test PASSED!")
        else:
            print("❌ Storage test failed")
            print(f"Expected: {test_jobs}")
            print(f"Got: {loaded}")