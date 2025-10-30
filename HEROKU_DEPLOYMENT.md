# Secure Heroku Deployment Guide for AI Jobs Scraper

## 🔐 Security Best Practices

Your email credentials are now protected using Heroku's secure config vars instead of being stored in your code.

## 📋 Prerequisites

1. Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
2. Git repository initialized
3. Heroku account created

## 🚀 Deployment Steps

### 1. Login to Heroku
```bash
heroku login
```

### 2. Create a new Heroku app
```bash
heroku create your-ai-jobs-scraper
# Replace 'your-ai-jobs-scraper' with your desired app name
```

### 3. Set up secure environment variables (CONFIG VARS)
**NEVER put your actual credentials in code or commit them to git!**

```bash
# Set your email configuration securely
heroku config:set SENDER_EMAIL="your-email@gmail.com"
heroku config:set SENDER_PASSWORD="your-app-password"
heroku config:set RECIPIENT_EMAIL="recipient@gmail.com"
heroku config:set SMTP_SERVER="smtp.gmail.com"
heroku config:set SMTP_PORT="587"
```

### 4. Deploy your application
```bash
# Add all files to git (your .env file is excluded by .gitignore)
git add .
git commit -m "Initial deployment to Heroku"

# Push to Heroku
git push heroku main
```

### 5. Scale your worker process
```bash
# Start the worker process (this runs your scheduled scraper)
heroku ps:scale worker=1
```

## 🔧 Managing Your App

### View logs
```bash
heroku logs --tail
```

### Check running processes
```bash
heroku ps
```

### Update config vars
```bash
# View current config vars
heroku config

# Update a config var
heroku config:set RECIPIENT_EMAIL="new-email@example.com"
```

### Stop/Start the scraper
```bash
# Stop
heroku ps:scale worker=0

# Start
heroku ps:scale worker=1
```

## 📧 Gmail App Password Setup

For Gmail, you'll need to use an "App Password" instead of your regular password:

1. Go to your Google Account settings
2. Select "Security" 
3. Under "Signing in to Google," select "2-Step Verification" (set this up if not already)
4. At the bottom of the page, select "App passwords"
5. Generate an app password for "Mail"
6. Use this 16-character password as your `SENDER_PASSWORD`

## 🎯 How It Works

- Your scraper runs as a **worker process** on Heroku
- It runs daily at 9:00 AM (scheduled)
- Email credentials are stored securely in Heroku's config vars
- The `.env` file is excluded from git, keeping your local development secure
- Heroku automatically provides the environment variables to your app

## 💰 Cost Information

- Heroku Free tier: No longer available
- Eco Dyno: $5/month (sleeps after 30min of inactivity)
- Basic Dyno: $7/month (never sleeps)

For a scheduled job like this, the Eco dyno should be sufficient.

## 🔍 Monitoring

You can monitor your scraper through:
- Heroku dashboard: https://dashboard.heroku.com/apps/your-app-name
- Heroku CLI: `heroku logs --tail`
- Email notifications (if configured)

## 🛠️ Troubleshooting

### Common Issues:

1. **App not starting**: Check `heroku logs --tail` for errors
2. **Email not sending**: Verify config vars with `heroku config`
3. **Scraper not running**: Ensure worker is scaled: `heroku ps:scale worker=1`

### Debug commands:
```bash
# Check if config vars are set
heroku config

# See running processes
heroku ps

# View recent logs
heroku logs --tail

# Restart the app
heroku restart
```

## 🔄 Updating Your App

When you make changes to your code:

```bash
git add .
git commit -m "Update scraper"
git push heroku main
```

The app will automatically redeploy with your changes.

---

**Remember**: Your credentials are now safely stored in Heroku's secure config vars and will never appear in your code or git history! 🔐