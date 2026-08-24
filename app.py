import os
import uuid
from datetime import datetime, timedelta

import bcrypt
import pymysql
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename

from config import Config

CATEGORIES = ("Plumbing", "Electrical", "Cleaning", "Security", "Lift", "Parking", "Other")
STATUSES = ("Open", "In Progress", "Resolved")
PRIORITIES = ("Low", "Medium", "High")
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

app = Flask(__name__, template_folder="Templates", static_folder="Static")
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"]
mail = Mail(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_db():
    return pymysql.connect(
        host=app.config["MYSQL_HOST"], port=app.config["MYSQL_PORT"], user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"], database=app.config["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor, autocommit=False
    )


def database_error(template, message="Database connection failed. Check your MySQL settings and restart the app."):
    return render_template(template, error=message), 503


def resident_required():
    return "resident_id" in session


def admin_required():
    return "admin_id" in session


def is_overdue(complaint):
    return complaint["status"] != "Resolved" and complaint["created_at"] < datetime.now() - timedelta(days=app.config["OVERDUE_DAYS"])


def refresh_overdue(complaints):
    for complaint in complaints:
        complaint["is_overdue"] = is_overdue(complaint)
    return complaints


def send_email(subject, recipients, body):
    try:
        if app.config.get("MAIL_USERNAME") and recipients:
            mail.send(Message(subject=subject, recipients=recipients, body=body, sender=app.config["MAIL_DEFAULT_SENDER"]))
        return None
    except Exception as exc:
        return str(exc)


def complaint_email(complaint, resident, note):
    return send_email(
        f"Complaint CMP{complaint['id']:04d} status updated",
        [resident["email"]],
        f"Hello {resident['full_name']},\n\nYour maintenance complaint CMP{complaint['id']:04d} is now {complaint['status']}.\nCategory: {complaint['category']}\nAdmin note: {note or 'No note provided'}\n\nSociety Maintenance Tracker"
    )


@app.route("/")
def index():
    return redirect(url_for("dashboard" if resident_required() else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            db = get_db()
        except pymysql.MySQLError:
            return database_error("index.html")
        with db.cursor() as cur:
            cur.execute("SELECT * FROM residents WHERE email=%s", (request.form["email"].strip().lower(),))
            resident = cur.fetchone()
        db.close()
        if resident and bcrypt.checkpw(request.form["password"].encode(), resident["password"].encode()):
            session.pop("admin_id", None)
            session.pop("admin_name", None)
            session["resident_id"] = resident["id"]
            session["resident_name"] = resident["full_name"]
            return redirect(url_for("dashboard"))
        return render_template("index.html", error="Invalid email or password")
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        unit_number = request.form.get("unit_number", "").strip()
        if not all((full_name, email, phone, unit_number, request.form.get("password"))):
            return render_template("register.html", error="Please complete every field")
        if len(full_name) > 120 or len(email) > 160 or len(phone) > 30 or len(unit_number) > 40:
            return render_template("register.html", error="One or more fields are too long")
        if request.form["password"] != request.form["confirm_password"]:
            return render_template("register.html", error="Passwords do not match")
        try:
            db = get_db()
            password = bcrypt.hashpw(request.form["password"].encode(), bcrypt.gensalt()).decode()
            with db.cursor() as cur:
                cur.execute("INSERT INTO residents (full_name,email,phone,unit_number,password) VALUES (%s,%s,%s,%s,%s)",
                            (full_name, email, phone, unit_number, password))
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            db.close()
            return render_template("register.html", error="That email is already registered")
        except pymysql.MySQLError:
            if "db" in locals():
                db.close()
            return database_error("register.html")
        db.close()
        return render_template("register-success.html")
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not resident_required():
        return redirect(url_for("login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) AS count FROM complaints WHERE resident_id=%s GROUP BY status", (session["resident_id"],))
        counts = {row["status"]: row["count"] for row in cur.fetchall()}
        cur.execute("SELECT * FROM notices ORDER BY is_important DESC, created_at DESC LIMIT 5")
        notices = cur.fetchall()
    db.close()
    return render_template("dashboard.html", counts=counts, notices=notices)


@app.route("/complaints/new", methods=["GET", "POST"])
def complaint_new():
    if not resident_required():
        return redirect(url_for("login"))
    if request.method == "POST":
        category = request.form.get("category", "")
        description = request.form.get("description", "").strip()
        if category not in CATEGORIES or not description:
            return render_template("complaint-form.html", error="Choose a valid category and describe the issue")
        photo = request.files.get("photo")
        photo_name = None
        if photo and photo.filename:
            safe_name = secure_filename(photo.filename)
            extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
            if not safe_name or extension not in IMAGE_EXTENSIONS:
                return render_template("complaint-form.html", error="Upload a JPG, PNG, or WebP image")
            photo_name = f"{uuid.uuid4().hex}.{extension}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], photo_name))
        try:
            db = get_db()
            with db.cursor() as cur:
                cur.execute("INSERT INTO complaints (resident_id,category,description,photo_path,status,priority) VALUES (%s,%s,%s,%s,'Open','Medium')",
                            (session["resident_id"], category, description, photo_name))
                complaint_id = cur.lastrowid
                cur.execute("INSERT INTO complaint_history (complaint_id,status,actor_id,actor_role,note) VALUES (%s,'Open',%s,'resident','Complaint submitted')", (complaint_id, session["resident_id"]))
            db.commit()
            db.close()
        except pymysql.MySQLError:
            if "db" in locals():
                db.rollback()
                db.close()
            if photo_name:
                photo_path = os.path.join(app.config["UPLOAD_FOLDER"], photo_name)
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            return render_template("complaint-form.html", error="Complaint could not be saved. Please try again")
        flash("Complaint submitted successfully", "success")
        return redirect(url_for("my_complaints"))
    return render_template("complaint-form.html")


@app.route("/complaints")
def my_complaints():
    if not resident_required():
        return redirect(url_for("login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM complaints WHERE resident_id=%s ORDER BY created_at DESC", (session["resident_id"],))
        complaints = refresh_overdue(cur.fetchall())
    db.close()
    return render_template("my-complaints.html", complaints=complaints)


@app.route("/complaints/<int:complaint_id>")
def complaint_detail(complaint_id):
    if not resident_required():
        return redirect(url_for("login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM complaints WHERE id=%s AND resident_id=%s", (complaint_id, session["resident_id"]))
        complaint = cur.fetchone()
        if not complaint:
            db.close()
            return redirect(url_for("my_complaints"))
        cur.execute("SELECT * FROM complaint_history WHERE complaint_id=%s ORDER BY created_at ASC", (complaint_id,))
        history = cur.fetchall()
    db.close()
    complaint["is_overdue"] = is_overdue(complaint)
    return render_template("complaint-detail.html", complaint=complaint, history=history)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not resident_required():
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        with db.cursor() as cur:
            cur.execute("UPDATE residents SET full_name=%s,phone=%s,unit_number=%s WHERE id=%s", (request.form["full_name"], request.form["phone"], request.form["unit_number"], session["resident_id"]))
        db.commit()
        session["resident_name"] = request.form["full_name"]
        flash("Profile updated", "success")
    with db.cursor() as cur:
        cur.execute("SELECT * FROM residents WHERE id=%s", (session["resident_id"],))
        resident = cur.fetchone()
    db.close()
    return render_template("profile.html", resident=resident)


@app.route("/notices")
def notices():
    if not resident_required():
        return redirect(url_for("login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM notices ORDER BY is_important DESC, created_at DESC")
        rows = cur.fetchall()
    db.close()
    return render_template("notices.html", notices=rows)


@app.route("/complaints/<int:complaint_id>/photo")
def complaint_photo(complaint_id):
    if not resident_required() and not admin_required():
        return redirect(url_for("login"))
    db = get_db()
    with db.cursor() as cur:
        if admin_required():
            cur.execute("SELECT photo_path FROM complaints WHERE id=%s", (complaint_id,))
        else:
            cur.execute("SELECT photo_path FROM complaints WHERE id=%s AND resident_id=%s", (complaint_id, session["resident_id"]))
        complaint = cur.fetchone()
    db.close()
    if not complaint or not complaint["photo_path"]:
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], complaint["photo_path"])


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        try:
            db = get_db()
        except pymysql.MySQLError:
            return database_error("admin-login.html")
        with db.cursor() as cur:
            cur.execute("SELECT * FROM admins WHERE username=%s", (request.form["username"],))
            admin = cur.fetchone()
        db.close()
        if admin and bcrypt.checkpw(request.form["password"].encode(), admin["password"].encode()):
            session.pop("resident_id", None)
            session.pop("resident_name", None)
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]
            return redirect(url_for("admin_dashboard"))
        return render_template("admin-login.html", error="Invalid admin credentials")
    return render_template("admin-login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    return redirect(url_for("admin_login"))


def admin_complaint_query(apply_filters=True):
    filters, values = [], []
    for key in ("category", "status", "priority") if apply_filters else ():
        if request.args.get(key):
            filters.append(f"c.{key}=%s")
            values.append(request.args[key])
    if apply_filters and request.args.get("date"):
        filters.append("DATE(c.created_at)=%s")
        values.append(request.args["date"])
    where = " WHERE " + " AND ".join(filters) if filters else ""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(f"SELECT c.*,r.full_name,r.unit_number FROM complaints c JOIN residents r ON r.id=c.resident_id{where} ORDER BY c.created_at DESC", values)
        complaints = refresh_overdue(cur.fetchall())
    db.close()
    if apply_filters and request.args.get("overdue"):
        complaints = [c for c in complaints if c["is_overdue"]]
    complaints.sort(key=lambda c: c["is_overdue"], reverse=True)
    return complaints


@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))
    complaints = admin_complaint_query(apply_filters=False)
    by_status = {status: sum(c["status"] == status for c in complaints) for status in ["Open", "In Progress", "Resolved"]}
    by_category = {}
    for complaint in complaints:
        by_category[complaint["category"]] = by_category.get(complaint["category"], 0) + 1
    return render_template("admin-dashboard.html", complaints=complaints[:8], by_status=by_status, by_category=by_category, overdue=sum(c["is_overdue"] for c in complaints))


@app.route("/admin/complaints")
def admin_complaints():
    if not admin_required():
        return redirect(url_for("admin_login"))
    return render_template("admin-complaints.html", complaints=admin_complaint_query(), filters=request.args)


@app.route("/admin/complaints/<int:complaint_id>")
def admin_complaint_detail(complaint_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT c.*,r.full_name,r.email,r.phone,r.unit_number FROM complaints c JOIN residents r ON r.id=c.resident_id WHERE c.id=%s", (complaint_id,))
        complaint = cur.fetchone()
        cur.execute("SELECT * FROM complaint_history WHERE complaint_id=%s ORDER BY created_at ASC", (complaint_id,))
        history = cur.fetchall()
    db.close()
    if not complaint:
        return redirect(url_for("admin_complaints"))
    complaint["is_overdue"] = is_overdue(complaint)
    return render_template("admin-complaint-detail.html", complaint=complaint, history=history)


@app.route("/admin/complaints/<int:complaint_id>/update", methods=["POST"])
def admin_update_complaint(complaint_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    new_status = request.form.get("status", "")
    priority = request.form.get("priority", "")
    note = request.form.get("note", "").strip()[:500]
    if new_status not in STATUSES or priority not in PRIORITIES:
        flash("Choose a valid status and priority", "error")
        return redirect(url_for("admin_complaint_detail", complaint_id=complaint_id))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT c.*,r.full_name,r.email FROM complaints c JOIN residents r ON r.id=c.resident_id WHERE c.id=%s", (complaint_id,))
        complaint = cur.fetchone()
        if not complaint:
            db.close()
            flash("Complaint not found", "error")
            return redirect(url_for("admin_complaints"))
        if complaint["status"] == "Resolved":
            db.close()
            flash("Resolved complaints are closed and cannot be changed", "warning")
            return redirect(url_for("admin_complaint_detail", complaint_id=complaint_id))
        status_changed = new_status != complaint["status"]
        resolved_at = datetime.now() if new_status == "Resolved" else None
        cur.execute("UPDATE complaints SET status=%s,priority=%s,updated_at=NOW(),resolved_at=%s WHERE id=%s", (new_status, priority, resolved_at, complaint_id))
        if status_changed:
            cur.execute("INSERT INTO complaint_history (complaint_id,status,actor_id,actor_role,note) VALUES (%s,%s,%s,'admin',%s)", (complaint_id, new_status, session["admin_id"], note))
        db.commit()
        cur.execute("SELECT * FROM complaints WHERE id=%s", (complaint_id,))
        updated = cur.fetchone()
    db.close()
    flash("Complaint updated successfully", "success")
    if status_changed:
        error = complaint_email(updated, complaint, note)
        if error:
            flash("Complaint updated, but email could not be sent", "warning")
    return redirect(url_for("admin_complaint_detail", complaint_id=complaint_id))


@app.route("/admin/residents")
def admin_residents():
    if not admin_required():
        return redirect(url_for("admin_login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM residents ORDER BY created_at DESC")
        residents = cur.fetchall()
    db.close()
    return render_template("admin-residents.html", residents=residents)


@app.route("/admin/notices", methods=["GET", "POST"])
def admin_notices():
    if not admin_required():
        return redirect(url_for("admin_login"))
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not content or len(title) > 180:
            db.close()
            flash("Enter a title and notice message", "error")
            return redirect(url_for("admin_notices"))
        important = 1 if request.form.get("is_important") else 0
        with db.cursor() as cur:
            cur.execute("INSERT INTO notices (title,content,is_important,created_by) VALUES (%s,%s,%s,%s)", (title, content, important, session["admin_id"]))
            if important:
                cur.execute("SELECT email FROM residents")
                recipients = [r["email"] for r in cur.fetchall()]
        db.commit()
        db.close()
        if important:
            error = send_email("Important society notice", recipients, f"{title}\n\n{content}")
            if error:
                flash("Notice posted, but email could not be sent", "warning")
        flash("Notice posted", "success")
        return redirect(url_for("admin_notices"))
    with db.cursor() as cur:
        cur.execute("SELECT * FROM notices ORDER BY is_important DESC,created_at DESC")
        rows = cur.fetchall()
    db.close()
    return render_template("admin-notices.html", notices=rows)


@app.route("/admin/notices/<int:notice_id>/delete", methods=["POST"])
def admin_delete_notice(notice_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM notices WHERE id=%s", (notice_id,))
    db.commit()
    db.close()
    return redirect(url_for("admin_notices"))


@app.errorhandler(413)
def file_too_large(_error):
    return render_template("complaint-form.html", error="That photo is too large. Choose an image under 5 MB"), 413


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
