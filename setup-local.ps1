$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"

if (-not (Test-Path -LiteralPath $mysql)) {
    $mysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
    if ($mysqlCommand) {
        $mysql = $mysqlCommand.Source
    } else {
        throw "MySQL was not found. Install MySQL Server 8 or update the mysql path in setup-local.ps1."
    }
}

Set-Location -LiteralPath $project
$password = Read-Host "Enter your MySQL root password" -AsSecureString
$passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
}

$env:SECRET_KEY = "local-hackathon-secret"
$env:MYSQL_HOST = "localhost"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "root"
$env:MYSQL_PASSWORD = $plainPassword
$env:MYSQL_DB = "society_maintenance"
$env:OVERDUE_DAYS = "3"

Write-Host "Checking MySQL connection..." -ForegroundColor Cyan
& $mysql --protocol=TCP -h localhost -P 3306 -u root "-p$plainPassword" -e "SELECT 1;"
if ($LASTEXITCODE -ne 0) {
    throw "MySQL login failed. Check the password and run this script again."
}

Write-Host "Creating/updating the society database..." -ForegroundColor Cyan
Get-Content -Raw -LiteralPath (Join-Path $project "schema.sql") | & $mysql --protocol=TCP -h localhost -P 3306 -u root "-p$plainPassword"
if ($LASTEXITCODE -ne 0) {
    throw "The schema could not be imported."
}

Write-Host "Database is ready." -ForegroundColor Green
Write-Host "Starting the website at http://127.0.0.1:5000" -ForegroundColor Green
python app.py
