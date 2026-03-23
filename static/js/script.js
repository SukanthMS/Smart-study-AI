document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

let myChart = null;
let weakChart = null;
let currentMcqAnswers = {};

function initApp() {
    setupNavigation();
    setupThemeToggle();
    setupDropZone();
    setupHandlers();
    loadDashboard();
}

// ---- Navigation Setup ----
function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-links a');
    const sections = document.querySelectorAll('.section-view');
    const mobileToggle = document.querySelector('.mobile-toggle');
    const navMenu = document.querySelector('.nav-links');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const id = e.target.closest('a').getAttribute('href').substring(1);
            if (id) {
                e.preventDefault();
                navigateTo(id);
                // Close mobile menu if open
                if(navMenu.classList.contains('show')) {
                    navMenu.classList.remove('show');
                }
            }
        });
    });

    mobileToggle.addEventListener('click', () => {
        navMenu.classList.toggle('show');
    });
}

function navigateTo(id) {
    // Nav active state
    document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
    const targetLink = document.querySelector(`.nav-links a[href="#${id}"]`);
    if(targetLink) targetLink.classList.add('active');

    // Section view toggle
    document.querySelectorAll('.section-view').forEach(sec => sec.classList.remove('active-view'));
    const targetSec = document.getElementById(id);
    if(targetSec) {
        targetSec.classList.add('active-view');
        
        // Specific actions on load
        if(id === 'dashboard') {
            loadDashboard();
        }
    }
}

// ---- Theme Setup ----
function setupThemeToggle() {
    const themeBtn = document.getElementById('theme-toggle');
    const root = document.documentElement;

    themeBtn.addEventListener('click', () => {
        const currentTheme = root.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', newTheme);
        themeBtn.innerHTML = newTheme === 'dark' ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
    });
}

// ---- Drop Zone Setup ----
function setupDropZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');

    browseBtn.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files), false);
}

let uploadedFile = null;
function handleDrop(e) {
    handleFiles(e.dataTransfer.files);
}

function handleFiles(files) {
    if (files.length > 0) {
        const file = files[0];
        if(file.type === 'application/pdf') {
            uploadedFile = file;
            const dropZone = document.getElementById('drop-zone');
            dropZone.innerHTML = `<i class="fa-solid fa-file-pdf upload-icon text-cyan"></i> <h3>${file.name}</h3>`;
        } else {
            alert('Please upload a PDF file.');
        }
    }
}

function showLoader() { document.getElementById('loader').classList.remove('hidden'); }
function hideLoader() { document.getElementById('loader').classList.add('hidden'); }

