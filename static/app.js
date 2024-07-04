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
