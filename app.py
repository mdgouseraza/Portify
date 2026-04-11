import io
import os

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_file, flash
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from report import generate_pdf

# ─────────────────────────────────────────────
# App & DB setup
# ─────────────────────────────────────────────

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "prooffolio-secret-key-2024"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'prooffolio.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────

class Student(db.Model):
    __tablename__ = "student"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    usn = db.Column(db.String(50), unique=True, nullable=False)
    branch = db.Column(db.String(100))
    grad_year = db.Column(db.Integer)
    linkedin = db.Column(db.String(300))
    github = db.Column(db.String(300))
    semester_marks = db.Column(db.Text)
    certifications = db.Column(db.Text)
    achievements = db.Column(db.Text)
    # Resume fields
    email           = db.Column(db.Text)
    phone           = db.Column(db.Text)
    proj1_title     = db.Column(db.Text)
    proj1_stack     = db.Column(db.Text)
    proj1_desc      = db.Column(db.Text)
    proj2_title     = db.Column(db.Text)
    proj2_stack     = db.Column(db.Text)
    proj2_desc      = db.Column(db.Text)
    skills_languages= db.Column(db.Text)
    skills_dev      = db.Column(db.Text)
    skills_other    = db.Column(db.Text)
    interests       = db.Column(db.Text)


class Professor(db.Model):
    __tablename__ = "professor"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    name = db.Column(db.String(200))


# ─────────────────────────────────────────────
# DB init & seeding
# ─────────────────────────────────────────────

def init_db():
    db.create_all()

    # Safely migrate: add new columns to existing student table if missing
    import sqlite3
    db_path = os.path.join(BASE_DIR, "prooffolio.db")
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(student)").fetchall()}
    new_cols = [
        "email", "phone",
        "proj1_title", "proj1_stack", "proj1_desc",
        "proj2_title", "proj2_stack", "proj2_desc",
        "skills_languages", "skills_dev", "skills_other",
        "interests",
    ]
    for col in new_cols:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE student ADD COLUMN {col} TEXT")
            print(f"[ProofFolio] Added column: {col}")
    conn.commit()
    conn.close()

    # Seed default professor if not present
    if not Professor.query.filter_by(email="prof@prooffolio.com").first():
        hashed = generate_password_hash("professor123")
        prof = Professor(
            email="prof@prooffolio.com",
            password=hashed,
            name="Default Professor",
        )
        db.session.add(prof)
        db.session.commit()
        print("[ProofFolio] Seeded default professor: prof@prooffolio.com")


# ─────────────────────────────────────────────
# Student routes
# ─────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        usn = request.form.get("usn", "").strip()

        if not name or not usn:
            flash("Name and USN are required.", "error")
            return render_template("index.html")

        branch = request.form.get("branch", "").strip()
        grad_year_raw = request.form.get("grad_year", "").strip()
        grad_year = int(grad_year_raw) if grad_year_raw.isdigit() else None
        linkedin = request.form.get("linkedin", "").strip()
        github = request.form.get("github", "").strip()
        semester_marks = request.form.get("semester_marks", "").strip()
        certifications = request.form.get("certifications", "").strip()
        achievements  = request.form.get("achievements",  "").strip()
        # Resume fields
        email            = request.form.get("email",            "").strip()
        phone            = request.form.get("phone",            "").strip()
        proj1_title      = request.form.get("proj1_title",      "").strip()
        proj1_stack      = request.form.get("proj1_stack",      "").strip()
        proj1_desc       = request.form.get("proj1_desc",       "").strip()
        proj2_title      = request.form.get("proj2_title",      "").strip()
        proj2_stack      = request.form.get("proj2_stack",      "").strip()
        proj2_desc       = request.form.get("proj2_desc",       "").strip()
        skills_languages = request.form.get("skills_languages", "").strip()
        skills_dev       = request.form.get("skills_dev",       "").strip()
        skills_other     = request.form.get("skills_other",     "").strip()
        interests        = request.form.get("interests",        "").strip()

        # Upsert: overwrite if USN exists
        student = Student.query.filter_by(usn=usn).first()
        if student:
            student.name = name
            student.branch = branch
            student.grad_year = grad_year
            student.linkedin = linkedin
            student.github = github
            student.semester_marks = semester_marks
            student.certifications = certifications
            student.achievements  = achievements
            student.email            = email
            student.phone            = phone
            student.proj1_title      = proj1_title
            student.proj1_stack      = proj1_stack
            student.proj1_desc       = proj1_desc
            student.proj2_title      = proj2_title
            student.proj2_stack      = proj2_stack
            student.proj2_desc       = proj2_desc
            student.skills_languages = skills_languages
            student.skills_dev       = skills_dev
            student.skills_other     = skills_other
            student.interests        = interests
        else:
            student = Student(
                name=name, usn=usn, branch=branch, grad_year=grad_year,
                linkedin=linkedin, github=github,
                semester_marks=semester_marks,
                certifications=certifications,
                achievements=achievements,
                email=email, phone=phone,
                proj1_title=proj1_title, proj1_stack=proj1_stack, proj1_desc=proj1_desc,
                proj2_title=proj2_title, proj2_stack=proj2_stack, proj2_desc=proj2_desc,
                skills_languages=skills_languages, skills_dev=skills_dev,
                skills_other=skills_other, interests=interests,
            )
            db.session.add(student)
        db.session.commit()

        # Handle optional document upload
        doc_path = None
        uploaded_file = request.files.get("document")
        if uploaded_file and uploaded_file.filename:
            orig_name = secure_filename(uploaded_file.filename)
            ext = os.path.splitext(orig_name)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                doc_path = os.path.join(UPLOAD_DIR, f"{usn}_{orig_name}")
                uploaded_file.save(doc_path)

        # Generate PDF and send as download
        try:
            pdf_bytes = generate_pdf(student, document_path=doc_path)
        finally:
            if doc_path and os.path.exists(doc_path):
                os.remove(doc_path)

        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=f"{usn}_ProofFolio.pdf",
            mimetype="application/pdf",
        )

    return render_template("index.html")


# ─────────────────────────────────────────────
# Professor routes
# ─────────────────────────────────────────────

@app.route("/professor/login", methods=["GET", "POST"])
def professor_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        prof = Professor.query.filter_by(email=email).first()
        if prof and check_password_hash(prof.password, password):
            session["professor_id"] = prof.id
            return redirect(url_for("professor_dashboard"))
        flash("Invalid email or password.", "error")

    return render_template("professor_login.html")


@app.route("/professor/logout")
def professor_logout():
    session.pop("professor_id", None)
    return redirect(url_for("professor_login"))


@app.route("/professor/dashboard")
def professor_dashboard():
    if "professor_id" not in session:
        return redirect(url_for("professor_login"))

    students = Student.query.order_by(Student.name).all()
    return render_template("professor_dashboard.html", students=students)


@app.route("/professor/generate/<int:student_id>")
def professor_generate(student_id):
    if "professor_id" not in session:
        return redirect(url_for("professor_login"))

    student = Student.query.get_or_404(student_id)
    pdf_bytes = generate_pdf(student)
    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f"{student.usn}_ProofFolio.pdf",
        mimetype="application/pdf",
    )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
