# 🤖 AI Jobs Scraper - Research Engineer Positions

A Python web scraper that monitors multiple AI companies' careers pages (Anthropic, OpenAI) for research engineer positions and can send daily email updates with new job listings.

## ✨ Features

- **Smart Filtering**: Finds research engineer positions using keyword matching
- **Blacklist Support**: Excludes unwanted job types (Safeguards, Recruiting, Operations, Management, etc.)
- **Email Notifications**: Send beautiful HTML email reports with job listings
- **New Job Detection**: Tracks and highlights newly posted positions
- **Daily Scheduling**: Run automatically once per day
- **Multiple Output Formats**: Console output, text file, and email

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install requests beautifulsoup4 lxml schedule python-dotenv
```

### 2. Configure Email (Optional)
Edit the `.env` file with your email settings:
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECIPIENT_EMAIL=recipient@example.com
```

**For Gmail users:**
1. Enable 2-factor authentication
2. Generate an App Password: https://support.google.com/accounts/answer/185833
3. Use the App Password in the `SENDER_PASSWORD` field

### 3. Run the Scraper

**Run once (no email):**
```bash
python3 ai_jobs_scraper.py
```

**Run once with email:**
```bash
python3 ai_jobs_scraper.py --email
```

**Run daily with email notifications:**
```bash
python3 ai_jobs_scraper.py --schedule
```

## 📧 Email Features

- **HTML Format**: Beautiful, responsive email layout
- **New Job Highlighting**: New positions are highlighted in green
- **Direct Apply Links**: Click to apply directly from the email
- **Location Information**: Clear location details for each position
- **Summary Statistics**: Total positions and new job counts

## 🎯 Filtering Logic

### Included Keywords:
- research engineer
- research scientist/engineer
- machine learning engineer
- staff research engineer
- senior research engineer
- AI research
- And more...

### Blacklisted Keywords (Excluded):
- safeguards
- recruit
- operation
- manager
- biology
- scaling
- honesty
- education

## 🕐 Scheduling Options

### Option 1: Built-in Scheduler
```bash
python3 ai_jobs_scraper.py --schedule
```
Runs daily at 9:00 AM. Keep the terminal open or run in background.

### Option 2: Cron Job (Linux/Mac)
```bash
crontab -e
# Add this line to run daily at 9:00 AM:
0 9 * * * cd /path/to/scraper && python3 ai_jobs_scraper.py --email
```

### Option 3: Task Scheduler (Windows)
Create a Windows Task Scheduler job to run the scraper daily.

## 📁 Output Files

- `ai_research_jobs.txt` - Text format results
- `ai_jobs_history.json` - Job history for new job detection
- `.env` - Email configuration (create from `.env.example`)

## 🛠️ Setup Script

Run the automated setup:
```bash
./setup_scraper.sh
```

This will:
- Create email configuration file
- Test email setup
- Provide usage instructions

## 📈 Current Results

The scraper typically finds **30+ research engineer positions** across both companies, including:

### **Anthropic (15 positions):**

- **Core Research**: Interpretability, Multimodal, Pre-training
- **AI Safety**: Alignment Science, Model Welfare, Reward Models
- **Specialized**: Machine Learning (Horizons), Model Performance

### **OpenAI (17 positions):**
- **Core Research**: Human Data, Human-Centered AI, Retrieval & Search
- **Safety Systems**: Health AI, Interpretability, Safety Oversight, Trustworthy AI
- **Advanced Research**: RL/Reasoning, Training, Future of Computing
- **Leadership Roles**: Lead Research Engineer positions

### **Locations**: 
Primarily San Francisco, NYC, London, Seattle, Remote options

## 🔧 Customization

### Adding Keywords
Edit the `research_keywords` list in the `filter_research_engineer_jobs` method.

### Modifying Blacklist
Edit the `blacklist_keywords` list to exclude different job types.

### Changing Schedule
Modify the schedule time in the `main()` function:
```python
schedule.every().day.at("09:00").do(run_daily_scraper)
```

## 🐛 Troubleshooting

**Email not working?**
- Check your email credentials in `.env`
- For Gmail, ensure you're using an App Password
- Verify SMTP settings for your email provider

**No jobs found?**
- Check your internet connection
- The website structure may have changed
- Review the filtering keywords

**Scheduling issues?**
- Ensure the script keeps running for scheduled jobs
- Consider using system-level scheduling (cron/Task Scheduler)

## 📝 License

This project is for educational and personal use only. Please respect Anthropic's website terms of service and don't overload their servers.

---

**Happy job hunting! 🚀**