
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
