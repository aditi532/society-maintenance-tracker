import unittest
from datetime import datetime, timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app, is_overdue, refresh_overdue


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test-secret", OVERDUE_DAYS=3)
        self.client = app.test_client()

    def test_public_pages_load_without_database(self):
        for path in ("/login", "/register", "/admin/login"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_root_redirects_to_resident_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))

    def test_protected_resident_pages_redirect_to_login(self):
        for path in ("/dashboard", "/complaints/new", "/complaints", "/profile", "/notices"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.location.endswith("/login"))

    def test_protected_admin_pages_redirect_to_admin_login(self):
        for path in ("/admin/dashboard", "/admin/complaints", "/admin/residents", "/admin/notices"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.location.endswith("/admin/login"))

    def test_old_open_complaint_is_overdue(self):
        complaint = {"status": "Open", "created_at": datetime.now() - timedelta(days=4)}
        self.assertTrue(is_overdue(complaint))

    def test_recent_and_resolved_complaints_are_not_overdue(self):
        recent = {"status": "Open", "created_at": datetime.now() - timedelta(days=1)}
        resolved = {"status": "Resolved", "created_at": datetime.now() - timedelta(days=10)}
        self.assertFalse(is_overdue(recent))
        self.assertFalse(is_overdue(resolved))

    def test_refresh_overdue_adds_calculated_flag(self):
        complaints = [
            {"status": "In Progress", "created_at": datetime.now() - timedelta(days=5)},
            {"status": "Resolved", "created_at": datetime.now() - timedelta(days=5)},
        ]
        result = refresh_overdue(complaints)
        self.assertTrue(result[0]["is_overdue"])
        self.assertFalse(result[1]["is_overdue"])

    def test_all_templates_compile(self):
        for template_name in app.jinja_env.list_templates():
            with self.subTest(template=template_name):
                app.jinja_env.get_template(template_name)

    def test_invalid_complaint_category_is_rejected_before_database(self):
        with self.client.session_transaction() as session:
            session["resident_id"] = 7
            session["resident_name"] = "Aditi"
        with patch("app.get_db") as get_db:
            response = self.client.post("/complaints/new", data={"category": "Fake", "description": "Broken tap"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Choose a valid category", response.data)
        get_db.assert_not_called()

    def test_invalid_photo_type_is_rejected(self):
        with self.client.session_transaction() as session:
            session["resident_id"] = 7
            session["resident_name"] = "Aditi"
        response = self.client.post(
            "/complaints/new",
            data={"category": "Plumbing", "description": "Broken tap", "photo": (BytesIO(b"text"), "notes.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"JPG, PNG, or WebP", response.data)

    def test_complaint_photo_gets_unique_name_and_history_record(self):
        class Cursor:
            lastrowid = 19

            def __init__(self):
                self.calls = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, query, values):
                self.calls.append((query, values))

        class Database:
            def __init__(self):
                self.cursor_object = Cursor()
                self.committed = False

            def cursor(self):
                return self.cursor_object

            def commit(self):
                self.committed = True

            def close(self):
                pass

        database = Database()
        with self.client.session_transaction() as session:
            session["resident_id"] = 7
            session["resident_name"] = "Aditi"
        with TemporaryDirectory() as uploads:
            app.config["UPLOAD_FOLDER"] = uploads
            with patch("app.get_db", return_value=database):
                response = self.client.post(
                    "/complaints/new",
                    data={"category": "Lift", "description": "Lift is stuck", "photo": (BytesIO(b"image"), "photo.jpg")},
                    content_type="multipart/form-data",
                )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(database.committed)
        self.assertEqual(len(database.cursor_object.calls), 2)
        saved_name = database.cursor_object.calls[0][1][3]
        self.assertTrue(saved_name.endswith(".jpg"))
        self.assertNotEqual(saved_name, "photo.jpg")
        self.assertIn("complaint_history", database.cursor_object.calls[1][0])

    def test_invalid_admin_update_is_rejected_before_database(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = 1
            session["admin_name"] = "admin"
        with patch("app.get_db") as get_db:
            response = self.client.post("/admin/complaints/1/update", data={"status": "Deleted", "priority": "Urgent"})
        self.assertEqual(response.status_code, 302)
        get_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
