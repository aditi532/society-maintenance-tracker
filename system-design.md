# System Design

## Overview

The Society Maintenance Tracker is a server-rendered Flask application backed by MySQL. Residents and admins use separate login routes, and Flask sessions store the authenticated account ID. Passwords are stored as bcrypt hashes. Jinja templates provide the frontend so the hackathon application does not need a separate API client or JavaScript framework.

## Complaint History Model

The `complaints` table stores the current state needed for fast lists and dashboards: resident, category, description, photo path, status, priority, creation/update time, and resolution time. Status is restricted to `Open`, `In Progress`, or `Resolved`, while priority is `Low`, `Medium`, or `High`.

The `complaint_history` table stores lifecycle events separately. A history row contains the complaint ID, resulting status, actor ID, actor role, optional note, and timestamp. Submitting a complaint creates its first `Open` event. Each admin status change adds another event. Priority-only changes update the complaint but do not create a false status event. Resident and admin detail pages read history in chronological order to show the complete timeline. Once a complaint is resolved, its update form is disabled and the backend refuses further state changes, treating it as closed.

## Overdue Detection

The overdue threshold is read from the `OVERDUE_DAYS` environment variable and defaults to three days. A complaint is overdue when it is not resolved and its creation time is older than the current time minus the configured threshold. The flag is calculated when admin dashboard and complaint pages load rather than stored in MySQL. This avoids stale overdue values and removes the need for a scheduler. The admin list sorts calculated overdue complaints first and supports an overdue-only filter. The dashboard counts the same calculated values.

## Photo Handling

The resident complaint form uses `multipart/form-data` and accepts an optional image. Flask restricts uploads to JPG, PNG, and WebP, sanitizes the extension, generates a unique UUID filename, and saves the file under `uploads/`. MySQL stores only that generated filename in `photo_path`. A complaint-aware Flask route serves the photo only to the owning resident or an authenticated admin. Flask limits the full request to 5 MB. Local storage is intentionally used for hackathon simplicity; a hosted version would need persistent disk or an external image service if the hosting platform has an ephemeral filesystem.

## Notification Flow

Flask-Mail uses SMTP values from environment variables. After an admin commits a status update, the application sends the complaint owner an email containing the complaint ID, category, new status, and optional admin note. Sending happens after the database commit so an SMTP problem cannot lose the maintenance update. An email failure produces a warning while the saved status remains valid.

When an admin publishes an important notice, the application selects all resident email addresses and sends the notice after saving it. Regular notices do not send email. Notice queries sort `is_important` first and creation time second, which pins important notices above normal updates.

## Dashboard And Access

Resident queries always include the logged-in resident ID, preventing residents from viewing another resident's complaint through an altered URL. Admin routes require an admin session. The resident dashboard aggregates personal complaints by status. The admin dashboard reads all complaints and produces totals by status, category, and overdue state in Python. This direct approach is easy to explain and appropriate for the expected hackathon data volume.
