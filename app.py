from __future__ import annotations

import os
import sqlite3
from typing import Dict, List, Optional, Tuple

from flask import Flask, g, redirect, render_template, request, session, url_for, flash, jsonify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "sat.db")

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"


# -------------------------
# DB helpers
# -------------------------
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stem TEXT NOT NULL,
            choice_a TEXT NOT NULL,
            choice_b TEXT NOT NULL,
            choice_c TEXT NOT NULL,
            choice_d TEXT NOT NULL,
            answer TEXT NOT NULL CHECK(answer IN ('A','B','C','D'))
        );
        """
    )
    db.commit()

    user_count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    q_count = db.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]

    if user_count == 0:
        db.execute("INSERT INTO users(username, password) VALUES(?, ?)", ("student", "1234"))
        db.commit()

    if q_count == 0:
        demo_questions = [
            ("If 3x + 5 = 20, what is the value of x?", "3", "4", "5", "6", "B"),
            ("A rectangle has length 10 and width 4. What is its area?", "14", "20", "30", "40", "D"),
            ("Which of the following is a prime number?", "21", "27", "29", "33", "C"),
            ("If f(x)=x^2, what is f(3)?", "6", "9", "12", "15", "B"),
        ]
        db.executemany(
            """
            INSERT INTO questions(stem, choice_a, choice_b, choice_c, choice_d, answer)
            VALUES(?,?,?,?,?,?)
            """,
            demo_questions,
        )
        db.commit()


def require_login() -> bool:
    return "user_id" in session


# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/practice")
def practice():
    return render_template("practice.html")




@app.route("/login", methods=["GET", "POST"])
def login():
    init_db()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db()
        user = db.execute(
            "SELECT id, username FROM users WHERE username=? AND password=?",
            (username, password),
        ).fetchone()

        if user:
            session.clear()
            session["user_id"] = int(user["id"])
            session["username"] = user["username"]
            return redirect(url_for("exam"))
        flash("用户名或密码不对（demo账号：student / 1234）")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/exam")
def exam():
    if not require_login():
        return redirect(url_for("login"))

    db = get_db()
    rows = db.execute(
        "SELECT id, stem, choice_a, choice_b, choice_c, choice_d FROM questions ORDER BY id ASC"
    ).fetchall()

    questions = [dict(r) for r in rows]

    return render_template("exam.html", questions=questions, username=session.get("username", ""))


@app.route("/submit", methods=["POST"])
def submit():
    if not require_login():
        return redirect(url_for("login"))

    answers: Dict[str, str] = request.form.to_dict()
    db = get_db()
    rows = db.execute("SELECT id, answer FROM questions").fetchall()
    key = {str(r["id"]): r["answer"] for r in rows}

    correct = 0
    total = len(key)
    detailed: List[Tuple[int, Optional[str], str, bool]] = []

    for qid_str, correct_ans in key.items():
        student_ans = answers.get(qid_str)
        is_right = (student_ans == correct_ans)
        if is_right:
            correct += 1
        detailed.append((int(qid_str), student_ans, correct_ans, is_right))

    score_pct = round(correct / total * 100, 1) if total else 0.0

    return render_template(
        "result.html",
        correct=correct,
        total=total,
        score_pct=score_pct,
        detailed=detailed,
        username=session.get("username", ""),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)


