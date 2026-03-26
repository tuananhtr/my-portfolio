import time
import random
import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import re 
from sqlalchemy import create_engine
from datetime import datetime, timedelta

# ==========================================
# --- BACKFILL CONFIGURATION ---
# ==========================================

# 1. Type the exact dates you want to backfill here (Format: DD/MM/YYYY)
TARGET_DATES = ["21/03/2026","22/03/2026","23/03/2026"]

# 2. Set this HIGH (e.g., 100-200) because old posts are buried deep!
NUM_PAGES_TO_SCAN = 100 

DB_URL = r"sqlite:///C:\Users\Admin\Desktop\my_portfolio\my-portfolio\real_estate_crawl\bds_data.db"
# ==========================================

engine = create_engine(DB_URL)

def is_target_date(date_str, target_dates):
    """Checks if the scraped date matches any date in your TARGET_DATES list"""
    if not date_str or date_str == "N/A": 
        return False
        
    date_str = date_str.lower()
    
    # Calculate what today and yesterday actually are in DD/MM/YYYY
    today_str = datetime.now().strftime("%d/%m/%Y")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    
    parsed_date = ""
    
    # Convert Vietnamese relative terms to actual dates
    if "hôm nay" in date_str or "giờ" in date_str or "phút" in date_str:
        parsed_date = today_str
    elif "hôm qua" in date_str:
        parsed_date = yesterday_str
    else:
        # Extract standard DD/MM/YYYY formats
        match = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', date_str)
        if match:
            day = match.group(1).zfill(2)
            month = match.group(2).zfill(2)
            year = match.group(3)
            parsed_date = f"{day}/{month}/{year}"
            
    # Check if the calculated date is in your target list
    return parsed_date in target_dates


def get_listing_urls(driver, page_num):
    base_url = "https://batdongsan.com.vn/ban-can-ho-chung-cu-tp-hcm"
    url = base_url if page_num == 1 else f"{base_url}/p{page_num}"
    
    print(f"\n--- Scanning Page {page_num}: {url} ---")
    driver.get(url)
    
    if page_num == 1:
        print("Waiting 15s for Cloudflare check...")
        time.sleep(15)
    else:
        time.sleep(random.uniform(3, 5))

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    cards = soup.select('.js-product-item')
    if not cards:
        cards = soup.select('.re__card-full')

    links = []
    for card in cards:
        link_tag = card.select_one('a')
        if link_tag and link_tag.get('href'):
            full_link = f"https://batdongsan.com.vn{link_tag['href']}"
            links.append(full_link)
    
    print(f"Found {len(links)} links on page {page_num}.")
    return links


def parse_detail_page(driver, url):
    print(f"Crawling: {url} ... ", end="")
    try:
        driver.get(url)
        time.sleep(random.uniform(3, 6))
    except Exception:
        print("Error loading page (Timeout/Broken)")
        return None
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    html = driver.page_source
    
    info = {
        "dt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        "URL": url, "Title": "N/A", "Product_ID": "N/A", "Price_Raw": "N/A",   
        "Price_per_m2": "N/A", "Area_Raw": "N/A", "Posted_Date": "N/A", 
        "Address": "N/A", "Latitude": "N/A", "Longitude": "N/A",   
        "Bedrooms": "N/A", "Bathrooms": "N/A", "Direction": "N/A",
        "Balcony": "N/A", "Legal": "N/A", "Project_Name": "N/A", "Project_Developer": "N/A",
    }

    title_elem = soup.select_one('.pr-title') or soup.select_one('.re__pr-title')
    if title_elem: info['Title'] = title_elem.text.strip()

    address_elem = soup.select_one('.js__pr-address') or soup.select_one('.re__pr-short-description')
    if address_elem: info['Address'] = address_elem.text.strip()

    spec_items = soup.select('.re__pr-specs-content-item')
    for item in spec_items:
        title_span = item.select_one('.re__pr-specs-content-item-title')
        value_span = item.select_one('.re__pr-specs-content-item-value')
        if title_span and value_span:
            label = title_span.text.strip().lower()
            value = value_span.text.strip()
            if "mức giá" in label or "khoảng giá" in label: info['Price'] = value
            elif "diện tích" in label: info['Area'] = value
            elif "phòng ngủ" in label: info['Bedrooms'] = value
            elif "tắm" in label or "vệ sinh" in label: info['Bathrooms'] = value
            elif "hướng nhà" in label: info['Direction'] = value
            elif "hướng ban công" in label: info['Balcony'] = value
            elif "pháp lý" in label: info['Legal'] = value

    short_infos = soup.select('.re__pr-short-info-item')
    for item in short_infos:
        title = item.select_one('.title')
        value = item.select_one('.value')
        if title and value and "ngày đăng" in title.text.strip().lower():
            info['Posted_Date'] = value.text.strip()
            
    project_box = soup.select_one('.re__project-infor')
    if not project_box:
        headers = soup.find_all(['h3', 'div'], string=re.compile('Thông tin dự án'))
        if headers:
            project_box = headers[0].find_parent('div', class_=re.compile('project')) or headers[0].parent

    if project_box:
        p_name = project_box.select_one('.re__project-title') or project_box.find('div', class_=re.compile('title'))
        if p_name: info['Project_Name'] = p_name.text.strip()

        p_investor = project_box.select_one('[class*="investor-name"]') or project_box.select_one('[class*="investor"]')
        if p_investor: info['Project_Developer'] = p_investor.text.strip()

        p_status = project_box.select_one('[class*="status"]')
        if p_status: info['Project_Status'] = p_status.text.strip()

    lat_match = re.search(r'latitude\s*:\s*([0-9\.]+)', html)
    long_match = re.search(r'longitude\s*:\s*([0-9\.]+)', html)
    if lat_match: info['Latitude'] = lat_match.group(1)
    if long_match: info['Longitude'] = long_match.group(1)

    pid_match = re.search(r'productId\s*:\s*(\d+)', html)
    if pid_match: info['Product_ID'] = pid_match.group(1)
    price_match = re.search(r'price\s*:\s*(\d+)', html)
    if price_match: info['Price_Raw'] = price_match.group(1)
    m2_match = re.search(r'pricePerM2\s*:\s*(\d+)', html)
    if m2_match: info['Price_per_m2'] = m2_match.group(1)
    area_match = re.search(r'area\s*:\s*(\d+)', html)
    if area_match: info['Area_Raw'] = area_match.group(1)

    print(f"Parsed. Date: {info.get('Posted_Date', 'Unknown')}")
    return info