// ---- API Handlers ----
function setupHandlers() {
    // 1. Upload
    document.getElementById('upload-submit').addEventListener('click', async () => {
        const textInput = document.getElementById('text-input').value;
        const statusMsg = document.getElementById('upload-status');
        
        if (!uploadedFile && !textInput.trim()) {
            alert('Please select a file or enter text');
            return;
        }

        const formData = new FormData();
        if (uploadedFile) formData.append('file', uploadedFile);
        if (textInput) formData.append('text', textInput);

        showLoader();
        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            statusMsg.classList.remove('hidden');
            if(res.ok) {
                statusMsg.innerHTML = `<span class="text-cyan"><i class="fa-solid fa-check-circle"></i> ${data.message} (${data.char_count} chars analyzed).</span>`;
                setTimeout(() => { navigateTo('notes'); }, 1500);
            } else {
                statusMsg.innerHTML = `<span style="color:red;"><i class="fa-solid fa-triangle-exclamation"></i> ${data.error}</span>`;
            }
        } catch (err) {
            console.error(err);
            alert('Upload failed.');
        } finally {
            hideLoader();
        }
    });

    // 2. Generate Notes
    document.getElementById('generate-notes-btn').addEventListener('click', async () => {
        showLoader();
        try {
            const res = await fetch('/api/generate_notes', { method: 'POST' });
            const data = await res.json();
            if(res.ok) {
                document.getElementById('notes-result').classList.remove('hidden');
                document.getElementById('notes-content').innerHTML = `
                    <p><strong>Summary Details:</strong> Reduced text from ${data.original_length} to ${data.summary_length} characters.</p>
                    <hr style="border-color:var(--glass-border); margin:15px 0;">
                    <p style="white-space: pre-wrap; font-size:1.1rem; line-height:1.8;">${data.notes}</p>
                `;
            } else {
                alert(data.error);
            }
        } catch(err) { console.error(err); } finally { hideLoader(); }
    });

    // 2b. TTS and Copy for Notes
    document.getElementById('speak-notes').addEventListener('click', function() {
        if (speechSynthesis.speaking) {
            speechSynthesis.cancel();
            this.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            this.title = "Read Aloud";
        } else {
            const text = document.getElementById('notes-content').innerText;
            const utterance = new SpeechSynthesisUtterance(text);
            
            utterance.onend = () => {
                this.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
                this.title = "Read Aloud";
            };
            
            speechSynthesis.speak(utterance);
            this.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
            this.title = "Stop Reading";
        }
    });

    document.getElementById('copy-notes').addEventListener('click', () => {
        const text = document.getElementById('notes-content').innerText;
        navigator.clipboard.writeText(text).then(() => alert('Notes copied to clipboard!'));
    });

    // 3. Generate Quiz
    document.getElementById('generate-quiz-btn').addEventListener('click', async () => {
        showLoader();
        try {
            const res = await fetch('/api/generate_questions', { method: 'POST' });
            const data = await res.json();
            if(data.error) {
                alert(data.error);
                return;
            }
            if(data.mcqs.length > 0) {
                // Determine badge color dynamically
                let colorClass = 'text-cyan';
                if (data.difficulty === 'hard') colorClass = 'text-purple';
                if (data.difficulty === 'easy') colorClass = 'text-orange';
                
                const header = document.querySelector('#quiz .massive-text');
                header.innerHTML = `Smart Quiz <span style="font-size: 1.2rem; vertical-align: middle; background: rgba(255,255,255,0.05); padding: 5px 15px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1);" class="${colorClass}"><i class="fa-solid fa-layer-group"></i> ${data.difficulty ? data.difficulty.toUpperCase() : 'MEDIUM'} MODE</span>`;
                
                renderQuiz(data.mcqs);
            } else {
                alert('Could not generate quiz. Try uploading more text!');
            }
        } catch(e) { console.error(e); } finally { hideLoader(); }
    });

    // 4. Submit Quiz
    document.getElementById('submit-quiz-btn').addEventListener('click', async () => {
        showLoader();
        try {
            const res = await fetch('/api/submit_quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answers: currentMcqAnswers })
            });
            const data = await res.json();
            if(res.ok) {
                document.getElementById('quiz-results').classList.remove('hidden');
                document.getElementById('score-display').innerText = `${Math.round(data.percentage)}%`;
                
                const wkList = document.getElementById('weak-areas-list');
                wkList.innerHTML = '';
                if(data.weak_topics.length > 0) {
                    data.weak_topics.forEach(t => {
                        wkList.innerHTML += `<li><i class="fa-solid fa-circle-exclamation text-secondary pr-2"></i> ${t}</li>`;
                    });
                } else {
                    wkList.innerHTML = '<li>You scored perfect! No weak areas detected.</li>';
                }
            }
        } catch (e) { console.error(e); } finally { hideLoader(); }
    });

    // 5. Generate Study Plan
    document.getElementById('generate-plan-btn').addEventListener('click', async () => {
        const topics = document.getElementById('plan-topics').value;
        const hours = document.getElementById('plan-hours').value;
        
        showLoader();
        try {
            const res = await fetch('/api/study_plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topics, hours })
            });
            const data = await res.json();
            if(res.ok) {
                const tl = document.getElementById('plan-timeline');
                tl.innerHTML = '';
                tl.classList.remove('hidden');
                
                data.plan.forEach((item, index) => {
                    tl.innerHTML += `
                        <div class="timeline-item">
                            <span class="time-badge">Phase ${index + 1}: ${item.duration}</span>
                            <h4>${item.topic}</h4>
                            <p>${item.task}</p>
                        </div>
                    `;
                });
            }
        } catch(e) { console.error(e); } finally { hideLoader(); }
    });

    // 6. Chatbot Widget Setup
    const chatToggle = document.getElementById('chatbot-toggle');
    const chatWidget = document.getElementById('chatbot-widget');
    const closeChat = document.getElementById('close-chat');
    const chatInput = document.getElementById('chat-input');
    const sendChat = document.getElementById('send-chat');
    const chatMessages = document.getElementById('chat-messages');

    chatToggle.addEventListener('click', () => chatWidget.classList.toggle('hidden'));
    closeChat.addEventListener('click', () => chatWidget.classList.add('hidden'));

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        chatMessages.innerHTML += `<div class="message user-message">${text}</div>`;
        chatInput.value = '';
        chatMessages.scrollTop = chatMessages.scrollHeight;

        const typingId = 'typing-' + Date.now();
        chatMessages.innerHTML += `<div id="${typingId}" class="message bot-message">Generating response... <i class="fa-solid fa-spinner fa-spin"></i></div>`;
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: text })
            });
            const data = await res.json();
            
            document.getElementById(typingId).remove();
            
            // Clean text for speech synthesis API
            const safeSpeech = data.answer.replace(/'/g, "\\'").replace(/"/g, '\\"');
            
            chatMessages.innerHTML += `
                <div class="message bot-message">
                    ${data.answer}
                    <div style="margin-top: 8px; text-align: right;">
                        <button class="btn-icon" style="width: 30px; height: 30px; font-size: 0.8rem; display: inline-flex;" onclick="speakChatbotText('${safeSpeech}')" title="Read Aloud">
                            <i class="fa-solid fa-volume-high text-cyan"></i>
                        </button>
                    </div>
                </div>
            `;
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } catch (error) {
            document.getElementById(typingId).remove();
            chatMessages.innerHTML += `<div class="message bot-message" style="color:#ff4d4d;">Failed to connect to AI brain.</div>`;
        }
    }

    sendChat.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // 7. Voice Input (Speech-To-Text) Accessibility 
    const voiceChat = document.getElementById('voice-chat');
    if (voiceChat && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        recognition.continuous = false;
        recognition.interimResults = false;
        
        recognition.onstart = function() {
            voiceChat.innerHTML = '<i class="fa-solid fa-microphone-lines fa-beat text-cyan"></i>';
            chatInput.placeholder = "Listening...";
        };
        
        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            chatInput.value = transcript;
            sendMessage(); // Automatically send question upon finished speaking
        };
        
        recognition.onerror = function(event) {
            console.error("Speech recognition error", event);
        };
        
        recognition.onend = function() {
            voiceChat.innerHTML = '<i class="fa-solid fa-microphone"></i>';
            chatInput.placeholder = "Type your doubt...";
        };
        
        voiceChat.addEventListener('click', () => {
            recognition.start();
        });
    } else if (voiceChat) {
        voiceChat.style.display = 'none'; // Not supported in this browser
    }
}

