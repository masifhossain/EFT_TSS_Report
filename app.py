import os
import sys
import logging
from datetime import datetime, date, timedelta
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename

from report_generator import parse_csv_files_grouped_by_taxi, generate_pdf_for_taxi, generate_pdf_for_taxi_tss


"""Resolve base paths for resources (templates/static) and data (uploads/output)."""
IS_FROZEN = bool(getattr(sys, 'frozen', False))


def _resolve_paths():
    """Return (base_data_dir, base_resource_dir).

    Handles frozen (PyInstaller) and dev modes, ensuring we always locate
    `templates/` and `static/` even if the folder is moved post-build.
    """

    def _candidate_resource_roots(base_path: str):
        candidates = []
        # Primary: PyInstaller temp extraction directory
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(os.path.abspath(meipass))
        # Secondary: _internal folder that ships with --onedir builds
        candidates.append(os.path.join(base_path, "_internal"))
        # Finally: the base folder itself (useful in dev mode or if user copies
        # templates/static alongside the EXE manually)
        candidates.append(base_path)
        # Also consider current working directory if different (paranoia)
        cwd = os.getcwd()
        if cwd not in candidates:
            candidates.append(cwd)
        return candidates

    if IS_FROZEN:
        exe_path = getattr(sys, 'executable', '') or sys.argv[0]
        base_dir = os.path.abspath(os.path.dirname(exe_path))

        # Change working directory to EXE location to ensure all relative paths resolve correctly
        try:
            original_cwd = os.getcwd()
            os.chdir(base_dir)
            print(f"Changed CWD from {original_cwd} to {os.getcwd()}")
        except Exception as exc:
            print(f"Failed to change CWD: {exc}")

        candidates = _candidate_resource_roots(base_dir)

        for candidate in candidates:
            templates_dir = os.path.join(candidate, "templates")
            if os.path.isdir(templates_dir):
                return base_dir, os.path.abspath(candidate)

        # If we reach here, templates/static are missing.
        # Fall back to base_dir but log a loud warning (rendering will still fail).
        print(
            "WARNING: Unable to locate templates directory. Checked candidates: "
            f"{candidates}"
        )
        return base_dir, base_dir

    # Development mode: base path is alongside source file
    base_dir = os.path.abspath(os.path.dirname(__file__))
    return base_dir, base_dir


BASE_DATA_DIR, BASE_RESOURCE_DIR = _resolve_paths()

UPLOAD_FOLDER = os.path.abspath(os.path.join(BASE_DATA_DIR, "uploads"))
OUTPUT_FOLDER = os.path.abspath(os.path.join(BASE_DATA_DIR, "output"))
TEMPLATE_FOLDER = os.path.abspath(os.path.join(BASE_RESOURCE_DIR, "templates"))
STATIC_FOLDER = os.path.abspath(os.path.join(BASE_RESOURCE_DIR, "static"))


def ensure_dirs():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


ensure_dirs()

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
app.secret_key = "dev-secret-key"  # replace for production

