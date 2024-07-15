import requests
import sqlite3
import json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# RSS feed URL
RSS_URL = "https://old.reddit.com/r/midsoledeals/search.rss?q=flair%3A%22New%20Balance%22%20OR%20flair%3A%22Adidas%22&restrict_sr=1&sort=new"

# Database setup
DB_NAME = 'reddit_posts.db'

def log_debug(message):
    with open('debug.log', 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

def get_user_agent():
    try:
        user_agents = requests.get(
            "https://techfanetechnologies.github.io/latest-user-agent/user_agents.json"
        ).json()
        return user_agents[-2]
    except Exception as e:
        log_debug(f"Error fetching user agent: {e}")
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create posts table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
        published TEXT,
        author TEXT,
        thumbnail TEXT
    )
    ''')
    
    # Check if new columns exist, add them if they don't
    cursor.execute("PRAGMA table_info(posts)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'first_seen' not in columns:
        cursor.execute('ALTER TABLE posts ADD COLUMN first_seen TEXT')
    if 'last_seen' not in columns:
        cursor.execute('ALTER TABLE posts ADD COLUMN last_seen TEXT')
    
    # Create runs table to keep track of each script run
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_time TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

# ... [The rest of the functions remain the same] ...

def main():
    log_debug("Script started")
    init_db()
    
    current_posts = fetch_posts()
    new_posts, updated_posts = update_database(current_posts)
    removed_posts = get_removed_posts()
    
    log_debug(f"Found {len(new_posts)} new posts:")
    for post in new_posts:
        log_debug(f"- {post['title']} ({post['link']})")
    
    log_debug(f"Updated {len(updated_posts)} existing posts")
    
    log_debug(f"Removed {len(removed_posts)} posts:")
    for post in removed_posts:
        log_debug(f"- {post['title']} ({post['link']})")
    
    comparison = {
        'new_posts': new_posts,
        'updated_posts': updated_posts,
        'removed_posts': removed_posts
    }
    
    with open('comparison_result.json', 'w') as f:
        json.dump(comparison, f, indent=2)
    log_debug("Comparison results saved to comparison_result.json")
    
    log_debug("Script finished")

if __name__ == "__main__":
    main()
