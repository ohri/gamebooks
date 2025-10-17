"""
NFL Gamebook Downloader
Automates login and download of NFL gamebook PDFs for a specified week
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import glob
import argparse
from datetime import datetime, timedelta

def get_current_nfl_week():
    """Calculate current NFL week based on season start date."""
    # NFL 2024 season started September 5, 2024 (Thursday)
    season_start = datetime(2024, 9, 5)
    current_date = datetime.now()

    if current_date < season_start:
        return 1

    days_since_start = (current_date - season_start).days
    week = (days_since_start // 7) + 1

    # Cap at week 18 (regular season)
    return min(week, 18)

# Parse command line arguments
parser = argparse.ArgumentParser(description='Download NFL gamebooks for a specific week')
parser.add_argument('--week', '-w', type=int, default=None,
                    help='Week number to download (1-18). Defaults to current week.')
args = parser.parse_args()

# Determine week to download
week_number = args.week if args.week is not None else get_current_nfl_week()
print(f"Downloading gamebooks for Week {week_number}")

# Configuration
LOGIN_URL = "https://nflgsis.com/GameStatsLive/Auth/?ReturnUrl=%2FGameStatsLive%2F"
USERNAME = "media"
PASSWORD = "media"
DOWNLOAD_DIR = os.path.join(os.getcwd(), f"w{week_number}")

# Create download directory if it doesn't exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Setup Chrome options
chrome_options = Options()
prefs = {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True
}
chrome_options.add_experimental_option("prefs", prefs)

# Initialize driver
driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 10)

try:
    # Step 1: Login
    print("Navigating to login page...")
    driver.get(LOGIN_URL)

    print("Logging in...")
    # Try multiple selector strategies for the login form
    try:
        username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Username'], input[name*='user' i], input[type='text']")))
    except:
        username_field = driver.find_element(By.XPATH, "//input[@type='text' or @placeholder='Username']")

    try:
        password_field = driver.find_element(By.CSS_SELECTOR, "input[placeholder='Password'], input[name*='pass' i], input[type='password']")
    except:
        password_field = driver.find_element(By.XPATH, "//input[@type='password' or @placeholder='Password']")

    username_field.send_keys(USERNAME)
    password_field.send_keys(PASSWORD)

    try:
        login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
    except:
        login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit'], button")

    login_button.click()

    # Wait for redirect after login
    time.sleep(3)

    # Handle accept/terms page if present
    print("Checking for accept/terms page...")
    if "TermsAndConditions" in driver.current_url:
        print("On terms page, navigating to accept URL...")
        driver.get("https://nflgsis.com/GameStatsLive/Auth/AcceptTermsAndConditions/")
        # Wait for redirect to main page
        time.sleep(3)
        print(f"After accept, current URL: {driver.current_url}")

    # Step 2: Navigate to specific week
    print(f"Navigating to Week {week_number}...")
    print(f"Current URL: {driver.current_url}")

    # Wait for page to load
    time.sleep(2)

    # Click on the specific week number in the selector
    try:
        # First, make sure we're on the REG (regular season) tab
        reg_button = driver.find_element(By.XPATH, "//div[text()='REG']")
        if reg_button:
            driver.execute_script("arguments[0].click();", reg_button)
            time.sleep(1)
            print("  Clicked on REG tab")
    except:
        print("  REG tab already selected or not found")

    # Find and click the week number (it's a div element with data-bind)
    try:
        week_selector = wait.until(EC.element_to_be_clickable((By.XPATH, f"//div[@data-bind and text()='{week_number}']")))
        driver.execute_script("arguments[0].click();", week_selector)
        print(f"  Clicked on Week {week_number}")
        time.sleep(2)
    except Exception as e:
        print(f"  Warning: Could not find week selector for week {week_number}: {e}")
        print("  Continuing with current page...")

    # Debug: Save page source to file
    with open("page_source.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Saved page source to page_source.html for debugging")

    # Step 3: Find and download all gamebook PDFs
    print("Finding game panels...")

    # Find all game panels
    game_panels = driver.find_elements(By.CLASS_NAME, "gamePanelLarge")
    print(f"Found {len(game_panels)} games")

    # Process each game
    for i in range(len(game_panels)):
        # Re-find game panels each iteration to avoid stale element reference
        game_panels = driver.find_elements(By.CLASS_NAME, "gamePanelLarge")
        if i >= len(game_panels):
            break

        panel = game_panels[i]

        # Extract team codes from the panel by looking at CSS classes
        try:
            # Find the two clubRow divs (visitor and home)
            club_rows = panel.find_elements(By.CLASS_NAME, "clubRow")

            visitor_team = None
            home_team = None

            if len(club_rows) >= 2:
                # Extract team code from class names like "clubRow possession teamSF"
                for class_name in club_rows[0].get_attribute("class").split():
                    if class_name.startswith("team"):
                        visitor_team = class_name[4:]  # Remove "team" prefix
                        break

                for class_name in club_rows[1].get_attribute("class").split():
                    if class_name.startswith("team"):
                        home_team = class_name[4:]  # Remove "team" prefix
                        break

            if visitor_team and home_team:
                game_name = f"{visitor_team}{home_team}"
                print(f"\nProcessing game {i+1}: {game_name}")
            else:
                game_name = f"game_{i+1}"
                print(f"\nProcessing game {i+1} (could not extract team names)")
        except Exception as e:
            game_name = f"game_{i+1}"
            print(f"\nProcessing game {i+1} (error extracting team names: {e})")

        # Find the GAME BOOK button within this panel
        try:
            gamebook_button = panel.find_element(By.XPATH, ".//a[contains(@class, 'btn') and contains(@class, 'reports') and contains(text(), 'GAME BOOK')]")
        except:
            print(f"  No GAME BOOK button found for this game, skipping...")
            continue

        # Get list of files before download
        existing_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")))

        # Click the button
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", gamebook_button)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", gamebook_button)
        print(f"  Clicked GAME BOOK button, waiting for download...")

        # Wait for download to complete
        time.sleep(5)

        # Find the newly downloaded file
        current_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")))
        new_files = current_files - existing_files

        if new_files:
            downloaded_file = list(new_files)[0]
            new_filename = os.path.join(DOWNLOAD_DIR, f"{game_name}.pdf")

            # Rename if file doesn't already exist with that name
            if downloaded_file != new_filename:
                # Handle duplicate names
                counter = 1
                final_filename = new_filename
                while os.path.exists(final_filename):
                    final_filename = os.path.join(DOWNLOAD_DIR, f"{game_name}_{counter}.pdf")
                    counter += 1

                os.rename(downloaded_file, final_filename)
                print(f"  Renamed to: {os.path.basename(final_filename)}")
        else:
            print(f"  Warning: Could not find downloaded file")

    print(f"\nDownload complete! Week {week_number} PDFs saved to: {DOWNLOAD_DIR}")

    # Wait a bit for all downloads to finish
    time.sleep(5)

except Exception as e:
    print(f"Error occurred: {str(e)}")
    print("Taking screenshot for debugging...")
    driver.save_screenshot("error_screenshot.png")

finally:
    driver.quit()
    print("Browser closed.")