# File logger for portable builds (logs next to EXE/folder)
LOG_FILE = os.path.join(OUTPUT_FOLDER, 'app.log')
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configure logging to be less verbose for frozen builds
log_level = logging.WARNING if IS_FROZEN else logging.INFO
logging.basicConfig(
    filename=LOG_FILE,
    level=log_level,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Only print diagnostic info if not frozen (to avoid console spam)
if not IS_FROZEN:
    msg = f"App starting. IS_FROZEN={IS_FROZEN} BASE_RESOURCE_DIR={BASE_RESOURCE_DIR} BASE_DATA_DIR={BASE_DATA_DIR} UPLOAD_FOLDER={UPLOAD_FOLDER} OUTPUT_FOLDER={OUTPUT_FOLDER}"
    logging.info(msg)
    try:
        print(msg)
        print(f"Working Directory: {os.getcwd()}")
        print(f"Absolute UPLOAD_FOLDER: {os.path.abspath(UPLOAD_FOLDER)}")
        print(f"Absolute OUTPUT_FOLDER: {os.path.abspath(OUTPUT_FOLDER)}")
    except Exception:
        pass


def get_default_period():
    today = date.today()
    # Find last Monday (including today if today is Monday)
    last_monday = today - timedelta(days=(today.weekday() - 0) % 7)
    # Find next Sunday (including today if today is Sunday)
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    return last_monday, next_sunday


def _safe_filename_component(text: str) -> str:
    """Sanitize a string for use in filenames (remove slashes and illegal chars)."""
    if not text:
        return ""
    # Replace path separators and common illegal characters on Windows
    bad_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for ch in bad_chars:
        text = text.replace(ch, '-')
    # Use Werkzeug's secure_filename for extra safety
    return secure_filename(text)


@app.route("/")
def index():
    start, end = get_default_period()
    return render_template(
        "index.html",
        default_start=start.strftime("%Y-%m-%d"),
        default_end=end.strftime("%Y-%m-%d"),
        default_issued=date.today().strftime("%Y-%m-%d"),
        uploads_dir=UPLOAD_FOLDER,
        output_dir=OUTPUT_FOLDER,
    )


@app.route("/generate", methods=["POST"])
def generate():
    period_start_str = request.form.get("period_start")
    period_end_str = request.form.get("period_end")
    date_issued_str = request.form.get("date_issued")

    if not period_start_str or not period_end_str or not date_issued_str:
        flash("Please provide Period Start, Period End, and Date Issued.")
        return redirect(url_for("index"))

    try:
        period_start = datetime.strptime(period_start_str, "%Y-%m-%d").date()
        period_end = datetime.strptime(period_end_str, "%Y-%m-%d").date()
        date_issued = datetime.strptime(date_issued_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.")
        return redirect(url_for("index"))

    report_type = request.form.get("report_type", "eftpos").lower()
    files = request.files.getlist("csv_files")
    if not files or all(f.filename.strip() == "" for f in files):
        flash("Please upload at least one CSV file.")
        return redirect(url_for("index"))

    saved_files = []
    for f in files:
        if not f.filename:
            continue
        # Use a unique name to avoid collisions/locks on Windows
        orig = secure_filename(f.filename)
        base, ext = os.path.splitext(orig)
        unique = f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, unique)
        try:
            # Ensure destination directory exists at runtime
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            f.save(save_path)
            logging.info("Saved upload to %s", save_path)
        except PermissionError as e:
            # Provide a helpful error and abort cleanly
            flash(
                "Permission denied while saving uploaded file. Close any open files (e.g., in Excel), "
                "and ensure the 'uploads' folder is writable."
            )
            return redirect(url_for("index"))
        except FileNotFoundError as e:
            # Retry once after ensuring directory
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                f.save(save_path)
                logging.info("Saved upload to %s after retry", save_path)
            except Exception as e2:
                logging.exception("Failed to save upload to %s", save_path)
                flash("Failed to save uploaded file. Please try again.")
                return redirect(url_for("index"))
        saved_files.append(save_path)

    if not saved_files:
        flash("No files were uploaded.")
        return redirect(url_for("index"))

    # Parse CSVs grouped by taxi, filtered by period
    taxis_data, taxi_totals = parse_csv_files_grouped_by_taxi(saved_files, period_start, period_end)

    if not taxis_data:
        flash("No taxi data found in the provided period.")
        return redirect(url_for("index"))

    generated = []
    skipped_unknown = []
    for taxi, records in taxis_data.items():
        # Generate for any taxi that has records (D/S/T)
        if not records:
            continue
        # Name as <TAXI>_<YYYYMMDD>_EFTPOS_.pdf (sanitize components to avoid path issues)
        taxi_text = str(taxi).strip()
        # Avoid date-like or numeric-only taxi ids
        import re as _re
        if _re.match(r"^\d{1,2}[-/ ]\d{1,2}[-/ ]\d{2,4}$", taxi_text):
            taxi_text = 'UNKNOWN'
        taxi_safe = _safe_filename_component(taxi_text) or "UNKNOWN"
        # Skip UNKNOWN to avoid generating spurious files
        if taxi_safe == 'UNKNOWN':
            skipped_unknown.append(taxi_text or 'UNKNOWN')
            logging.info("Skipping UNKNOWN taxi group with records count=%d", len(records))
            continue
        date_safe = period_start.strftime('%Y%m%d')
        if report_type == 'tss':
            out_name = f"{taxi_safe}_{date_safe}_TSS.pdf"
        else:
            out_name = f"{taxi_safe}_{date_safe}_EFTPOS_.pdf"
        out_path = os.path.join(OUTPUT_FOLDER, out_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if report_type == 'tss':
            generate_pdf_for_taxi_tss(
                taxi=taxi,
                records=records,
                period_start=period_start,
                period_end=period_end,
                date_issued=date_issued,
                output_path=out_path,
                static_folder=STATIC_FOLDER,
            )
        else:
            generate_pdf_for_taxi(
                taxi=taxi,
                records=records,
                period_start=period_start,
                period_end=period_end,
                date_issued=date_issued,
                output_path=out_path,
                static_folder=STATIC_FOLDER,
            )
        logging.info("Generated report: %s", out_path)
        generated.append(out_name)

    return render_template(
        "result.html",
        files=generated,
        skipped_unknown=skipped_unknown,
        output_dir=OUTPUT_FOLDER,
    )


@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


@app.route("/open-output")
def open_output_folder():
    try:
        # Windows: open in Explorer
        os.startfile(OUTPUT_FOLDER)
    except Exception:
        pass
    return redirect(url_for('index'))


@app.route("/open-uploads")
def open_uploads_folder():
    try:
        os.startfile(UPLOAD_FOLDER)
    except Exception:
        pass
    return redirect(url_for('index'))


@app.route("/health")
def health():
    info = {
        'is_frozen': IS_FROZEN,
        'base_resource_dir': BASE_RESOURCE_DIR,
        'base_data_dir': BASE_DATA_DIR,
        'uploads_dir': UPLOAD_FOLDER,
        'output_dir': OUTPUT_FOLDER,
    }
    return info


if __name__ == "__main__":
    # Auto-open browser shortly after starting the server
    import threading, time, webbrowser

    def _open_browser_later():
        try:
            time.sleep(0.5)
            webbrowser.open_new("http://127.0.0.1:5000/")
        except Exception:
            pass

    threading.Thread(target=_open_browser_later, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=not IS_FROZEN, use_reloader=False)
