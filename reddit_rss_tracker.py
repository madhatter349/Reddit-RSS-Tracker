import requests
import sqlite3
import json
from datetime import datetime
import xml.etree.ElementTree as ET

# RSS feed URL
RSS_URL = "https://old.reddit.com/r/midsoledeals/search.xml?q=flair%3A%22New%20Balance%22%20OR%20flair%3A%22Adidas%22&restrict_sr=1&sort=new"

# Database setup
DB_NAME = 'reddit_posts.db'

def get_user_agent():
    try:
        user_agents = requests.get(
            "https://techfanetechnologies.github.io/latest-user-agent/user_agents.json"
        ).json()
        return user_agents[-2]
    except Exception as e:
        print(f"Error fetching user agent: {e}")
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

def fetch_and_save_posts():
    user_agent = get_user_agent()
    headers = {"user-agent": user_agent}
    
    response = requests.get(RSS_URL, headers=headers)
    root = ET.fromstring(response.content)
    
    # Define namespaces
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'media': 'http://search.yahoo.com/mrss/'
    }
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    new_posts = []
    for entry in root.findall('atom:entry', namespaces):
        post_id = entry.find('atom:id', namespaces).text
        title = entry.find('atom:title', namespaces).text
        link = entry.find('atom:link', namespaces).attrib['href']
        published = entry.find('atom:published', namespaces).text
        author = entry.find('atom:author/atom:name', namespaces).text
        thumbnail = entry.find('media:thumbnail', namespaces)
        thumbnail_url = thumbnail.attrib['url'] if thumbnail is not None else None
        
        cursor.execute('SELECT id FROM posts WHERE id = ?', (post_id,))
        if cursor.fetchone() is None:
            cursor.execute('''
            INSERT INTO posts (id, title, link, published, author, thumbnail)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (post_id, title, link, published, author, thumbnail_url))
            new_posts.append({
                'id': post_id,
                'title': title,
                'link': link,
                'published': published,
                'author': author,
                'thumbnail': thumbnail_url
            })
    
    conn.commit()
    conn.close()
    
    return new_posts

def main():
    init_db()
    new_posts = fetch_and_save_posts()
    
    if new_posts:
        print(f"Found {len(new_posts)} new posts:")
        for post in new_posts:
            print(f"- {post['title']} ({post['link']})")
        
        # Save new posts to a JSON file
        with open('new_posts.json', 'w') as f:
            json.dump(new_posts, f, indent=2)
        print("New posts saved to new_posts.json")
    else:
        print("No new posts found.")

if __name__ == "__main__":
    main()
