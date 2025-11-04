# 🤖 AI Jobs Scraper

A Python script that scrapes AI research engineer job postings from multiple companies and sends daily email updates with new positions. **Completely free deployment** on Heroku with persistent job history using GitHub Gist storage.

## 🎯 Features

- **Multi-Company Support**: Scrapes Anthropic, OpenAI, DeepMind, X.ai, ByteDance Seed, Thinking Machines
- **Smart Filtering**: Focuses on research engineer and scientist positions
- **Persistent History**: Tracks jobs across Heroku restarts using GitHub Gist (free)
- **New Job Detection**: Only highlights truly new positions (no more false positives!)
- **Email Notifications**: Sends formatted HTML emails with job updates
- **Zero Cost**: Runs completely free on Heroku with no paid addons required

## 🚀 Quick Deploy to Heroku (Free)

### Prerequisites
- Heroku account (free)
- GitHub account (free) 
- 5 minutes setup time

### 1. Get GitHub Token
```bash
# Go to: https://github.com/settings/tokens
# Create new token with 'gist' permission only
# Copy the token (starts with ghp_)
```

### 2. Deploy to Heroku
```bash
# Clone and deploy
git clone <this-repo>
cd job_scraper

# Create Heroku app
heroku create your-app-name

# Set GitHub token for persistent storage
heroku config:set GITHUB_TOKEN=ghp_your_token_here

# Optional: Set email notifications  
heroku config:set SENDER_EMAIL=your-email@gmail.com
heroku config:set SENDER_PASSWORD=your-app-password
heroku config:set RECIPIENT_EMAIL=recipient@gmail.com

# Deploy
git push heroku main
```

### 3. Schedule Daily Runs
```bash
# Add free scheduler
heroku addons:create scheduler:standard

# Open scheduler dashboard
heroku addons:open scheduler

# Add job in web interface:
# Command: python ai_jobs_scraper.py --email  
# Frequency: Daily at 9:00 AM UTC
```

## 💰 Cost Breakdown
- **Heroku App**: FREE
- **GitHub Gist Storage**: FREE  
- **Scheduler**: FREE
- **Total**: $0/month 🎉

## 🔧 Local Development

### Setup
```bash
pip install -r requirements.txt

# Optional: Set GitHub token for persistent history
export GITHUB_TOKEN=ghp_your_token_here
```

### Run Commands
```bash
# Run once (console output only)
python ai_jobs_scraper.py

# Run with email notifications
python ai_jobs_scraper.py --email

# Run with built-in scheduling (for testing)
python ai_jobs_scraper.py --schedule
```

## � How Persistent Storage Works

### The Problem (Before)
```
Day 1: Scrape 15 jobs → All marked "NEW" ✨
Heroku restart (every 24h) → History file lost 
Day 2: Same 15 jobs → All marked "NEW" again ❌
```

### The Solution (After)  
```
Day 1: Scrape 15 jobs → All marked "NEW" ✨ → Save to GitHub Gist
Heroku restart → Gist persists in cloud ☁️
Day 2: Same 15 jobs → Load from Gist → 0 marked "NEW" ✅
Day 3: 1 new job appears → Only that 1 marked "NEW" ✅
```

## 🏢 Supported Companies

| Company | Jobs Scraped | Method |
|---------|--------------|--------|
| **Anthropic** | Research positions | HTML scraping |
| **OpenAI** | Research positions | Ashby API |
| **DeepMind** | All positions | Greenhouse API |
| **X.ai** | All positions | Greenhouse API |
| **ByteDance Seed** | Research positions | Multi-page scraping |
| **Thinking Machines** | All positions | Greenhouse API |

## 📧 Email Output Example

```html
🤖 AI Research Engineer Jobs Update
📅 2024-11-04 | 📊 Total: 23 positions | 🆕 New: 2

🆕 NEW JOBS (2)
├─ OpenAI: AI Safety Engineer (San Francisco)
└─ Anthropic: Research Engineer (Remote)

📋 ALL POSITIONS BY COMPANY
🏢 OPENAI - 8 positions
├─ Research Engineer
├─ Senior Research Scientist  
├─ AI Safety Engineer 🆕
└─ ...

🏢 ANTHROPIC - 6 positions  
├─ Constitutional AI Research Engineer 🆕
├─ Research Scientist
└─ ...
```

## �️ Configuration

### Required (for persistence)
```bash
GITHUB_TOKEN=ghp_your_token_here  # GitHub personal access token
```

### Optional (for email)  
```bash
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@gmail.com
```

### Gmail Setup
1. Enable 2FA on Gmail
2. Generate App Password: https://myaccount.google.com/apppasswords  
3. Use app password (not regular Gmail password)

## 📁 Project Structure

```
job_scraper/
├── 📄 ai_jobs_scraper.py     # Main scraper with all company integrations
├── 📄 simple_storage.py      # GitHub Gist storage for persistence  
├── � requirements.txt       # Python dependencies
├── 📄 Procfile              # Heroku configuration
├── 📄 runtime.txt           # Python version
├── 📄 GITHUB_TOKEN_GUIDE.md # Setup instructions
└── � README.md             # This file
```

## 🔍 Job Filtering Logic

### Included Keywords
```python
research_keywords = [
    'research engineer', 'research scientist',
    'machine learning engineer', 'ml engineer', 
    'ai research', 'staff research engineer',
    'member of technical staff'
]
```

### Excluded Keywords (to filter out non-research roles)
```python
blacklist_keywords = [
    'recruiter', 'sales', 'marketing', 'business',
    'security', 'legal', 'finance', 'manager'
]
```

## � Troubleshooting

### Storage Issues
```bash
# Check if GitHub token is set
heroku config -a your-app-name

# View logs for gist creation
heroku logs --tail -a your-app-name

# Look for: "Created new gist: abc123..."
# Then set: heroku config:set GITHUB_GIST_ID=abc123
```

### Email Issues
```bash
# Test email locally
python ai_jobs_scraper.py --email

# Common fixes:
# - Use Gmail app password, not regular password
# - Check spam folder
# - Verify environment variables are set
```

### Heroku Issues  
```bash
# View recent logs
heroku logs --lines=100 -a your-app-name

# Restart app
heroku restart -a your-app-name

# Check config
heroku config -a your-app-name
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b new-feature`
3. Test changes locally
4. Submit pull request

### Adding New Companies
Extend the scraper by adding new company classes following the existing patterns.

## ⚖️ Legal & Ethics

- Respects robots.txt and rate limits
- Only scrapes publicly available job listings  
- No personal data collection
- Educational and personal use

## 📝 License

MIT License - See LICENSE file for details.

---

🎯 **Result**: Never miss a new AI research job opening again, with zero monthly costs!