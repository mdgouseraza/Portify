# ProofFolio 🎓

ProofFolio is a full-stack Python web application designed to help university students effortlessly build and download a professional academic portfolio and resume in seconds.

## ✨ Features and Capabilities

* **Student Flow (No Login Required):**
  * Modern, dark-themed, glassmorphism UI for data entry.
  * Captures personal info, academics, projects, skills, and interests.
  * File uploads: Students can attach certificates or mark sheets which are automatically merged into the final portfolio.
  * **Instant PDF Workflow:** Hits "Generate," saves data to SQLite, and streams back a custom 2-page PDF instantly.

* **Professor Flow (Secured Dashboard):**
  * Protected by secure session cookie authentication (hashed passwords).
  * Dashboard displaying all student submissions in a clean, filterable UI.
  * One-click "Generate PDF" action for an instructor to review a student's resume/portfolio natively.
  * Discreet dashboard access via the footer on the student page.

* **Dynamic Multi-Page PDF Generation:**
  * **Page 1 (Resume):** Clean, professional ATS-friendly layout. It features distinct sections for education, a 2-project detailed breakdown (with tech stacks), parsed list of skills (languages, dev logic, other), and interests.
  * **Page 2 (Portfolio & Validation):** Detailed academic portfolio incorporating a dynamically generated **QR Code**. The QR code links/embeds the student's essential data for verification.
  * **Attachments:** Uses PyPDF2 to append uploaded certificates directly to the end of the student's custom PDF.

## 🛠️ Tech Stack & Architecture

* **Backend Framework**: Python / Flask
* **Database**: SQLite with SQLAlchemy ORM
* **PDF Engine**: `ReportLab` (for canvas drawing, text formatting, line drawing) & `PyPDF2` (for PDF merging and appending)
* **QR Generation**: `qrcode[pil]`
* **Frontend**: Vanilla HTML / CSS (modern glassmorphism design, zero external CSS framework dependencies to keep styling localized and native).

## 📂 Codebase Deep-Dive

### 1. `app.py` (Core Application & Routing)
The central controller of the application.
- **Database Initialization (`init_db`):** Uses SQLite and SQLAlchemy. Features auto-migration logic (`PRAGMA table_info`) which dynamically adds new attributes to ongoing tables safely. It also auto-seeds the default professor account dynamically using `werkzeug.security.generate_password_hash`.
- **Routes:**
  - `/`: Handles student form data parsing, data fallback logic, SQLite upsert operations (updating records if the USN already exists), processing `multipart/form-data` uploads securely, and triggering the `generate_pdf` proxy stream.
  - `/professor/login`: Authentication layer verifying hashes.
  - `/professor/dashboard`: Session-protected dashboard viewer.
  - `/professor/generate/<id>`: On-demand remote PDF triggering mechanism.

### 2. `report.py` (The PDF Engine)
Handles all rigorous layout and byte-stream processing for the PDFs.
- **`generate_pdf(student, document_path)` main function:** Uses in-memory `io.BytesIO` streams rather than writing layout traces to the file system, reducing IO blocks and preventing disk bloat.
- **First Page (Resume Layout):**
  - Uses `reportlab.pdfgen.canvas`.
  - Manual typography configuration, calculating Y-axis spacing, horizontal dividing lines, and text wrapping based on standard A4 point measurements.
- **Second Page (Portfolio Layout):**
  - Triggers a `canvas.showPage()` push to start a new sheet.
  - Generates a QR image via `qrcode` mapping to the USN, converts to a temporary JPG, and uses `canvas.drawImage` to place the verification code seamlessly onto the canvas.
- **Document Merging:**
  - Leverages `PyPDF2.PdfReader/PdfWriter` to stitch the `ReportLab` output with the student's optionally uploaded `.pdf`, `.png`, or `.jpg` documents. Merges everything into one streamlined PDF stream shipped back to the Flask router.

### 3. Database Schema Models (`app.py`)
- **`Student`:** 
  - Over 20 columns covering Identity (`usn`, `name`), Professional metadata (`github`, `linkedin`), Resume segments (`proj1_title`, `skills_dev`), and additional Achievements.
- **`Professor`:**
  - High security mapping with `email`, `password` (hashed), and `name`.

### 4. `templates/` (UI/UX Layer)
- **`index.html`:** The student-facing portal. Features complex two-column CSS Grid layouts, custom glassmorphism layered elements, HTML5 validation, floating icon lockups, visual file-upload proxies, and loading states for submit interactions.
- **`professor_login.html` & `professor_dashboard.html`:** Instructor side portals with custom data-grid layouts, and dynamic flash-message rendering for authentication failures.

## 🚀 Setup & Installation

**1. Clone or navigate to the project directory:**
```bash
cd PBL/
```

**2. Create and activate a Virtual Environment:**
```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**3. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**4. Run the Application:**
```bash
python app.py
```
*(The database `prooffolio.db` and the default professor account will be automatically generated on the first run. Any table updates handle themselves automatically.)*

## 📖 Usage

Once the Flask server is running, you can access the application:

* **Student Portal:** [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
* **Professor Dashboard:** [http://127.0.0.1:5000/professor/login](http://127.0.0.1:5000/professor/login)
  *(Or use the discreet footer link on the Student Portal)*

### Default Professor Credentials
* **Email:** `prof@prooffolio.com`
* **Password:** `professor123`

---
*Developed for academic innovation.*
