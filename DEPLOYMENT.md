# Simple Setup And Deployment

## Local Windows Setup

Use one PowerShell window. Do not start Flask from another window.

1. Open PowerShell.
2. Go to the project folder:

```powershell
cd "C:\Users\aditi\Downloads\College-Complaint-System-main\College-Complaint-System-main"
```

3. Install packages once:

```powershell
python -m pip install -r requirements.txt
```

4. Run the setup script:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-local.ps1
```

5. Enter the MySQL root password when asked. The script will:
   - Check MySQL login
   - Create `society_maintenance`
   - Create all tables
   - Start Flask with the correct password

6. Open:

```text
http://127.0.0.1:5000/register
```

The script keeps the password only in the running PowerShell process. It does not write the password to a project file.

## Create The Admin

Run this in a separate PowerShell window while the app is running:

```powershell
cd "C:\Users\aditi\Downloads\College-Complaint-System-main\College-Complaint-System-main"
python -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode())"
```

Copy the generated hash, open MySQL, and run:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

Then:

```sql
USE society_maintenance;
INSERT INTO admins (username, password) VALUES ('admin', 'PASTE_THE_HASH_HERE');
```

If the admin already exists, use:

```sql
UPDATE admins SET password = 'PASTE_THE_HASH_HERE' WHERE username = 'admin';
```

Admin login:

```text
URL: http://127.0.0.1:5000/admin/login
Username: admin
Password: admin123
```

## Hosted MySQL

Create a MySQL database with your provider first. Note its host, port, database name, username, and password.

Run `schema-hosted.sql` in that provider's SQL console. Do not run `schema.sql` on a hosted database if the provider has already created the database, because `schema.sql` contains `CREATE DATABASE` and `USE society_maintenance`.

Create the admin hash locally using the command above, then run the admin `INSERT` in the hosted SQL console.

## Render

1. Push the project to GitHub.
2. In Render, create a Web Service from the repository.
3. Build command:

```text
pip install -r requirements.txt
```

4. Start command:

```text
gunicorn app:app
```

5. Add these environment variables in Render:

```text
SECRET_KEY=<generate a random value>
MYSQL_HOST=<hosted MySQL host>
MYSQL_PORT=<hosted MySQL port>
MYSQL_USER=<hosted MySQL username>
MYSQL_PASSWORD=<hosted MySQL password>
MYSQL_DB=<hosted database name>
OVERDUE_DAYS=3
```

6. Optional email variables:

```text
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<SMTP email>
MAIL_PASSWORD=<SMTP app password>
MAIL_DEFAULT_SENDER=<same SMTP email>
```

7. Deploy and open the Render URL.

## If Something Fails

Check these in order:

1. MySQL service is running.
2. `setup-local.ps1` prints `Database is ready.`
3. Flask is started by the same setup script.
4. The browser URL uses the same port shown by Flask.
5. Hosted environment variables exactly match the hosted MySQL provider.
6. `schema-hosted.sql` was run in the selected hosted database.

Never commit `.env`, a MySQL password, or uploaded photos.
