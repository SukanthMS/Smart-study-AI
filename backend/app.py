import os
import re
import math
import json
from collections import Counter
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from groq import Groq
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_study_key')

# Database Configuration
db_url = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Try PostgreSQL first, fallback to SQLite if needed
try:
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")
    print(f"Attempting to test PostgreSQL: {db_url[:20]}...")
    import psycopg2
    # Test raw connection first with a short timeout
    conn = psycopg2.connect(db_url, connect_timeout=3)
    conn.close()
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    # Only PostgreSQL needs this specific timeout arg in SQLAlchemy
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": { "connect_timeout": 5 }
    }
    print("PostgreSQL connection verified!")
except Exception as e:
    print(f"Postgres unreachable ({e}). Falling back to Local SQLite...")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local_study.db'

db = SQLAlchemy(app)

# Groq Configuration
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    print("⚠️ WARNING: GROQ_API_KEY not found in environment variables. AI features will not work.")
client = Groq(api_key=api_key)

# Models
class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    difficulty = db.Column(db.String(20), default='medium')
    history = db.Column(db.JSON, default=list)
    scores = db.Column(db.JSON, default=list)
    weak_areas = db.Column(db.JSON, default=list)
    badges = db.Column(db.JSON, default=list)
# Initialize Database schema
with app.app_context():
    try:
        db.create_all()
        # Seed default user
        if not db.session.get(UserProgress, 1):
            user = UserProgress(id=1)
            db.session.add(user)
            db.session.commit()
        print("Schema successfully created/verified.")
    except Exception as e:
        print(f"Schema creation failed: {e}")

UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def extract_text_from_pdf(filepath):
    """Extract text from a PDF file using pypdf"""
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        print(f"[BACKEND] PDF extracted: {len(text)} characters from {len(reader.pages)} pages.")
        return text.strip()
    except Exception as e:
        print(f"[BACKEND] PDF extraction error: {e}")
        return ""

def get_user():
    user = db.session.get(UserProgress, 1)
    if not user:
        try:
            print("[DATABASE] Creating default user 1...")
            user = UserProgress(id=1)
            db.session.add(user)
            db.session.commit()
            return user
        except:
            db.session.rollback()
            return None
    return user

def add_xp(amount, reason):
    user = get_user()
    user.xp += amount
    new_level = max(1, (user.xp // 50) + 1)
    
    # Handle JSON mutability for SQLAlchemy
    history = list(user.history)
    if new_level > user.level:
        user.level = new_level
        history.append(f"🏆 Leveled up to Level {new_level}!")
    
    user.history = history
    db.session.commit()

def add_badge(badge_name, icon):
    user = get_user()
    badges = list(user.badges)
    existing_badges = [b['name'] for b in badges]
    if badge_name not in existing_badges:
        badges.append({'name': badge_name, 'icon': icon})
        user.badges = badges
        db.session.commit()

def generate_summary(text):
    if not text or len(text.split()) < 5:
        return "Not enough content to summarize."
    
    try:
        # Attempt AI Summarization with Groq
        response = client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"Summarize the following study material into well-structured, easy-to-read bullet points with bold key terms: \n\n{text[:15000]}"
            }],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq AI Failed: {e}. Falling back to local summarizer...")
        # Local Fallback (TF-IDF simple logic)
        sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
        if len(sentences) <= 3: return text
        
        all_words = re.findall(r'\b\w{4,}\b', text.lower())
        word_freq = Counter(all_words)
        
        sentence_scores = {}
        for sent in sentences:
            words = re.findall(r'\b\w{4,}\b', sent.lower())
            score = sum(word_freq.get(w, 0) for w in set(words))
            sentence_scores[sent] = score / max(1, len(sent.split()))
            
        top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:max(2, len(sentences)//4)]
        summary = " ".join([s for s in sentences if s in top_sentences])
        return "### [Local Summary] \n\n" + summary


def generate_questions_ai(text, num_questions=10):
    """Generate quiz questions using Groq AI for proper, meaningful MCQs"""
    import json as json_lib
    try:
        prompt = "Based on the following study material, generate exactly " + str(num_questions) + """ multiple choice questions.

RULES:
- Each question must be a clear, meaningful question.
- Each question must have exactly 4 answer choices.
- Only ONE answer should be correct.
- The "answer" field MUST be the EXACT text of the correct option from the "options" array.

Return ONLY a valid JSON array in this exact format, no other text:
[
  {
    "question": "What is the capital of France?",
    "options": ["London", "Berlin", "Paris", "Madrid"],
    "answer": "Paris",
    "topic": "Geography"
  }
]

STUDY MATERIAL:
""" + text[:8000]

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Return ONLY a JSON array of MCQs based on the context. No preamble."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2500,
            top_p=1,
            stream=False
        )
        
        response_text = completion.choices[0].message.content.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            response_text = response_text.rsplit("```", 1)[0]
        response_text = response_text.strip()
        
        mcqs_raw = json_lib.loads(response_text)
        
        mcqs = []
        for i, q in enumerate(mcqs_raw):
            mcqs.append({
                "id": "q_" + str(i),
                "question": q["question"],
                "options": q["options"][:4],
                "answer": q["answer"],
                "topic": q.get("topic", "General")
            })
        
        return mcqs
        
    except Exception as e:
        print("[BACKEND] AI Quiz Generation failed: " + str(e))
        return None


