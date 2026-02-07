async function loadTweets() {
    try {
        const response = await fetch('data/tweets.json');
        const tweets = await response.json();
        
        const container = document.getElementById('tweets-container');
        
        if (tweets.length === 0) {
            container.innerHTML = '<p class="no-tweets">No tweets yet. Wait for the first fetch!</p>';
            return;
        }
        
        container.innerHTML = tweets.map(tweet => {
            const author = tweet.author || {};
            const date = new Date(tweet.created_at);
            
            return `
                <div class="tweet-card">
                    <div class="tweet-header">
                        <strong>${author.name || 'User'}</strong>
                        <span class="username">@${author.username || 'unknown'}</span>
                    </div>
                    <p class="tweet-text">${tweet.text}</p>
                    <div class="tweet-footer">
                        <span class="tweet-time">${date.toLocaleString()}</span>
                        <a href="https://twitter.com/i/web/status/${tweet.id}" 
                           target="_blank" class="tweet-link">View on X →</a>
                    </div>
                </div>
            `;
        }).join('');
        
        document.getElementById('last-update').textContent = 
            `Last updated: ${new Date().toLocaleString()}`;
    } catch (error) {
        console.error('Error loading tweets:', error);
    }
}

loadTweets();
setInterval(loadTweets, 60000);