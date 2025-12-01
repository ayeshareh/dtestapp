import streamlit as st
import os
import json
import pandas as pd
import glob
from datetime import datetime
import requests
import re

# -------------------------------
# GEMINI API CONFIG
# -------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"

# -------------------------------
# GEMINI API CALL
# -------------------------------
def gemini_chat(prompt: str):
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(GEMINI_URL, json=data)
    if response.status_code != 200:
        raise Exception(f"Gemini API Error {response.status_code}: {response.text}")
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

# -------------------------------
# QUIZ GENERATION WITH RETRY
# -------------------------------
def generate_quiz(categories: str):
    prompt = f"""
You are an expert cybersecurity instructor.
Always respond ONLY in STRICT JSON.

Create a cybersecurity quiz with EXACTLY 10 MCQs.

STRICT FORMAT ONLY:

{{
    "quiz": [
        {{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct": "A", "explanation": "..."}}
    ]
}}

No extra text or paragraphs.

Topics:
{categories}
"""
    return gemini_chat(prompt).strip()

def parse_quiz(quiz_text: str):
    try:
        return json.loads(quiz_text)["quiz"]
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", quiz_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))["quiz"]
            except json.JSONDecodeError:
                st.error("❌ Gemini output contains invalid JSON. Try regenerating the quiz.")
                return []
        else:
            st.error("❌ Could not find JSON in Gemini response. Try regenerating the quiz.")
            return []

def generate_quiz_with_retry(categories, retries=3):
    for _ in range(retries):
        text = generate_quiz(categories)
        parsed = parse_quiz(text)
        if parsed:
            return parsed, text
    st.error("❌ Failed to generate valid JSON quiz after multiple attempts.")
    return [], ""

# -------------------------------
# SAVE / LOAD QUIZ
# -------------------------------
def save_quiz_file(quiz_text):
    with open("latest_quiz.json", "w") as f:
        json.dump({"quiz_text": quiz_text}, f, indent=4)

def load_quiz_file():
    try:
        with open("latest_quiz.json", "r") as f:
            return json.load(f)["quiz_text"]
    except FileNotFoundError:
        return None

# -------------------------------
# SAVE STUDENT RESULTS
# -------------------------------
def save_student_results(student_name, score, parsed_questions, user_answers):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    results = []
    for i, q in enumerate(parsed_questions):
        results.append({
            "question": q["question"],
            "student_answer": user_answers[i],
            "correct_answer": q["correct"],
            "explanation": q["explanation"]
        })
    filename = f"results_{student_name}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump({"student_name": student_name, "score": score, "answers": results}, f, indent=4)
    return filename

def load_all_results():
    all_res = []
    for file in glob.glob("results_*.json"):
        with open(file, "r") as f:
            all_res.append(json.load(f))
    return all_res

# -------------------------------
# STREAMLIT APP
# -------------------------------
st.set_page_config(
    page_title="Cybersecurity Quiz Platform",
    page_icon="🔐",
    layout="wide",
)

st.title("🔐 Cybersecurity Quiz Platform (GEMINI Version)")

tabs = st.tabs(["Teacher", "Student"])

# -------------------------------
# TEACHER MODE
# -------------------------------
with tabs[0]:
    st.subheader("📌 Teacher Dashboard")
    st.markdown("Create and manage quizzes for students.")

    categories_input = st.text_area(
        "Enter Topics / Categories:",
        "Introduction to Cybersecurity"
    )
    
    if st.button("Generate Quiz"):
        if not categories_input.strip():
            st.error("Please enter at least one category.")
        else:
            with st.spinner("Generating quiz via Gemini..."):
                parsed, quiz_text = generate_quiz_with_retry(categories_input)
                if parsed:
                    save_quiz_file(quiz_text)
                    st.success("✅ Quiz generated successfully!")
                    st.markdown("### Sample Questions Preview:")
                    for i, q in enumerate(parsed[:3], 1):
                        st.markdown(f"**Q{i}: {q['question']}**")
                        st.write(q["options"])

    st.subheader("📊 All Student Results")
    all_results = load_all_results()
    if all_results:
        df = pd.DataFrame([{"Student": r["student_name"], "Score": r["score"]} for r in all_results])
        df = df.sort_values(by="Score", ascending=False).reset_index(drop=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No student results yet.")

# -------------------------------
# STUDENT MODE
# -------------------------------
with tabs[1]:
    st.subheader("📝 Take Quiz")
    student_name = st.text_input("Enter Your Name:").strip().replace(" ", "_") or "Unknown"

    quiz_text = load_quiz_file()
    if not quiz_text:
        st.warning("Quiz not generated yet. Please ask your teacher to generate a quiz.")
    else:
        parsed_questions = parse_quiz(quiz_text)
        if parsed_questions:
            # Initialize session state for answers
            if "user_answers" not in st.session_state:
                st.session_state.user_answers = [""] * len(parsed_questions)

            # Progress bar
            answered_count = len([a for a in st.session_state.user_answers if a])
            st.progress(answered_count / len(parsed_questions))

            # Question navigation slider
            question_index = st.slider("Select Question", 1, len(parsed_questions), 1)
            q = parsed_questions[question_index - 1]

            # Unique key for each question
            key = f"q_{question_index}"
            st.markdown(f"**Q{question_index}: {q['question']}**")

            # Safely find previous selection index
            prev_answer = st.session_state.user_answers[question_index - 1]
            if prev_answer in q["options"]:
                default_index = q["options"].index(prev_answer)
            else:
                default_index = 0

            ans = st.radio(
                "Choose your answer:",
                q["options"],
                index=default_index,
                key=key
            )
            st.session_state.user_answers[question_index - 1] = ans

            # Submit button
            if st.button("Submit Quiz"):
                score = 0
                unanswered = []
                for i, q in enumerate(parsed_questions):
                    answer = st.session_state.user_answers[i]
                    if not answer:
                        unanswered.append(i+1)
                    else:
                        chosen_letter = answer[0]
                        if chosen_letter == q["correct"]:
                            score += 1

                if unanswered:
                    st.warning(f"⚠️ You have not answered questions: {unanswered}")
                    st.info("Please answer all questions before submitting.")
                else:
                    st.success(f"🎉 {student_name}, you scored {score} / {len(parsed_questions)}")
                    filename = save_student_results(student_name, score, parsed_questions, st.session_state.user_answers)
                    st.info(f"Results saved as **{filename}**")

                    # Show correct answers and explanations
                    st.markdown("### ✅ Correct Answers & Explanations")
                    for i, q in enumerate(parsed_questions):
                        st.markdown(f"**Q{i+1}: {q['question']}**")
                        st.write(f"Your Answer: {st.session_state.user_answers[i]}")
                        st.write(f"Correct Answer: {q['correct']}")
                        st.write(f"Explanation: {q['explanation']}")
