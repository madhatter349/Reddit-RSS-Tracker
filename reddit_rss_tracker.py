import requests
import sqlite3
import json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import os

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
        thumbnail TEXT,
        first_seen TEXT,
        last_seen TEXT
    )
    ''')
    
    # Create runs table to keep track of each script run
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_time TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def fetch_posts():
    user_agent = get_user_agent()
    headers = {"user-agent": user_agent}
    
    log_debug(f"Fetching RSS feed from {RSS_URL}")
    response = requests.get(RSS_URL, headers=headers)
    
    if response.status_code != 200:
        log_debug(f"Error: Received status code {response.status_code}")
        return []
    
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        log_debug(f"XML parsing error: {e}")
        return []
    
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'media': 'http://search.yahoo.com/mrss/'
    }
    
    posts = []
    for entry in root.findall('atom:entry', namespaces):
        post = {
            'id': entry.find('atom:id', namespaces).text,
            'title': entry.find('atom:title', namespaces).text,
            'link': entry.find('atom:link', namespaces).attrib['href'],
            'published': entry.find('atom:published', namespaces).text,
            'author': entry.find('atom:author/atom:name', namespaces).text,
            'thumbnail': entry.find('media:thumbnail', namespaces).attrib['url'] if entry.find('media:thumbnail', namespaces) is not None else None
        }
        posts.append(post)
    
    return posts

def update_database(posts):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    
    new_posts = []
    updated_posts = []
    
    for post in posts:
        cursor.execute('SELECT id, last_seen FROM posts WHERE id = ?', (post['id'],))
        result = cursor.fetchone()
        
        if result is None:
            # New post
            cursor.execute('''
            INSERT INTO posts (id, title, link, published, author, thumbnail, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post['id'], post['title'], post['link'], post['published'], post['author'], post['thumbnail'], current_time, current_time))
            new_posts.append(post)
        else:
            # Existing post, update last_seen
            cursor.execute('UPDATE posts SET last_seen = ? WHERE id = ?', (current_time, post['id']))
            updated_posts.append(post)
    
    # Insert new run record
    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))
    
    conn.commit()
    conn.close()
    
    return new_posts, updated_posts

def get_removed_posts():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get the time of the previous run
    cursor.execute('SELECT run_time FROM runs ORDER BY id DESC LIMIT 1 OFFSET 1')
    result = cursor.fetchone()
    if result is None:
        return []  # No previous run, so no removed posts
    
    previous_run_time = result[0]
    
    # Find posts that were seen in the previous run but not in the current run
    cursor.execute('''
    SELECT id, title, link, published, author, thumbnail
    FROM posts
    WHERE last_seen = ? AND last_seen < (SELECT MAX(run_time) FROM runs)
    ''', (previous_run_time,))
    
    removed_posts = [dict(zip(['id', 'title', 'link', 'published', 'author', 'thumbnail'], row)) for row in cursor.fetchall()]
    
    conn.close()
    
    return removed_posts

def send_email(new_posts):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    for post in new_posts:
        body_content = f"""
        <h2>New Post from Reddit Tracker</h2>
        <p>A new post has been found:</p>
        <ul>
            <li><a href='{post['link']}'>{post['title']}</a> by {post['author']}</li>
        </ul>
        """

        # Truncate the title if it's too long for the subject
        subject_title = post['title'] if len(post['title']) <= 100 else post['title'][:97] + '...'
        
        data = {
            'to': 'madhatter349@gmail.com',
            'subject': f"New Post: {subject_title}",
            'body': body_content,
            'type': 'text/html'
        }

        response = requests.post('https://www.cinotify.cc/api/notify', headers=headers, data=data)

        log_debug(f"Email sending status code: {response.status_code}")
        log_debug(f"Email sending response: {response.text}")

        if response.status_code != 200:
            log_debug(f"Failed to send email for post: {post['title']}. Status code: {response.status_code}")
        else:
            log_debug(f"Email sent successfully for post: {post['title']}")

    return True  # Return True if the process completes, even if some emails fail

def main():
    log_debug("Script started")
    init_db()
    
    current_posts = fetch_posts()
    new_posts, updated_posts = update_database(current_posts)
    removed_posts = get_removed_posts()
    
    comparison_results = {
        'new_posts': new_posts,
        'updated_posts': updated_posts,
        'removed_posts': removed_posts
    }
    
    log_debug(f"Found {len(new_posts)} new posts")
    log_debug(f"Updated {len(updated_posts)} existing posts")
    log_debug(f"Removed {len(removed_posts)} posts")
    
    with open('comparison_result.json', 'w') as f:
        json.dump(comparison_results, f, indent=2)
    log_debug("Comparison results saved to comparison_result.json")
    
    if new_posts:
        send_email(new_posts)
        log_debug(f"Attempted to send {len(new_posts)} email(s) for new posts")
    else:
        log_debug("No new posts found. No emails sent.")
    
    log_debug("Script finished")

if __name__ == "__main__":
    main()
