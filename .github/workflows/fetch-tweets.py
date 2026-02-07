import requests
import json
import os
from datetime import datetime

BEARER_TOKEN = os.environ['X_BEARER_TOKEN']
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# REPLACE THESE with your trader user IDs
USER_IDS = ['44196397', '1234567890', '9876543210']

KEYWORDS = ['buy', 'sell', 'alert', 'breaking', '$']

def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def load_seen_tweets():
    try:
        with open('data/seen_tweets.json', 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_seen_tweets(seen_ids):
    os.makedirs('data', exist_ok=True)
    with open('data/seen_tweets.json', 'w') as f:
        json.dump(list(seen_ids), f)

seen_tweets = load_seen_tweets()
headers = {'Authorization': f'Bearer {BEARER_TOKEN}'}
all_tweets = []
new_tweets = []

for user_id in USER_IDS:
    url = f'https://api.twitter.com/2/users/{user_id}/tweets'
    params = {
        'max_results': 10,
        'tweet.fields': 'created_at,public_metrics',
        'expansions': 'author_id',
        'user.fields': 'username,name'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if 'data' in data and 'includes' in data:
            users = {u['id']: u for u in data['includes'].get('users', [])}
            
            for tweet in data['data']:
                tweet['author'] = users.get(tweet['author_id'], {})
                all_tweets.append(tweet)
                
                if tweet['id'] not in seen_tweets:
                    new_tweets.append(tweet)
                    seen_tweets.add(tweet['id'])
    except Exception as e:
        print(f"Error fetching tweets for user {user_id}: {e}")

for tweet in new_tweets[:5]:
    author = tweet['author']
    text = tweet['text']
    tweet_url = f"https://twitter.com/{author.get('username', 'i')}/status/{tweet['id']}"
    
    is_priority = any(kw.lower() in text.lower() for kw in KEYWORDS)
    emoji = "🔥" if is_priority else "📊"
    
    message = f"""{emoji} <b>{author.get('name', 'Unknown')}</b> (@{author.get('username', 'unknown')})

{text[:280]}

🔗 <a href="{tweet_url}">View on X</a>"""
    
    send_telegram(message)

all_tweets.sort(key=lambda x: x['created_at'], reverse=True)

os.makedirs('data', exist_ok=True)
with open('data/tweets.json', 'w') as f:
    json.dump(all_tweets[:100], f, indent=2)

save_seen_tweets(seen_tweets)

print(f"Fetched {len(all_tweets)} tweets, {len(new_tweets)} new")