// Global function to speak text anywhere
window.speakChatbotText = function(text) {
    window.speechSynthesis.cancel(); // Overwrite any existing speech
    const utterance = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(utterance);
};

function renderQuiz(mcqs) {
    const container = document.getElementById('mcq-container');
    container.innerHTML = '';
    currentMcqAnswers = {};
    
    if(mcqs.length === 0) {
        container.innerHTML = '<p>No questions could be generated from the text. Please provide longer content.</p>';
        return;
    }

    document.getElementById('quiz-container').classList.remove('hidden');
    document.getElementById('quiz-results').classList.add('hidden');

    mcqs.forEach((q, index) => {
        let optionsHtml = q.options.map(opt => 
            `<div class="mcq-option" data-qid="${q.id}" data-val="${opt}">${opt}</div>`
        ).join('');

        container.innerHTML += `
            <div class="mcq-item">
                <p><strong>Q${index + 1}:</strong> ${q.question}</p>
                <div class="mcq-options">${optionsHtml}</div>
            </div>
        `;
    });

    // Attach click listeners to options
    document.querySelectorAll('.mcq-option').forEach(el => {
        el.addEventListener('click', function() {
            const qid = this.getAttribute('data-qid');
            const val = this.getAttribute('data-val');
            
            // visually deselect siblings
            const siblings = this.parentElement.querySelectorAll('.mcq-option');
            siblings.forEach(sib => sib.classList.remove('selected'));
            
            // select this
            this.classList.add('selected');
            
            // save answer
            currentMcqAnswers[qid] = val;
        });
    });
}

