import os
import re
import math
from collections import Counter
from flask import Flask, render_template, request, jsonify, session
from pypdf import PdfReader
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_study_key'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_default_progress():
    return {
        'history': [],
        'scores': [],
        'weak_areas': [],
        'xp': 0,
        'level': 1,
        'badges': [],
        'difficulty': 'medium'
    }

# Simulated database
user_progress = get_default_progress()

def add_xp(amount, reason):
    user_progress['xp'] += amount
    new_level = max(1, (user_progress['xp'] // 50) + 1)
    if new_level > user_progress['level']:
        user_progress['level'] = new_level
        user_progress['history'].append(f"🏆 Leveled up to Level {new_level}!")
    
def add_badge(badge_name, icon):
    existing_badges = [b['name'] for b in user_progress['badges']]
    if badge_name not in existing_badges:
        user_progress['badges'].append({'name': badge_name, 'icon': icon})

def extract_text_from_pdf(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return str(e)

def generate_summary(text):
    if not text or len(text.split()) < 30:
        return text
    
    # Split text into original paragraphs, keeping short ones as headings
    raw_paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    if len(raw_paragraphs) < 2:
        sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
        chunk_size = max(5, len(sentences) // 4)
        raw_paragraphs = [" ".join(sentences[i:i + chunk_size]) for i in range(0, len(sentences), chunk_size)]

    stop_words = set(["the", "is", "in", "and", "to", "of", "it", "that", "you", "a", "an", "for", "on", "with", "as", "by", "this", "are", "from", "be", "or", "which", "will", "can", "has", "have", "had", "were", "was"])
    
    # Calculate global TF-IDF for the text for sharper summarization
    all_sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
    total_docs = max(1, len(all_sentences))
    word_doc_count = Counter()
    for sentence in all_sentences:
        words = set(re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower()))
        for w in words:
            word_doc_count[w] += 1
            
    idf = {}
    for kw, doc_count in word_doc_count.items():
        idf[kw] = math.log(total_docs / doc_count) + 1
    
    final_summary_bullets = []
    
    for para in raw_paragraphs:
        words_in_para = para.split()
        
        # Explicit Heading detection
        if len(words_in_para) <= 8 and not para.endswith('.'):
            final_summary_bullets.append(f"<strong class='text-cyan' style='font-size:1.2rem;'>{para}</strong>")
            continue
            
        sentences = re.split(r'(?<=[.!?]) +', para)
        if len(sentences) <= 2:
            final_summary_bullets.append("• " + para)
            continue
            
        sentence_scores = {}
        for sentence in sentences:
            score = 0
            words = set(re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower()))
            for word in words:
                if word not in stop_words and word in idf:
                    score += idf[word]
            sentence_scores[sentence] = score / max(1, len(sentence.split()))

        # Keep the top, highly-specific explanatory sentences
        top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:max(1, len(sentences)//4)]
        summary_para = [s for s in sentences if s in top_sentences]
        final_summary_bullets.append("• " + " ".join(summary_para))
        
    return "<br><br>".join(final_summary_bullets)


def generate_questions(text, difficulty='medium'):
    import random
    sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
    mcqs = []
    
    if difficulty == 'easy':
        min_len, max_len = 6, 20
        target_criteria = lambda k, freq: -freq.get(k.lower(), 1)  # Easiest common words
        distractor_complexity = False
    elif difficulty == 'hard':
        min_len, max_len = 15, 45
        target_criteria = lambda k, freq: freq.get(k.lower(), 1)   # Most unique/rarest words
        distractor_complexity = True
    else: # medium
        min_len, max_len = 10, 30
        target_criteria = lambda k, freq: freq.get(k.lower(), 1)
        distractor_complexity = False
        
    qualified_sentences = [s for s in sentences if len(s.split()) >= min_len and len(s.split()) <= max_len]
    random.shuffle(qualified_sentences)
    
    all_words = re.findall(r'\b[A-Za-z]{6,}\b', text)
    stop_words = {"however", "furthermore", "therefore", "because", "although", "instead", "during", "should", "would", "could", "through", "between", "without", "against", "system", "example", "process", "various"}
    valid_keywords = list(set([w for w in all_words if w.lower() not in stop_words]))
    
    # Calculate word frequency for dynamic Weak Topic generation
    word_freq = Counter([w.lower() for w in re.findall(r'\b[A-Za-z]{5,}\b', text) if w.lower() not in stop_words])
    
    for i, sentence in enumerate(qualified_sentences[:20]):
        # Limit word size for easy mode, strict unique for hard
        regex_pattern = r'\b[a-zA-Z]{5,}\b' if difficulty == 'easy' else r'\b[a-zA-Z]{7,}\b|\b[A-Z][a-z]{4,}\b'
        words = re.findall(regex_pattern, sentence)
        keywords = [w for w in words if w.lower() not in stop_words]
        
        if keywords:
            # Pick target dynamically based on difficulty curve
            target_keyword = min(keywords, key=lambda k: target_criteria(k, word_freq))
            
            # Form accurate "Topic" for Weak Area tracking using the two rarest words in this sentence
            sent_words = [w for w in re.findall(r'\b[A-Za-z]{5,}\b', sentence) if w.lower() not in stop_words]
            sent_words_sorted = sorted(sent_words, key=lambda k: word_freq.get(k.lower(), 1))
            topic_tag = " ".join(sent_words_sorted[:2]).title() if len(sent_words_sorted) >= 2 else target_keyword.title()
            
            # Seamless, professional format without repetitive meta-instructions
            question_text = f"{sentence.replace(target_keyword, '_______', 1)}"
            
            options = [target_keyword]
            distractor_pool = [k for k in valid_keywords if k.lower() != target_keyword.lower()]
            random.shuffle(distractor_pool)
            options.extend(distractor_pool[:3])
            
            # Fill remaining with complex generic terms or easy terms depending on difficulty
            if distractor_complexity:
                fillers = ["Methodology", "Optimization", "Architecture", "Validation", "Synthesis"]
            else:
                fillers = ["Computer", "System", "Machine", "Data", "Information"]
                
            while len(options) < 4:
                filler = random.choice(fillers)
                if filler not in options: options.append(filler)
            
            random.shuffle(options)
            
            mcqs.append({
                "id": f"q_{i}",
                "question": question_text,
                "options": options[:4],
                "answer": target_keyword,
                "topic": topic_tag
            })
            
    return mcqs, []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    text = request.form.get('text', '')
    
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            if filename.endswith('.pdf'):
                extracted = extract_text_from_pdf(filepath)
                text += "\n" + extracted
            else:
                return jsonify({"error": "Unsupported file format. Please upload PDF."}), 400
                
    if not text.strip():
        return jsonify({"error": "No text or file provided"}), 400
        
    session['current_text'] = text
    user_progress['history'].append("Uploaded Study Material")
    return jsonify({"message": "Content uploaded successfully", "char_count": len(text)})

@app.route('/api/generate_notes', methods=['POST'])
def generate_notes():
    text = session.get('current_text', '')
    if not text:
        return jsonify({"error": "No text uploaded yet."}), 400
        
    summary = generate_summary(text)
    user_progress['history'].append("Generated Smart Notes")
    
    return jsonify({"notes": summary, "original_length": len(text), "summary_length": len(summary)})

@app.route('/api/generate_questions', methods=['POST'])
def generate_questions_route():
    text = session.get('current_text', '')
    if not text:
        return jsonify({"error": "No content found. Please upload first."}), 400
        
    diff = user_progress.get('difficulty', 'medium')
    mcqs, _ = generate_questions(text, difficulty=diff)
    
    # Store questions in session to check answers later
    session['current_mcqs'] = mcqs
    user_progress['history'].append(f"Generated a {diff.title()} Quiz")
    
    return jsonify({"mcqs": mcqs, "difficulty": diff})

@app.route('/api/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    answers = data.get('answers', {})
    mcqs = session.get('current_mcqs', [])
    
    score = 0
    total = len(mcqs)
    weak_topics = []
    
    for q in mcqs:
        q_id = q['id']
        correct_answer = q['answer']
        topic = q.get('topic', correct_answer) # Graceful fallback
        user_answer = answers.get(q_id, "")
        
        if str(user_answer).lower().strip() == str(correct_answer).lower().strip():
            score += 1
        else:
            weak_topics.append(topic)
            
    percentage = (score / total * 100) if total > 0 else 0
    
    # Adaptive Learning Modifier
    if percentage >= 80:
        if user_progress['difficulty'] != 'hard': user_progress['history'].append("🧠 Promoted to Hard Quizzes!")
        user_progress['difficulty'] = 'hard'
    elif percentage >= 50:
        user_progress['difficulty'] = 'medium'
    else:
        if user_progress['difficulty'] != 'easy': user_progress['history'].append("📉 Demoted to Easy Quizzes.")
        user_progress['difficulty'] = 'easy'
    
    # Gamification: 1 point per correct answer, 0 for wrong
    earned_xp = score  # 1 XP per correct answer
    if percentage == 100 and total > 0:
        add_badge("Perfect Scholar", "fa-solid fa-star text-yellow")
        
    add_xp(earned_xp, f"Quiz Graded ({score}/{total})")
    if total > 0: add_badge("First Quiz", "fa-solid fa-medal text-orange")
    
    # Update progress
    user_progress['scores'].append(percentage)
    user_progress['history'].append(f"Took Quiz: {score}/{total}")
    for topic in weak_topics:
        if len(topic) < 30: # sanity check
            user_progress['weak_areas'].append(topic)
        
    return jsonify({
        "score": score,
        "total": total,
        "percentage": percentage,
        "weak_topics": list(set(weak_topics))
    })

@app.route('/api/study_plan', methods=['POST'])
def study_plan():
    data = request.json
    topics_raw = data.get('topics', "")
    hours = data.get('hours', 2)
    
    topics = [t.strip() for t in topics_raw.split(',') if t.strip()]
    if not topics:
        topics = list(set(user_progress['weak_areas']))[-5:] if user_progress['weak_areas'] else ["Literature Review", "Practice Test", "Concept Mapping"]
        
    try:
        hours = float(hours)
    except:
        hours = 2.0
        
    hours_per_topic = hours / len(topics) if len(topics) > 0 else hours
    
    plan = []
    for t in topics:
        plan.append({
            "topic": t,
            "duration": f"{hours_per_topic:.1f} hours",
            "task": f"Focus deeply on '{t}', utilizing the Pomodoro technique (25m study, 5m break)."
        })
        
    user_progress['history'].append("Generated Study Plan")
    return jsonify({"plan": plan})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    question = data.get('question', '').strip()
    text = session.get('current_text', '')
    
    if not question:
        return jsonify({"answer": "Please ask a question."})
        
    if not text:
        return jsonify({"answer": "Please upload a document or paste text first so I can answer questions about it!"})

    q_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', question.lower()))
    stop_words = {"what", "who", "when", "where", "why", "how", "is", "are", "do", "does", "did", "the", "a", "an", "of", "and", "in", "to", "for", "explain", "describe", "about", "tell", "me", "can", "you", "doubt", "doubts", "question"}
    q_keywords = list(q_words - stop_words)
    
    if not q_keywords:
        return jsonify({"answer": "Can you be more specific with some precise keywords?"})
        
    sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
    
    # ---------------------------------------------------------
    # Custom TF-IDF (Inverse Document Frequency) Search Engine 
    # to perfectly locate specific relevant answers
    # ---------------------------------------------------------
    total_docs = max(1, len(sentences))
    word_doc_count = Counter()
    for sentence in sentences:
        words_in_sent = set(re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower()))
        for w in words_in_sent:
            word_doc_count[w] += 1
            
    idf = {}
    for kw in q_keywords:
        doc_count = word_doc_count.get(kw, 0)
        if doc_count > 0:
            idf[kw] = math.log(total_docs / doc_count) + 1
        else:
            idf[kw] = 0 # Word doesn't exist in the text at all
            
    best_score = 0
    best_sentence = ""
    
    for i, sentence in enumerate(sentences):
        sent_lower = sentence.lower()
        
        # Calculate TF-IDF score for this sentence
        score = sum(idf[kw] for kw in q_keywords if kw in sent_lower)
        
        # If the user asked an exact phrase, heavily boost it
        phrase = " ".join(q_keywords)
        if len(q_keywords) > 1 and phrase in sent_lower:
            score += 5.0
                
        if score > best_score:
            best_score = score
            context = sentence
            # Grab next sentence for better context explanation
            if i + 1 < len(sentences):
                context += " " + sentences[i+1]
            best_sentence = context
            
    # Require at least one highly relevant keyword match
    if best_score < 1.0 or not best_sentence:
        return jsonify({"answer": "I couldn't find a contextually relevant answer to that specific doubt in the uploaded study material."})
        
    return jsonify({"answer": best_sentence.strip()})

@app.route('/api/progress', methods=['GET'])
def get_progress():
    weak_counts = Counter(user_progress['weak_areas']).most_common(5)
    formatted_weak_areas = [{"topic": item[0], "count": item[1]} for item in weak_counts]
    
    return jsonify({
        "scores": user_progress['scores'][-10:],
        "history": user_progress['history'][-10:],
        "weak_areas": formatted_weak_areas,
        "xp": user_progress['xp'],
        "level": user_progress['level'],
        "badges": user_progress['badges']
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
