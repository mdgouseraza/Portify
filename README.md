# ProofFolio 🎓

**ProofFolio** is a full-stack Python (Flask) web application that lets university students instantly generate a professional academic portfolio and resume PDF — in seconds, with no login required.

> Built for GM University | Davangere, Karnataka, India

---

## ✨ Features

### 🎓 Student Flow (No Login Required)
- Modern **4-step wizard** UI with dark glassmorphism design
- **Step 1 — Personal Info:** Full Name, USN, Branch, Graduation Year, LinkedIn, GitHub, Profile Picture upload (with live circular preview)
- **Step 2 — Academic Details:** Semester Marks, Certifications, Achievements, optional Supporting Document upload
- **Step 3 — Projects & Skills:** Email, Phone, 2 Projects (Title, Stack, Description), Skills (Languages, Frameworks, Other/AI-ML), Interests/Summary
- **Step 4 — Preview:** Read-only summary of all fields before final PDF generation
- **Instant PDF download** on form submit — no page reload

### 🧑‍🏫 Professor Flow (Secured Dashboard)
- Login-protected dashboard with hashed password authentication
- View all student submissions in a clean data grid
- One-click **Generate PDF** per student directly from the dashboard
- Access via discreet footer link on the student page

### 📄 Dynamic 2-Page PDF Generation
- **Page 1 — Resume:**
  - Student's **profile photo** displayed in the top-right header corner
  - Name in bold centered ALL CAPS
  - Contact row: Email | Phone | LinkedIn | GitHub | India
  - Sections: **PROFESSIONAL SUMMARY**, **SKILLS**, **EDUCATION**, **PROJECTS**, **ACHIEVEMENTS & CERTIFICATIONS**
  - Clean ATS-friendly layout matching professional resume standards
  - Blue section headers with horizontal rule dividers
- **Page 2 — Portfolio:**
  - Profile photo + student name and identity details
  - Full academic breakdown: Semester Marks, Certifications, Achievements
  - Auto-generated **QR Code** encoding student identity for verification
- **Attachments:** Uploaded certificates/mark sheets (PDF/image) are appended as extra pages via PyPDF2

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask, SQLAlchemy |
| Database | SQLite (`prooffolio.db`) |
| PDF Engine | ReportLab (layout & drawing) + PyPDF2 (merging) |
| QR Code | `qrcode[pil]` |
| Auth | Werkzeug password hashing + Flask sessions |
| Frontend | Vanilla HTML/CSS — glassmorphism, dark theme, zero external CSS frameworks |

---

## 📂 Project Structure

```
PBL/
├── app.py                  # Flask routes, DB models, file handling
├── report.py               # PDF generation engine (resume + portfolio)
├── requirements.txt
├── prooffolio.db           # SQLite database (auto-created on first run)
├── uploads/                # Temporary upload storage (auto-cleaned)
└── templates/
    ├── index.html          # 4-step student wizard UI
    ├── professor_login.html
    └── professor_dashboard.html
```

---

## 🚀 Setup & Installation

**1. Clone the repository:**
```bash
git clone https://github.com/mdgouseraza/Portify.git
cd Portify
```

**2. Create and activate a virtual environment:**
```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Run the application:**
```bash
python app.py
```

> The database (`prooffolio.db`) and default professor account are created automatically on first run. Schema migrations are handled automatically via `PRAGMA table_info`.

---

## 📖 Usage

Once running, open your browser:

| Portal | URL |
|---|---|
| **Student Portal** | http://127.0.0.1:5000/ |
| **Professor Dashboard** | http://127.0.0.1:5000/professor/login |

### Default Professor Credentials
| Field | Value |
|---|---|
| Email | `prof@prooffolio.com` |
| Password | `professor123` |

---

## 🗂️ Database Models

### `Student`
Stores all student submission data including identity, academics, project details, skills, and contact info. Supports **upsert** — re-submitting with the same USN updates the existing record.

### `Professor`
Stores instructor credentials with hashed passwords. Seeded automatically with a default account.

---

## 📝 PDF Resume Sections (Page 1)

| Section | Source Field |
|---|---|
| Name & Photo | `name` + `profile_pic` upload |
| Contact | `email`, `phone`, `linkedin`, `github` |
| Professional Summary | `interests` field |
| Skills | `skills_languages`, `skills_dev`, `skills_other` |
| Education | `branch`, `grad_year`, `semester_marks` (CGPA parsed) |
| Projects | `proj1_*`, `proj2_*` (title, stack, description) |
| Achievements & Certs | `certifications` + `achievements` |

---

*Developed for academic innovation — GM University, Davangere.*