async function loadDashboard() {
    try {
        const res = await fetch('/api/progress');
        const data = await res.json();
        
        // History List
        const hl = document.getElementById('activity-list');
        hl.innerHTML = data.history.length ? '' : '<li>No recent activity to show.</li>';
        data.history.reverse().slice(0, 5).forEach(h => {
            hl.innerHTML += `<li><i class="fa-solid fa-check text-cyan pr-2"></i> ${h}</li>`;
        });
        
        // Gamification Update
        if(document.getElementById('nav-level-text')) {
            document.getElementById('nav-level-text').textContent = 'Lvl ' + data.level;
            const xpProgress = (data.xp % 50) * 2; // 50 points per level, scale to percentage
            document.getElementById('nav-xp-fill').style.width = xpProgress + '%';
        }
        
        // Badges Update
        const bg = document.getElementById('badges-grid');
        if(bg) {
            bg.innerHTML = data.badges.length ? '' : '<p class="text-secondary" style="font-size: 0.9rem;">No badges earned yet. Generate notes or take a quiz to unlock them!</p>';
            data.badges.forEach(b => {
                 bg.innerHTML += `<div class="badge-item"><i class="${b.icon}"></i> <span>${b.name}</span></div>`;
            });
        }
        
        // Charts
        renderChart(data.scores);
        renderWeaknessChart(data.weak_areas);
        
        // Weak Areas List (clear text)
        const wl = document.getElementById('weak-areas-list');
        if(wl) {
            wl.innerHTML = data.weak_areas.length ? '' : '<li style="border-left-color: var(--snap-green, #2ed573);">✅ No weak areas! Keep up the great work!</li>';
            data.weak_areas.forEach(wa => {
                wl.innerHTML += `<li><i class="fa-solid fa-triangle-exclamation text-orange pr-2"></i> <strong>${wa.topic}</strong> — answered wrong ${wa.count} time${wa.count > 1 ? 's' : ''}</li>`;
            });
        }

    } catch(e) { console.error("Dashboard Load Error: ", e); }
}

function renderChart(scores) {
    if(!document.getElementById('scoresChart')) return;
    
    // Default dummy data if empty
    const displayScores = scores.length > 0 ? scores : [0, 0, 0, 0, 0];
    const labels = displayScores.map((_, i) => 'Quiz ' + (i + 1));

    const ctx = document.getElementById('scoresChart').getContext('2d');
    
    if (myChart) myChart.destroy();
    
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(0, 242, 254, 0.4)');
    gradient.addColorStop(1, 'rgba(0, 242, 254, 0.0)');

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
    const textColor = isDark ? '#94a3b8' : '#475569';

    myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Quiz Score (%)',
                data: displayScores,
                borderColor: '#00f2fe',
                borderWidth: 3,
                backgroundColor: gradient,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#03040b',
                pointBorderColor: '#00f2fe',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: { beginAtZero: true, max: 100, grid: { color: gridColor }, ticks: { color: textColor, padding: 10 } },
                x: { grid: { display: false }, ticks: { color: textColor, padding: 10 } }
            },
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: 'rgba(15, 17, 30, 0.9)', titleColor: '#00f2fe', padding: 12, cornerRadius: 8, borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1 }
            }
        }
    });
}

function renderWeaknessChart(weakAreas) {
    if(!document.getElementById('weaknessChart')) return;
    
    const ctx = document.getElementById('weaknessChart').getContext('2d');
    if (weakChart) weakChart.destroy();

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#e2e8f0' : '#0f172a';
    
    const labels = weakAreas.length > 0 ? weakAreas.map(w => w.topic) : ['No Weak Areas Yet'];
    const data = weakAreas.length > 0 ? weakAreas.map(w => w.count) : [1];
    
    const bgColors = [
        'rgba(0, 242, 254, 0.8)',
        'rgba(131, 58, 180, 0.8)',
        'rgba(252, 176, 69, 0.8)',
        'rgba(253, 29, 29, 0.8)',
        'rgba(156, 39, 176, 0.8)'
    ];

    weakChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: weakAreas.length > 0 ? bgColors : ['rgba(255,255,255,0.05)'],
                borderWidth: 0,
                hoverOffset: 12
            }]
        },
        options: {
            responsive: true,
            cutout: '75%',
            plugins: {
                legend: { position: 'bottom', labels: { color: textColor, padding: 20, usePointStyle: true, pointStyle: 'circle' } },
                tooltip: { backgroundColor: 'rgba(15, 17, 30, 0.9)', padding: 12, cornerRadius: 8, borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1 }
            }
        }
    });
}