def generate_questions(text, difficulty='medium'):
    import random
    sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
    mcqs = []
    
    if difficulty == 'easy':
        min_len, max_len = 6, 20
        target_criteria = lambda k, freq: -freq.get(k.lower(), 1)
        distractor_complexity = False
    elif difficulty == 'hard':
        min_len, max_len = 15, 45
        target_criteria = lambda k, freq: freq.get(k.lower(), 1)
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
    
    word_freq = Counter([w.lower() for w in re.findall(r'\b[A-Za-z]{5,}\b', text) if w.lower() not in stop_words])
    
    for i, sentence in enumerate(qualified_sentences[:20]):
        regex_pattern = r'\b[a-zA-Z]{5,}\b' if difficulty == 'easy' else r'\b[a-zA-Z]{7,}\b|\b[A-Z][a-z]{4,}\b'
        words = re.findall(regex_pattern, sentence)
        keywords = [w for w in words if w.lower() not in stop_words]
        
        if keywords:
            target_keyword = min(keywords, key=lambda k: target_criteria(k, word_freq))
            sent_words = [w for w in re.findall(r'\b[A-Za-z]{5,}\b', sentence) if w.lower() not in stop_words]
            sent_words_sorted = sorted(sent_words, key=lambda k: word_freq.get(k.lower(), 1))
            topic_tag = " ".join(sent_words_sorted[:2]).title() if len(sent_words_sorted) >= 2 else target_keyword.title()
            
            question_text = f"{sentence.replace(target_keyword, '_______', 1)}"
            
            options = [target_keyword]
            distractor_pool = [k for k in valid_keywords if k.lower() != target_keyword.lower()]
            random.shuffle(distractor_pool)
            options.extend(distractor_pool[:3])
            
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
    user = get_user()
    
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"[BACKEND] Saving file to: {filepath}")
            file.save(filepath)
            if filename.lower().endswith('.pdf'):
                print(f"[BACKEND] Extracting text from PDF: {filename}")
                extracted = extract_text_from_pdf(filepath)
                if extracted:
                    print(f"[BACKEND] Successfully extracted {len(extracted)} characters.")
                    text += "\n" + extracted
                else:
                    print("[BACKEND] WARNING: Extracted text was empty!")
            else:
                print(f"[BACKEND] ERROR: Unsupported file extension: {filename}")
                return jsonify({"error": "Unsupported file format. Please upload PDF."}), 400
                
    try:
        if not text.strip():
            print("[BACKEND] ERROR: No valid text extracted for upload.")
            return jsonify({"error": "No text or file provided"}), 400
            
        session['current_text'] = text
        session.modified = True 
        print(f"[BACKEND] Success: Uploaded {len(text)} characters.")
        
        try:
            history = list(user.history) if user else []
            history.append("Uploaded Study Material")
            if user:
                user.history = history
                db.session.commit()
        except:
            pass # Non-critical if history fails
            
        return jsonify({"message": "Content uploaded successfully", "char_count": len(text)})
    except Exception as e:
        print(f"[BACKEND] CRITICAL UPLOAD ERROR: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route('/api/generate_notes', methods=['POST'])
def generate_notes():
    text = session.get('current_text', '')
    print(f"[BACKEND] Attempting Note Generation. Session text length: {len(text)}")
    
    if not text or len(text.strip()) < 5:
        print("[BACKEND] ERROR: current_text was empty in session! Did upload fail or session reset?")
        return jsonify({"error": "No text uploaded yet or session expired. Please upload again."}), 400
        
    user = get_user()
    try:
        summary = generate_summary(text)
        print(f"[BACKEND] Summary successfully generated ({len(summary)} chars).")
        
        history = list(user.history)
        history.append("📑 Compiled Topic Summaries (Study Time: ~20 mins)")
        user.history = history
        db.session.commit()
        
        add_badge("Topic Completion Badge", "fa-solid fa-check-double text-purple")
        add_badge("Study Streak Badge", "fa-solid fa-fire text-orange")
        
        return jsonify({"notes": summary, "original_length": len(text), "summary_length": len(summary)})
    except Exception as e:
        print(f"[BACKEND] CRITICAL FAILED during summary processing: {e}")
        return jsonify({"error": f"AI Brain is busy/errored: {str(e)}"}), 500

@app.route('/api/generate_questions', methods=['POST'])
def generate_questions_route():
    text = session.get('current_text', '')
    user = get_user()
    if not text:
        return jsonify({"error": "No content found. Please upload first."}), 400
        
    diff = user.difficulty
    
    # Try AI-powered quiz generation first
    ai_mcqs = generate_questions_ai(text, num_questions=20)
    
    if ai_mcqs and len(ai_mcqs) > 0:
        mcqs = ai_mcqs
        print("[BACKEND] AI generated " + str(len(mcqs)) + " quiz questions successfully.")
    else:
        # Fallback to procedural method
        mcqs, _ = generate_questions(text, difficulty=diff)
        print("[BACKEND] Fallback: procedural method generated " + str(len(mcqs)) + " questions.")
    
    session['current_mcqs'] = mcqs
    
    history = list(user.history)
    history.append(f"Generated a {diff.title()} Quiz")
    user.history = history
    db.session.commit()
    
    return jsonify({"mcqs": mcqs, "difficulty": diff})

@app.route('/api/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    answers = data.get('answers', {})
    mcqs = session.get('current_mcqs', [])
    user = get_user()
    
    score = 0
    total = len(mcqs)
    weak_topics = []
    
    for q in mcqs:
        q_id = q['id']
        correct_answer = q['answer']
        topic = q.get('topic', correct_answer)
        user_answer = answers.get(q_id, "")
        
        if str(user_answer).lower().strip() == str(correct_answer).lower().strip():
            score += 1
        else:
            weak_topics.append(topic)
            
    percentage = (score / total * 100) if total > 0 else 0
    
    history = list(user.history)
    if percentage >= 80:
        if user.difficulty != 'hard': history.append("🧠 Promoted to Hard Quizzes!")
        user.difficulty = 'hard'
    elif percentage >= 50:
        user.difficulty = 'medium'
    else:
        if user.difficulty != 'easy': history.append("📉 Demoted to Easy Quizzes.")
        user.difficulty = 'easy'
        
    earned_xp = score
    if percentage == 100 and total > 0:
        add_badge("Perfect Scholar", "fa-solid fa-star text-yellow")
        
    add_xp(earned_xp, f"Quiz Graded ({score}/{total})")
    if total > 0: add_badge("First Quiz", "fa-solid fa-medal text-orange")
    
    scores = list(user.scores)
    scores.append(percentage)
    user.scores = scores
    
    history.append(f"✍️ Took Quiz: {score}/{total} (Quiz Results Recorded)")
    user.history = history
    
    if len(scores) >= 3:
        add_badge("Quiz Master Badge", "fa-solid fa-crown text-cyan")
        
    if percentage >= 80:
        add_badge("Fast Learner Badge", "fa-solid fa-rocket text-yellow")
    
    user_weak_areas = list(user.weak_areas)
    for topic in weak_topics:
        if len(topic) < 30:
            user_weak_areas.append(topic)
    user.weak_areas = user_weak_areas
    
    db.session.commit()
        
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
    user = get_user()
    
    topics = [t.strip() for t in topics_raw.split(',') if t.strip()]
    if not topics:
        topics = list(set(user.weak_areas))[-5:] if user.weak_areas else ["Literature Review", "Practice Test", "Concept Mapping"]
        
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
        
    history = list(user.history)
    history.append("Generated Study Plan")
    user.history = history
    db.session.commit()
    
    return jsonify({"plan": plan})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    question = data.get('question', '').strip()
    text = session.get('current_text', '')
    
    if not question:
        return jsonify({"answer": "Please ask a question."})
        
    try:
        # Use Groq AI for much better responses
        if not text:
            system_prompt = """
            You are a highly intelligent Study Assistant. 
            The user has not uploaded any study material yet.
            Answer their questions generally and offer helpful educational advice.
            Keep your answers clear, professional, and helpful.
            """
        else:
            system_prompt = f"""
            You are a highly intelligent Study Assistant. 
            The context provided below is the content of the student's study material.
            Always answer questions based on this context. If the answer isn't in the context, say you don't know but try to offer general educational advice.
            Keep your answers clear, professional, and helpful.
            
            STUDY MATERIAL CONTEXT:
            {text[:15000]} # Limiting context for token limits
            """
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.5,
            max_tokens=600,
            top_p=1,
            stream=False
        )
        
        answer = completion.choices[0].message.content
        return jsonify({"answer": answer})
        
    except Exception as e:
        print(f"Groq Error: {str(e)}")
        return jsonify({"answer": "I'm having trouble connecting to my AI brain. Please try again in a moment."})

@app.route('/api/progress', methods=['GET'])
def get_progress():
    user = get_user()
    weak_counts = Counter(user.weak_areas).most_common(5)
    formatted_weak_areas = [{"topic": item[0], "count": item[1]} for item in weak_counts]
    
    return jsonify({
        "scores": user.scores[-10:],
        "history": user.history[-10:],
        "weak_areas": formatted_weak_areas,
        "xp": user.xp,
        "level": user.level,
        "badges": user.badges
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
