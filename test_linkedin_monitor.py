import requests
from bs4 import BeautifulSoup
import urllib.parse

# Test the Google search functionality
def test_google_search():
    companies = ["Apple"]
    base_query = (
        'site:linkedin.com/posts ("we\'re hiring" OR "now hiring" OR "join our team" '
        'OR "apply now" OR "hiring engineer" OR "hiring developer")'
    )
    company_query = " OR ".join([f'"{c}"' for c in companies])
    full_query = f"{base_query} ({company_query})"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"https://www.google.com/search?q={urllib.parse.quote(full_query)}"
    
    print(f"Testing URL: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Response status: {response.status_code}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check what div classes are actually present
        all_divs = soup.find_all("div", limit=20)
        div_classes = []
        for div in all_divs:
            if div.get('class'):
                div_classes.extend(div.get('class'))
        
        print(f"Found div classes: {set(div_classes)}")
        
        # Try different selectors
        selectors_to_try = [
            "div.tF2Cxc",
            "div.g",
            "div[data-ved]",
            ".g",
            ".tF2Cxc"
        ]
        
        for selector in selectors_to_try:
            results = soup.select(selector)
            print(f"Selector '{selector}': {len(results)} results")
            
            if results:
                for i, result in enumerate(results[:3]):  # Check first 3
                    title_tag = result.select_one("h3")
                    link_tag = result.select_one("a")
                    snippet_tag = result.select_one(".VwiC3b")
                    
                    print(f"  Result {i+1}:")
                    print(f"    Title: {'Found' if title_tag else 'None'}")
                    print(f"    Link: {'Found' if link_tag else 'None'}")
                    print(f"    Snippet: {'Found' if snippet_tag else 'None'}")
                    
                    if title_tag:
                        print(f"    Title text: {title_tag.text[:100]}")
                break
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_google_search()