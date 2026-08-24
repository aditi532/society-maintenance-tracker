# Society Maintenance Tracker

A hackathon-scale platform where residents raise maintenance complaints and track progress, while admins prioritize work, update statuses, publish notices, and monitor overdue issues.

## Live Application

**Hosted application:** [Open Society Maintenance Tracker](PASTE_YOUR_RENDER_URL_HERE)

Replace `PASTE_YOUR_RENDER_URL_HERE` with the final Render URL after deployment, for example:

```text
https://society-maintenance-tracker.onrender.com
```

**Source code:** [GitHub repository](https://github.com/aditi532/society-maintenance-tracker)

### Demo Access

```text
Resident registration: <HOSTED_URL>/register
Resident login:        <HOSTED_URL>/login
Admin login:           <HOSTED_URL>/admin/login

Admin username: admin
Admin password: admin123
```

Create a resident account from the registration page to demonstrate the resident workflow.

## Technology

- Python 3.12 and Flask
- MySQL with PyMySQL
- HTML, CSS, JavaScript, and Jinja templates
- bcrypt password hashing
- Flask cookie sessions
- Flask-Mail SMTP notifications
- Gunicorn for hosted deployment

## Features

### Resident

- Register and log in securely
- Raise a complaint with category, description, and optional photo
- View only their own complaints
- Follow complete timestamped status history and admin notes
- Read notices with important notices pinned first
- Receive email when a complaint status changes or an important notice is posted

### Admin

- Separate role-protected login and dashboard
- View every complaint and filter by category, status, priority, date, or overdue state
- Set priority to Low, Medium, or High
- Move complaints through Open, In Progress, and Resolved
- Add an optional note to a status update
- View complaint photos and complete history
- View totals by status/category and overdue count
- Publish and delete notices
- Mark notices important to pin and email them

Resolved complaints are closed and cannot be reopened. Overdue status is calculated automatically from `OVERDUE_DAYS` and overdue complaints appear first in the admin queue.

## Project Structure

```text
app.py                 Flask routes and database operations
config.py              Environment-based configuration
schema.sql             Local MySQL database and table setup
schema-hosted.sql      Tables for an existing hosted MySQL database
requirements.txt       Python dependencies
Procfile               Gunicorn process command
render.yaml            Render configuration
.env.example           Environment variable template
Templates/             Jinja HTML pages
Static/css/style.css   Responsive visual design
Static/js/main.js      Small browser interactions
tests/test_app.py      Lightweight automated checks
DEPLOYMENT.md          Detailed local and hosted deployment guide
system-design.md       System design write-up (under 800 words)
SUBMISSION.md          Deliverable manifest
```

## Local Setup

### Quick Windows Setup

1. Install Python 3.12 and MySQL Server 8.
2. Open PowerShell in the project folder.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Run the helper:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-local.ps1
```

5. Enter the local MySQL root password when prompted.
6. Open `http://127.0.0.1:5000/register`.

The script checks MySQL, imports `schema.sql`, and starts Flask with the database settings in the same PowerShell process.

### Manual Environment Setup

The application reads operating-system environment variables. It also reads a local `.env` file when present. `.env` is ignored by Git and must never be committed.

Example `.env`:

```text
SECRET_KEY=local-hackathon-secret
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-local-mysql-password
MYSQL_DB=society_maintenance
OVERDUE_DAYS=3
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
```

Import the local schema:

```powershell
Get-Content -Raw ".\schema.sql" | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

Start Flask:

```powershell
python app.py
```

## Create An Admin

Generate a bcrypt hash for the demo password `admin123`:

```powershell
python -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode())"
```

Insert the generated hash:

```sql
USE society_maintenance;
INSERT INTO admins (username, password)
VALUES ('admin', 'PASTE_GENERATED_HASH_HERE');
```

Admin URL: `http://127.0.0.1:5000/admin/login`

## Hosted Deployment

The GitHub repository is:

`https://github.com/aditi532/society-maintenance-tracker`

Recommended hackathon setup:

- Railway MySQL database
- Render Flask web service

Run `schema-hosted.sql` inside the database Railway provides. Do not run `schema.sql` against an already-created hosted database.

Render settings:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
```

Required Render variables:

```text
SECRET_KEY=<random value>
MYSQL_HOST=<Railway public host>
MYSQL_PORT=<Railway public port>
MYSQL_USER=<Railway username>
MYSQL_PASSWORD=<Railway password>
MYSQL_DB=<Railway database name>
OVERDUE_DAYS=3
```

Optional email variables:

```text
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<SMTP email>
MAIL_PASSWORD=<SMTP app password>
MAIL_DEFAULT_SENDER=<same SMTP email>
```

See `DEPLOYMENT.md` for the complete process.

## Route / API Documentation

This is a server-rendered Flask application. These HTTP routes form its backend API and return HTML or redirects rather than JSON.

| Method | Route | Access | Purpose |
|---|---|---|---|
| GET | `/` | Public | Redirect to resident login/dashboard |
| GET, POST | `/login` | Public | Resident authentication |
| GET, POST | `/register` | Public | Resident registration |
| GET | `/logout` | Resident | Clear resident session |
| GET | `/dashboard` | Resident | Personal counts and recent notices |
| GET, POST | `/complaints/new` | Resident | Submit complaint and optional photo |
| GET | `/complaints` | Resident | List own complaints |
| GET | `/complaints/<id>` | Resident | Own complaint and history |
| GET | `/complaints/<id>/photo` | Owner/Admin | Protected complaint photo |
| GET, POST | `/profile` | Resident | View/update profile |
| GET | `/notices` | Resident | Pinned notice board |
| GET, POST | `/admin/login` | Public | Admin authentication |
| GET | `/admin/logout` | Admin | Clear admin session |
| GET | `/admin/dashboard` | Admin | Status/category/overdue reporting |
| GET | `/admin/complaints` | Admin | Filtered work queue |
| GET | `/admin/complaints/<id>` | Admin | Complaint management and history |
| POST | `/admin/complaints/<id>/update` | Admin | Update status, priority, and note |
| GET | `/admin/residents` | Admin | Resident directory |
| GET, POST | `/admin/notices` | Admin | List/create notices |
| POST | `/admin/notices/<id>/delete` | Admin | Delete notice |

Admin complaint filters are query parameters:

```text
/admin/complaints?category=Plumbing&status=Open&priority=High&date=2026-08-24&overdue=1
```

## Database Schema

### `residents`

Account and apartment details: `id`, `full_name`, `email`, `phone`, `unit_number`, bcrypt `password`, `created_at`.

### `admins`

Admin credentials: `id`, `username`, bcrypt `password`, `created_at`.

### `complaints`

Current complaint state: resident, category, description, generated photo filename, status, priority, creation/update time, and resolution time.

### `complaint_history`

Append-only lifecycle records: complaint, resulting status, actor ID, actor role, optional note, and timestamp.

### `notices`

Notice title/content, important flag, creating admin, and timestamp.

See `schema.sql` and `schema-hosted.sql` for exact definitions and foreign keys.

## Tests

Run:

```powershell
python -m unittest discover -s tests -v
```

The suite checks route guards, overdue behavior, template compilation, complaint validation, image validation, unique filenames, history insertion, and admin update validation. MySQL-backed workflows should also be manually checked after deployment.

## Hackathon Limitations

- Emails are sent synchronously rather than through a job queue.
- Photos use the local filesystem. Free Render instances may lose uploaded photos after restart/redeploy.
- This uses Flask form routes instead of a separate JSON REST API.
- The project intentionally avoids production-level infrastructure and advanced security additions outside the hackathon scope.