def main():
    print(f"=== BACKFILL SCRIPT INITIATED ===")
    print(f"Target Dates to Backfill: {TARGET_DATES}")
    
    scraped_urls = set()
    try:
        existing_data = pd.read_sql("SELECT URL FROM listings", con=engine)
        scraped_urls = set(existing_data["URL"].tolist())
        print(f"Found {len(scraped_urls)} total items already in the database.")
    except Exception:
        print("Database not found. Starting fresh.")

    print("Launching browser...")
    options = uc.ChromeOptions()
    
    # Chrome version fix included!
    driver = uc.Chrome(options=options, version_main=146)
    driver.set_page_load_timeout(45)

    all_urls = []

    try:
        # Phase 1: Collect URLs
        for page in range(1, NUM_PAGES_TO_SCAN + 1):
            urls = get_listing_urls(driver, page)
            all_urls.extend(urls)
        
        all_urls = list(set(all_urls))
        urls_to_scrape = [u for u in all_urls if u not in scraped_urls]
        
        print(f"\n--- Total URLs found on {NUM_PAGES_TO_SCAN} pages: {len(all_urls)}")
        print(f"--- Already in DB: {len(scraped_urls)}")
        print(f"--- Remaining to Check: {len(urls_to_scrape)}")
        
        if len(urls_to_scrape) == 0:
            print("No new URLs to check. Exiting.")
            return

        print("\nStarting Phase 2: Deep Crawling for Target Dates...")

        for i, link in enumerate(urls_to_scrape):
            print(f"[{i+1}/{len(urls_to_scrape)}] ", end="")
            try:
                details = parse_detail_page(driver, link)
                
                if details:
                    # --- THE BACKFILL FILTER ---
                    if not is_target_date(details.get("Posted_Date"), TARGET_DATES):
                        print(" -> Skipped (Not in target dates)")
                        continue 
                    
                    print(" -> VALID TARGET DATE! Saving to DB...")
                    
                    df_row = pd.DataFrame([details])
                    cols = [
                        "dt", "Title", "Address", "Price", "Product_ID", "Price_Raw", 
                        "Latitude", "Longitude", "Area_Raw", "Price_per_m2", 
                        "Posted_Date", "Area", "Project_Name", "Project_Developer", 
                        "Project_Status", "Bedrooms", "Bathrooms", "Direction", 
                        "Balcony", "Legal", "URL"
                    ]
                    final_cols = [c for c in cols if c in df_row.columns]
                    df_row = df_row[final_cols]
                    df_row.to_sql('listings', con=engine, if_exists='append', index=False)
                    
            except Exception as e:
                print(f"Error saving data: {e}")
                if "invalid session" in str(e).lower():
                    print("Browser Session Lost. Stopping script.")
                    break
                continue

    finally:
        try:
            driver.quit()
        except:
            pass
        print(f"\nBackfill complete! Data stored in '{DB_URL}'")

if __name__ == "__main__":
    main()