import requests
from bs4 import BeautifulSoup
import time
import hashlib
import urllib.parse
import re
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session():
    """Create a requests session with retry strategy and better headers"""
    session = requests.Session()
    
    # Add retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Rotate through different realistic User-Agents
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]
    
    session.headers.update({
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    return session


def check_for_blocking(soup, url):
    """Check if Google is blocking the request"""
    # Check for common blocking indicators
    if soup.find("title") and "blocked" in soup.find("title").text.lower():
        return True, "Request appears to be blocked by Google"
    
    if "captcha" in str(soup).lower():
        return True, "CAPTCHA detected - request blocked"
    
    # Check for the specific Google anti-bot page
    if soup.find("div", {"id": "yvlrue"}):
        return True, "Google anti-bot protection triggered"
    
    # Check if page is suspiciously small
    if len(str(soup)) < 1000:
        return True, "Response too small - likely blocked"
    
    return False, "No blocking detected"


def is_actual_hiring_post(text: str) -> bool:
    """Heuristic filter to detect real hiring announcements."""
    text_lower = text.lower()

    # ✅ Positive signals — real hiring phrases
    include_patterns = [
        r"we'?re\s+hiring",
        r"now\s+hiring",
        r"join\s+our\s+team",
        r"apply\s+now",
        r"hiring\s+(engineer|developer|manager|intern|designer|scientist|analyst|role|position)",
        r"open\s+position",
        r"career\s+opportunit",
    ]

    # 🚫 Negative signals — news, trends, or analysis
    exclude_patterns = [
        r"hiring\s+space",
        r"hiring\s+trend",
        r"hiring\s+platform",
        r"hiring\s+report",
        r"hiring\s+news",
        r"launche[sd]",
        r"rival\s+to",
        r"analysis",
        r"survey",
        r"study",
        r"statistic",
    ]

    if any(re.search(p, text_lower) for p in include_patterns) and not any(
        re.search(p, text_lower) for p in exclude_patterns
    ):
        return True
    return False


def monitor_company_hiring(companies, interval=3600, max_retries=3):
    """
    Periodically searches Google for LinkedIn posts mentioning hiring at specific companies.
    
    Args:
        companies: List of company names to monitor
        interval: Time in seconds between checks (default: 1 hour)
        max_retries: Maximum consecutive blocks before giving up (default: 3)
    
    Example: monitor_company_hiring(["Apple", "Google", "Amazon"], interval=1800)
    
    Note: Google may block automated requests. Consider:
    - Using a VPN to change IP address
    - Increasing the interval between requests
    - Using LinkedIn's official API instead
    """
    base_query = (
        'site:linkedin.com/posts ("we\'re hiring" OR "now hiring" OR "join our team" '
        'OR "apply now" OR "hiring engineer" OR "hiring developer")'
    )
    company_query = " OR ".join([f'"{c}"' for c in companies])
    full_query = f"{base_query} ({company_query})"

    session = create_session()
    seen = set()

    print(f"🔎 Monitoring hiring posts for: {', '.join(companies)}")
    print("Google query URL:")
    print(f"https://www.google.com/search?q={urllib.parse.quote(full_query)}\n")

    consecutive_blocks = 0
    max_blocks = max_retries

    while True:
        print(f"🔍 Checking for new hiring posts at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Add some randomization to avoid being detected
            time.sleep(random.uniform(2, 5))
            
            url = f"https://www.google.com/search?q={urllib.parse.quote(full_query)}"
            response = session.get(url, timeout=30)
            
            print(f"Response status: {response.status_code}")
            print(f"Response size: {len(response.text)} bytes")
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Check if we're being blocked
            is_blocked, block_reason = check_for_blocking(soup, url)
            if is_blocked:
                print(f"⚠️  {block_reason}")
                consecutive_blocks += 1
                
                if consecutive_blocks >= max_blocks:
                    print(f"❌ Too many consecutive blocks ({consecutive_blocks}). Try:")
                    print("   1. Use a VPN")
                    print("   2. Increase the interval time")
                    print("   3. Try searching manually to solve any CAPTCHA")
                    print(f"   4. Visit this URL manually: {url}")
                    break
                else:
                    wait_time = 300 * consecutive_blocks  # Exponential backoff
                    print(f"   Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
            else:
                consecutive_blocks = 0  # Reset counter on success
            
            # Try multiple selectors for Google search results
            selectors_to_try = [
                "div.tF2Cxc",  # Current Google format
                "div.g",       # Older Google format
                ".g",          # Alternative
                "div[data-ved]"  # Results with data-ved attribute
            ]
            
            results_found = False
            for selector in selectors_to_try:
                results = soup.select(selector)
                if results:
                    print(f"✅ Found {len(results)} results using selector: {selector}")
                    results_found = True
                    break
                else:
                    print(f"❌ No results with selector: {selector}")
            
            if not results_found:
                print("⚠️  No search results found with any selector. Google may have changed their HTML structure.")
                print("Raw HTML snippet:")
                print(str(soup)[:500] + "...")
                time.sleep(interval)
                continue

            new_posts = []
            for i, result in enumerate(results[:10]):  # Limit to first 10 results
                print(f"\n--- Processing result {i+1} ---")
                
                # Try different selectors for title, link, and snippet
                title_selectors = ["h3", ".LC20lb", ".DKV0Md"]
                link_selectors = ["a", "a[href*='linkedin']"]
                snippet_selectors = [".VwiC3b", ".s", ".st"]
                
                title_tag = None
                for ts in title_selectors:
                    title_tag = result.select_one(ts)
                    if title_tag:
                        break
                
                link_tag = None
                for ls in link_selectors:
                    link_tag = result.select_one(ls)
                    if link_tag and link_tag.get("href"):
                        break
                
                snippet_tag = None
                for ss in snippet_selectors:
                    snippet_tag = result.select_one(ss)
                    if snippet_tag:
                        break
                
                print(f"Title found: {'✅' if title_tag else '❌'}")
                print(f"Link found: {'✅' if link_tag else '❌'}")
                print(f"Snippet found: {'✅' if snippet_tag else '❌'}")
                
                if not (title_tag and link_tag):
                    print("Skipping - missing required elements")
                    continue

                title = title_tag.text.strip()
                link = link_tag["href"]
                snippet = snippet_tag.text.strip() if snippet_tag else ""
                
                print(f"Title: {title[:100]}...")
                print(f"Link: {link}")
                print(f"Snippet: {snippet[:100]}...")
                
                # Skip non-LinkedIn links
                if "linkedin.com" not in link:
                    print("Skipping - not a LinkedIn link")
                    continue
                
                combined_text = f"{title} {snippet}"

                # ✅ Apply hiring intent filter
                if not is_actual_hiring_post(combined_text):
                    print("Skipping - doesn't match hiring intent")
                    continue

                uid = hashlib.md5(link.encode()).hexdigest()
                if uid not in seen:
                    seen.add(uid)
                    new_posts.append((title, link, snippet))
                    print("✅ Added as new hiring post!")
                else:
                    print("Skipping - already seen")

            if new_posts:
                print(f"\n🆕 Found {len(new_posts)} new real hiring posts:")
                for title, link, snippet in new_posts:
                    print(f"- {title}\n  {link}\n  → {snippet}\n")
            else:
                print("\n📭 No new hiring posts found this round.")

        except requests.RequestException as e:
            print(f"❌ Request error: {e}")
            consecutive_blocks += 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()

        print(f"⏳ Waiting {interval/60:.1f} minutes before next check...\n")
        time.sleep(interval)


if __name__ == "__main__":
    # 👇 Edit this list to track your target companies
    monitor_company_hiring(["Apple", "Google", "Amazon"], interval=1800)
