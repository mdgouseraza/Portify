import io
import json
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
app.config["SECRET_KEY"] = "prooffolio-secret-key-2026"
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
    # Contact & resume fields
    email            = db.Column(db.Text)
    phone            = db.Column(db.Text)
    # Legacy project columns (kept for backward compat)
    proj1_title      = db.Column(db.Text)
    proj1_stack      = db.Column(db.Text)
    proj1_desc       = db.Column(db.Text)
    proj2_title      = db.Column(db.Text)
    proj2_stack      = db.Column(db.Text)
    proj2_desc       = db.Column(db.Text)
    # Dynamic projects stored as JSON
    projects_json    = db.Column(db.Text)
    # Skills
    skills_languages = db.Column(db.Text)
    skills_dev       = db.Column(db.Text)
    skills_other     = db.Column(db.Text)
    interests        = db.Column(db.Text)


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
        "projects_json",
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
        usn  = request.form.get("usn",  "").strip()

        if not name or not usn:
            flash("Name and USN are required.", "error")
            return render_template("index.html")

        branch         = request.form.get("branch",         "").strip()
        grad_year_raw  = request.form.get("grad_year",      "").strip()
        grad_year      = int(grad_year_raw) if grad_year_raw.isdigit() else None
        linkedin       = request.form.get("linkedin",       "").strip()
        github         = request.form.get("github",         "").strip()
        semester_marks = request.form.get("semester_marks", "").strip()
        certifications = request.form.get("certifications", "").strip()
        achievements   = request.form.get("achievements",   "").strip()
        email          = request.form.get("email",          "").strip()
        phone          = request.form.get("phone",          "").strip()
        skills_languages = request.form.get("skills_languages", "").strip()
        skills_dev       = request.form.get("skills_dev",       "").strip()
        skills_other     = request.form.get("skills_other",     "").strip()
        interests        = request.form.get("interests",        "").strip()

        # ── Dynamic projects ──────────────────────────────────────────────
        MAX_PROJECTS = 20
        proj_data = {}
        for i in range(1, MAX_PROJECTS + 1):
            title = request.form.get(f"proj{i}_title", "").strip()
            if not title:
                break
            proj_data[str(i)] = {
                "title": title,
                "stack": request.form.get(f"proj{i}_stack", "").strip(),
                "desc":  request.form.get(f"proj{i}_desc",  "").strip(),
            }

        projects_json = json.dumps(proj_data) if proj_data else None

        # Legacy proj1/proj2 mirror (professor dashboard may still display these)
        proj1_title = proj_data.get("1", {}).get("title", "")
        proj1_stack = proj_data.get("1", {}).get("stack", "")
        proj1_desc  = proj_data.get("1", {}).get("desc",  "")
        proj2_title = proj_data.get("2", {}).get("title", "")
        proj2_stack = proj_data.get("2", {}).get("stack", "")
        proj2_desc  = proj_data.get("2", {}).get("desc",  "")

        # Upsert: overwrite if USN exists
        student = Student.query.filter_by(usn=usn).first()
        if student:
            student.name             = name
            student.branch           = branch
            student.grad_year        = grad_year
            student.linkedin         = linkedin
            student.github           = github
            student.semester_marks   = semester_marks
            student.certifications   = certifications
            student.achievements     = achievements
            student.email            = email
            student.phone            = phone
            student.projects_json    = projects_json
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
                projects_json=projects_json,
                proj1_title=proj1_title, proj1_stack=proj1_stack, proj1_desc=proj1_desc,
                proj2_title=proj2_title, proj2_stack=proj2_stack, proj2_desc=proj2_desc,
                skills_languages=skills_languages, skills_dev=skills_dev,
                skills_other=skills_other, interests=interests,
            )
            db.session.add(student)
        db.session.commit()

        # ── Handle multiple certificate/proof uploads ─────────────────────
        cert_paths = []
        i = 1
        while True:
            cert_file = request.files.get(f"cert_file_{i}")
            if cert_file is None:
                break
            if cert_file and cert_file.filename:
                orig_name = secure_filename(cert_file.filename)
                ext = os.path.splitext(orig_name)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    cert_save_path = os.path.join(UPLOAD_DIR, f"{usn}_cert{i}{ext}")
                    cert_file.save(cert_save_path)
                    cert_paths.append(cert_save_path)
            i += 1

        # ── Handle mandatory profile picture ──────────────────────────────
        pic_path = None
        profile_pic = request.files.get("profile_pic")
        if profile_pic and profile_pic.filename:
            orig_name = secure_filename(profile_pic.filename)
            ext = os.path.splitext(orig_name)[1].lower()
            if ext in {".jpg", ".jpeg", ".png"}:
                pic_path = os.path.join(UPLOAD_DIR, f"{usn}_pic{ext}")
                profile_pic.save(pic_path)

        # ── Generate PDF and send as download ────────────────────────────
        try:
            pdf_bytes = generate_pdf(
                student,
                cert_paths=cert_paths,
                profile_pic_path=pic_path,
            )
        finally:
            for p in cert_paths:
                if os.path.exists(p):
                    os.remove(p)
            if pic_path and os.path.exists(pic_path):
                os.remove(pic_path)

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
        email    = request.form.get("email",    "").strip()
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
