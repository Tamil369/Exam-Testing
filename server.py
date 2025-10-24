from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import random
import os
from datetime import datetime

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24)  # Secret key for session management

# MongoDB configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/Students_Details"
mongo = PyMongo(app)

# Sample MCQ and MSQ questions
QUESTIONS = [
    {
        "id": 1,
        "type": "mcq",
        "question": "Which of the following is not a Python data type?",
        "options": ["List", "Tuple", "Class", "Dictionary"],
        "correct_answer": 2  # Index of correct option (0-based)
    },
    {
        "id": 2,
        "type": "msq",
        "question": "Which of the following are valid loop constructs in Python?",
        "options": ["for", "while", "do-while", "until"],
        "correct_answers": [0, 1]  # Indices of correct options
    },
    {
        "id": 3,
        "type": "mcq",
        "question": "What does HTML stand for?",
        "options": [
            "Hyper Text Markup Language",
            "High Tech Modern Language",
            "Hyper Transfer Markup Language",
            "Home Tool Markup Language"
        ],
        "correct_answer": 0
    },
    {
        "id": 4,
        "type": "msq",
        "question": "Which of these are JavaScript frameworks?",
        "options": ["React", "Django", "Angular", "Flask"],
        "correct_answers": [ 0, 2]
    },
    {
        "id": 5,
        "type": "mcq",
        "question": "Which symbol is used for comments in Python?",
        "options": ["//", "/* */", "#", "--"],
        "correct_answer": 2
    },
    {
        "id": 6,
        "type": "msq",
        "question": "Which data structures are built-in in Python?",
        "options": ["Array", "List", "Stack", "Dictionary"],
        "correct_answers": [1, 3]
    },
    {
        "id": 7,
        "type": "mcq",
        "question": "What is the output of 2**3 in Python?",
        "options": ["6", "8", "9", "23"],
        "correct_answer": 1
    },
    {
        "id": 8,
        "type": "msq",
        "question": "Which of these are valid Python variable names?",
        "options": ["_var", "2var", "var-name", "var_name"],
        "correct_answers": [0, 3]
    },
    {
        "id": 9,
        "type": "mcq",
        "question": "Which method is used to add an element to a list in Python?",
        "options": ["add()", "append()", "insert()", "push()"],
        "correct_answer": 1
    },
    {
        "id": 10,
        "type": "msq",
        "question": "Which of these are web development technologies?",
        "options": ["HTML", "CSS", "SQL", "Java"],
        "correct_answers": [0, 1]
    }
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    # Get all results sorted by score (descending) and time taken (ascending)
    results = list(mongo.db.Results.find().sort([
        ("score", -1), 
        ("time_taken", 1),
        ("submission_time", 1)
    ]))
    
    # Convert ObjectId to string for JSON serialization
    for result in results:
        result["_id"] = str(result["_id"])
        if "student_id" in result:
            result["student_id"] = str(result["student_id"])
    
    return render_template('admin.html', results=results)

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        name = data.get('name')
        reg_number = data.get('reg_number')
        email = data.get('email')
        
        # Store login time in session
        session['login_time'] = datetime.now().isoformat()
        
        # Check if student already exists in Details collection
        student = mongo.db.Details.find_one({"reg_number": reg_number})
        
        if not student:
            # Create new student record
            student_id = mongo.db.Details.insert_one({
                "name": name,
                "reg_number": reg_number,
                "email": email,
                "login_time": datetime.now()
            }).inserted_id
        else:
            student_id = student["_id"]
            # Update login time
            mongo.db.Details.update_one(
                {"_id": student_id},
                {"$set": {"login_time": datetime.now()}}
            )
        
        # Store student ID in session
        session['student_id'] = str(student_id)
        session['reg_number'] = reg_number
        session['name'] = name
        
        return jsonify({"success": True, "message": "Login successful"})
    
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/get_questions')
def get_questions():
    if 'student_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    # Shuffle questions for this student
    shuffled_questions = random.sample(QUESTIONS, min(10, len(QUESTIONS)))
    
    # Store the question order in session
    session['questions'] = [q['id'] for q in shuffled_questions]
    
    return jsonify({"questions": shuffled_questions})

@app.route('/submit', methods=['POST'])
def submit():
    if 'student_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.json
    answers = data.get('answers', [])
    cancelled = data.get('cancelled', False)
    malpractice_count = data.get('malpractice_count', 0)
    
    # Calculate time taken
    login_time = datetime.fromisoformat(session['login_time'])
    time_taken = (datetime.now() - login_time).total_seconds()
    
    # Calculate score if not cancelled
    score = 0
    total = len(answers)
    
    if not cancelled:
        for answer in answers:
            question_id = answer['question_id']
            # Find the question
            question = next((q for q in QUESTIONS if q['id'] == question_id), None)
            
            if question:
                if question['type'] == 'mcq':
                    # For MCQ, check if the selected option is correct
                    if answer.get('answer') == question['correct_answer']:
                        score += 1
                elif question['type'] == 'msq':
                    # For MSQ, check if all selected options are correct
                    user_answers = sorted(answer.get('answers', []))
                    correct_answers = sorted(question['correct_answers'])
                    
                    # Award points only if all answers are correct
                    if user_answers == correct_answers:
                        score += 1
    
    # Store results in database
    result_data = {
        "student_id": ObjectId(session['student_id']),
        "name": session['name'],
        "reg_number": session['reg_number'],
        "answers": answers,
        "score": score,
        "total": total,
        "time_taken": time_taken,
        "submission_time": datetime.now()
    }
    
    # Add cancellation info if exam was cancelled
    if cancelled:
        result_data["cancelled"] = True
        result_data["malpractice_count"] = malpractice_count
    
    result_id = mongo.db.Results.insert_one(result_data).inserted_id
    
    # Clear session
    session.clear()
    
    return jsonify({
        "success": True, 
        "score": score, 
        "total": total,
        "time_taken": time_taken,
        "cancelled": cancelled,
        "result_id": str(result_id)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9696)