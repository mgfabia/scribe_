const socket = io();

document.getElementById('transcription-form').addEventListener('submit', async function (event) {
    event.preventDefault();

    const youtubeUrl = document.getElementById('youtube-url').value;
    const spinner = document.getElementById('spinner');
    const errorMessage = document.getElementById('error-message');

    // Clear previous error message
    errorMessage.textContent = '';

    // Show spinner
    spinner.style.display = 'block';

    try {
        const response = await fetch('/api/transcribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: youtubeUrl }),
        });

        if (response.ok) {
            const data = await response.json();
            document.getElementById('transcription-text').textContent = data.transcription;
            await loadHistory(); // Load history after successful transcription
        } else {
            const errorData = await response.json();
            document.getElementById('transcription-text').textContent = '';
            errorMessage.textContent = `Error: ${errorData.error}`;
        }
    } catch (error) {
        document.getElementById('transcription-text').textContent = '';
        errorMessage.textContent = `Error: ${error.message}`;
    }

    // Hide spinner after some delay
    setTimeout(() => {
        spinner.style.display = 'none';
    }, 500);
});

document.getElementById('copy-button').addEventListener('click', function() {
    const transcriptionText = document.getElementById('transcription-text');
    transcriptionText.select();
    document.execCommand('copy');
    alert('Transcription copied to clipboard!');
});

document.getElementById('download-button').addEventListener('click', function() {
    const transcriptionText = document.getElementById('transcription-text').value;
    const blob = new Blob([transcriptionText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcription.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

document.getElementById('dark-mode-toggle').addEventListener('change', function() {
    document.body.classList.toggle('dark-mode');
});

socket.on('transcription_update', function(data) {
    document.getElementById('transcription-text').textContent = data.transcription;
});

async function loadHistory() {
    const response = await fetch('/api/history');
    if (response.ok) {
        const history = await response.json();
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = '';
        history.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item.url;
            historyList.appendChild(li);
        });
    }
}

// Load history on page load
document.addEventListener('DOMContentLoaded', loadHistory);

document.addEventListener('DOMContentLoaded', () => {
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    
    // Check for saved dark mode preference
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        darkModeToggle.checked = true;
    }

    darkModeToggle.addEventListener('change', () => {
        if (darkModeToggle.checked) {
            document.body.classList.add('dark-mode');
            localStorage.setItem('darkMode', 'enabled');
        } else {
            document.body.classList.remove('dark-mode');
            localStorage.setItem('darkMode', null);
        }
    });
});

function loadTranscriptions() {
    fetch('/api/transcriptions')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('transcription-container');
            container.innerHTML = ''; // Clear existing content

            data.transcriptions.forEach(item => {
                const transcriptionItem = document.createElement('div');
                transcriptionItem.className = 'transcription-item';
                transcriptionItem.innerHTML = `
                    <h2 class="video-title">${item.title}</h2>
                    <p class="video-author">${item.author}</p>
                    <pre class="transcription">${item.transcription}</pre>
                    <a href="/transcription/${item.id}" class="read-more">Read More</a>
                `;
                container.appendChild(transcriptionItem);
            });
        })
        .catch(error => console.error('Error:', error));
}

function loadMarketNews() {
    console.log('Fetching market news...'); // Add logging
    fetch('/api/market-news')
        .then(response => response.json())
        .then(data => {
            console.log('Market news data:', data); // Add logging
            const container = document.getElementById('market-news');
            container.innerHTML = ''; // Clear the container first
            if (data.feed) {
                data.feed.forEach(newsItem => {
                    const div = document.createElement('div');
                    div.className = 'news-item';

                    const title = document.createElement('div');
                    title.className = 'news-title';
                    title.textContent = newsItem.title;

                    const summary = document.createElement('div');
                    summary.className = 'news-summary';
                    summary.textContent = newsItem.summary;

                    const link = document.createElement('a');
                    link.href = newsItem.url;
                    link.target = '_blank';
                    link.textContent = 'Read more';
                    link.className = 'read-more';

                    div.appendChild(title);
                    div.appendChild(summary);
                    div.appendChild(link);
                    container.appendChild(div);
                });
            } else {
                container.innerHTML = '<p>No news available.</p>';
            }
        })
        .catch(error => {
            console.error('Error fetching market news:', error);
        });
}

document.addEventListener('DOMContentLoaded', function () {
    loadTranscriptions();
    loadMarketNews();
});

document.addEventListener('DOMContentLoaded', function () {
    loadTranscriptions();
    loadMarketNews();
});

document.addEventListener('DOMContentLoaded', function() {
    const downloadButtons = document.querySelectorAll('.download-btn');
    
    downloadButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const videoId = this.getAttribute('data-video-id');
            
            // Trigger the download
            window.location.href = `/download/${videoId}`;
        });
    });
});

// Call this function when the page loads
document.addEventListener('DOMContentLoaded', loadTranscriptions);