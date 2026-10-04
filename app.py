import os
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
# Needed by flash() messages. In real projects, load this from an environment variable.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Build the database path relative to this file, so it works from any folder.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "employees.db")


def get_db():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us use row["name"] instead of row[1]
    return conn


def init_db():
    """Create the database folder and the employees table if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            phone      TEXT NOT NULL,
            department TEXT NOT NULL,
            job_role   TEXT NOT NULL,
            salary     REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def read_form():
    """Read and clean the employee fields from the submitted form."""
    return (
        request.form["name"].strip(),
        request.form["email"].strip(),
        request.form["phone"].strip(),
        request.form["department"].strip(),
        request.form["job_role"].strip(),
        request.form["salary"].strip(),
    )


# ---------- READ (view all + search) ----------
@app.route("/")
def index():
    search = request.args.get("search", "").strip()
    conn = get_db()
    if search:
        like = f"%{search}%"
        # The ? placeholders protect us from SQL injection.
        employees = conn.execute(
            """
            SELECT * FROM employees
            WHERE name LIKE ? OR email LIKE ? OR department LIKE ?
               OR job_role LIKE ? OR CAST(id AS TEXT) = ?
            ORDER BY id
            """,
            (like, like, like, like, search),
        ).fetchall()
    else:
        employees = conn.execute("SELECT * FROM employees ORDER BY id").fetchall()
    conn.close()
    return render_template("index.html", employees=employees, search=search)


# ---------- CREATE ----------
@app.route("/add", methods=["GET", "POST"])
def add_employee():
    if request.method == "POST":
        name, email, phone, department, job_role, salary = read_form()
        conn = get_db()
        try:
            salary = float(salary)
            conn.execute(
                "INSERT INTO employees (name, email, phone, department, job_role, salary) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, email, phone, department, job_role, salary),
            )
            conn.commit()
            flash("Employee added successfully!", "success")
            return redirect(url_for("index"))
        except ValueError:
            flash("Salary must be a number.", "danger")
        except sqlite3.IntegrityError:
            flash("An employee with that email already exists.", "danger")
        finally:
            # finally ALWAYS runs, so the connection is closed even when an error happens.
            conn.close()
    return render_template("add_employee.html")


# ---------- UPDATE ----------
@app.route("/edit/<int:emp_id>", methods=["GET", "POST"])
def edit_employee(emp_id):
    conn = get_db()
    employee = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
    if employee is None:
        conn.close()
        flash("Employee not found.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        name, email, phone, department, job_role, salary = read_form()
        try:
            salary = float(salary)
            conn.execute(
                "UPDATE employees SET name=?, email=?, phone=?, department=?, "
                "job_role=?, salary=? WHERE id=?",
                (name, email, phone, department, job_role, salary, emp_id),
            )
            conn.commit()
            conn.close()
            flash("Employee updated successfully!", "success")
            return redirect(url_for("index"))
        except ValueError:
            flash("Salary must be a number.", "danger")
        except sqlite3.IntegrityError:
            flash("Another employee already uses that email.", "danger")

    conn.close()
    return render_template("edit_employee.html", employee=employee)


# ---------- DELETE ----------
@app.route("/delete/<int:emp_id>", methods=["POST"])
def delete_employee(emp_id):
    conn = get_db()
    conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    flash("Employee deleted.", "warning")
    return redirect(url_for("index"))


# Health check: handy later for Docker, Jenkins and Nginx tests.
@app.route("/health")
def health():
    return {"status": "ok"}, 200


# Create the table when the app starts.
init_db()

if __name__ == "__main__":
    # host 0.0.0.0 is needed later so Docker can reach the app.
    app.run(host="0.0.0.0", port=8000, debug=True)
