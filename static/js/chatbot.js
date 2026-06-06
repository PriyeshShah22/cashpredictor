document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('chatbot-toggle');
    const chatWindow = document.getElementById('chatbot-window');
    const close = document.getElementById('close-chat');
    const input = document.getElementById('chat-input');
    const send = document.getElementById('send-chat');
    const messages = document.getElementById('chatbot-messages');

    feather.replace();

    toggle.onclick = () => {
        const isHidden = chatWindow.style.display === 'none';
        chatWindow.style.display = isHidden ? 'flex' : 'none';
        if (isHidden) { input.focus(); scrollToBottom(); }
    };

    close.onclick = () => { chatWindow.style.display = 'none'; };

    const addMessage = (text, sender) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        msgDiv.innerHTML = text.replace(/\n/g, '<br>');
        messages.appendChild(msgDiv);
        scrollToBottom();
    };

    const scrollToBottom = () => { messages.scrollTop = messages.scrollHeight; };

    const executeCommand = (command) => {
        console.log("Chatbot Command Executed:", command);
        if (command === 'NAVIGATE:TRANSACTIONS') {
            window.location.href = '/transactions.html';
        } else if (command.startsWith('GOTO_TRANSACTION:')) {
            const term = command.split(':')[1];
            window.location.href = `/transactions.html?search=${encodeURIComponent(term)}`;
        }
    };

    const handleSend = async () => {
        const query = input.value.trim();
        if (!query) return;

        addMessage(query, 'user');
        input.value = '';

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message bot';
        loadingDiv.textContent = '...';
        messages.appendChild(loadingDiv);
        scrollToBottom();

        try {
            const response = await fetch('/api/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const data = await response.json();
            
            loadingDiv.remove();
            addMessage(data.response, 'bot');

            if (data.command) {
                setTimeout(() => executeCommand(data.command), 1500);
            }
        } catch (error) {
            loadingDiv.remove();
            addMessage("I'm having trouble connecting. Is the server running?", 'bot');
        }
    };

    send.onclick = handleSend;
    input.onkeypress = (e) => { if (e.key === 'Enter') handleSend(); };
});
