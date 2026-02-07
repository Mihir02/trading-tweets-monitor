import requests
import json
import os
from datetime import datetime

BEARER_TOKEN = os.environ['X_BEARER_TOKEN']
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# JUST USE USERNAMES - the script will convert them to IDs automatically
TRADER_USERNAMES = [
    'zephyr_z9',
    'jukan05',
    'IncomeSharks',
    # Add your traders here (without the @ symbol)
]

KEYWORDS = ['capitulation', 'volatility', 'alert', '$', '$MU', 'market', 'crypto', 'stocks', 'capex', 'AI', 'semis', 'robot', 'supply', 'chain']

def get_user_id_from_username(username, headers):
    """Convert username to numeric user ID"""
    url = f'https://api.twitter.com/2/users/by/username/{username}'
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if 'data' in data and 'id' in data['data']:
            user_id = data['data']['id']
            print(f"✓ Found {username} → ID: {user_id}")
            return user_id
        else:
            print(f"✗ Could not find user: {username}")
            return None
    except Exception as e:
        print(f"✗ Error fetching user {username}: {e}")
        return None

def load_user_id_cache():
    """Load cached username->ID mappings"""
    try:
        with open('data/user_id_cache.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_id_cache(cache):
    """Save username->ID mappings to avoid repeated API calls"""
    os.makedirs('data', exist_ok=True)
    with open('data/user_id_cache.json', 'w') as f:
        json.dump(cache, f, indent=2)

def analyze_tweet_with_gemini(tweet_text, author_username, has_media=False):
    """Use Gemini to add context and analysis to ambiguous tweets"""
    if not GEMINI_API_KEY:
        return None
    
    media_context = " (Tweet contains an image/chart)" if has_media else ""
    
    prompt = f"""Analyze this trading/investment tweet and provide brief context{media_context}:

Tweet from @{author_username}:
"{tweet_text}"

Task:
- If it references "as I said" or "I told you": Note what context is missing
- If it mentions a chart/image: Indicate visual analysis is needed
- If it contains tickers: Identify them clearly
- If ambiguous: Clarify the likely trading action or insight

Provide a concise 2-3 sentence summary. Be direct and investment-focused."""

    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}'
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 200,
            }
        }
        
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                content = result['candidates'][0]['content']['parts'][0]['text']
                return content.strip()
        else:
            print(f"Gemini API error: {response.status_code}")
    except Exception as e:
        print(f"Gemini API error: {e}")
    
    return None

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

def save_trader_history(username, tweet_text, tweet_id):
    """Build a history of what each trader has said"""
    os.makedirs('data/history', exist_ok=True)
    history_file = f'data/history/{username}.json'
    
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
    except FileNotFoundError:
        history = []
    
    history.append({
        'id': tweet_id,
        'text': tweet_text,
        'timestamp': datetime.now().isoformat()
    })
    
    history = history[-30:]
    
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

def get_recent_context(username):
    """Get trader's recent tweets for context"""
    history_file = f'data/history/{username}.json'
    
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
            return [h['text'] for h in history[-3:]]
    except FileNotFoundError:
        return []

# Main execution starts here
print("🚀 Starting tweet fetch...")

headers = {'Authorization': f'Bearer {BEARER_TOKEN}'}

# Load cached user IDs
user_id_cache = load_user_id_cache()

# Convert usernames to IDs (with caching)
USER_IDS = []
cache_updated = False

for username in TRADER_USERNAMES:
    if username in user_id_cache:
        # Use cached ID
        USER_IDS.append(user_id_cache[username])
        print(f"✓ Using cached ID for {username}")
    else:
        # Fetch new ID
        user_id = get_user_id_from_username(username, headers)
        if user_id:
            USER_IDS.append(user_id)
            user_id_cache[username] = user_id
            cache_updated = True

# Save cache if updated
if cache_updated:
    save_user_id_cache(user_id_cache)

print(f"\n📋 Monitoring {len(USER_IDS)} traders\n")

# Load seen tweets
seen_tweets = load_seen_tweets()
all_tweets = []
new_tweets = []

# Fetch tweets from each user
for user_id in USER_IDS:
    url = f'https://api.twitter.com/2/users/{user_id}/tweets'
    params = {
        'max_results': 10,
        'tweet.fields': 'created_at,public_metrics,entities',
        'expansions': 'author_id,attachments.media_keys,referenced_tweets.id',
        'media.fields': 'url,preview_image_url,type',
        'user.fields': 'username,name'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if 'data' in data and 'includes' in data:
            users = {u['id']: u for u in data['includes'].get('users', [])}
            media = {m['media_key']: m for m in data['includes'].get('media', [])}
            
            for tweet in data['data']:
                tweet['author'] = users.get(tweet['author_id'], {})
                
                if 'attachments' in tweet and 'media_keys' in tweet['attachments']:
                    tweet['media'] = [media.get(k) for k in tweet['attachments']['media_keys']]
                else:
                    tweet['media'] = []
                
                all_tweets.append(tweet)
                
                if tweet['id'] not in seen_tweets:
                    new_tweets.append(tweet)
                    seen_tweets.add(tweet['id'])
        
        elif 'errors' in data:
            print(f"⚠️ API Error for user {user_id}: {data['errors']}")
            
    except Exception as e:
        print(f"❌ Error fetching tweets for user {user_id}: {e}")

print(f"📊 Found {len(new_tweets)} new tweets\n")

# Send notifications with context
for tweet in new_tweets[:5]:
    author = tweet['author']
    text = tweet['text']
    username = author.get('username', 'unknown')
    tweet_url = f"https://twitter.com/{username}/status/{tweet['id']}"
    
    save_trader_history(username, text, tweet['id'])
    
    is_priority = any(kw.lower() in text.lower() for kw in KEYWORDS)
    emoji = "🔥" if is_priority else "📊"
    
    has_media = len(tweet.get('media', [])) > 0
    media_note = ""
    
    if has_media:
        media_types = [m.get('type', 'image') for m in tweet['media']]
        if 'photo' in media_types or 'image' in media_types:
            media_note = "\n📸 <i>Contains chart/image</i>"
        elif 'video' in media_types:
            media_note = "\n🎥 <i>Contains video</i>"
    
    needs_context = any(phrase in text.lower() for phrase in [
        'as i said', 'i told you', 'called it', 'my previous', 
        'chart shows', 'see below', 'mentioned earlier'
    ])
    
    gemini_context = ""
    if GEMINI_API_KEY and (needs_context or is_priority or len(text) < 150):
        print(f"🤖 Getting AI context for tweet from @{username}...")
        analysis = analyze_tweet_with_gemini(text, username, has_media)
        if analysis:
            gemini_context = f"\n\n💡 <i>{analysis}</i>"
    
    history_note = ""
    if needs_context:
        recent = get_recent_context(username)
        if len(recent) > 1:
            history_note = f"\n\n📝 <i>Recent from @{username}: \"{recent[-2][:80]}...\"</i>"
    
    message = f"""{emoji} <b>{author.get('name', 'Unknown')}</b> (@{username})

{text[:300]}{media_note}{gemini_context}{history_note}

🔗 <a href="{tweet_url}">View on X</a>"""
    
    print(f"📤 Sending notification for @{username}")
    send_telegram(message)

# Save all data
all_tweets.sort(key=lambda x: x['created_at'], reverse=True)

os.makedirs('data', exist_ok=True)
with open('data/tweets.json', 'w') as f:
    json.dump(all_tweets[:100], f, indent=2)

save_seen_tweets(seen_tweets)

print(f"\n✅ Complete! Fetched {len(all_tweets)} tweets, sent {len(new_tweets[:5])} notifications")