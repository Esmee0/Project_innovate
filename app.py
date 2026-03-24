import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-change-me"

# Always store the SQLite DB next to this file (stable path)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "app.db")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    total_hours = db.Column(db.Float, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if username == "" or password == "":
            flash("Fill in username and password.")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return render_template("register.html")

        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Wrong username or password.")
            return render_template("login.html")

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    assignments = (
        Assignment.query
        .filter_by(user_id=current_user.id)
        .order_by(Assignment.due_date.asc())
        .all()
    )
    return render_template(
        "dashboard.html",
        username=current_user.username,
        assignments=assignments,
    )


@app.route("/assignments/new", methods=["GET", "POST"])
@login_required
def new_assignment():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        start_date_raw = request.form.get("start_date") or ""
        due_date_raw = request.form.get("due_date") or ""
        total_hours_raw = (request.form.get("total_hours") or "").strip().replace(",", ".")

        if not title:
            flash("Title is required.")
            return render_template("new_assignment.html")

        try:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            total_hours = float(total_hours_raw)
        except ValueError:
            flash("Invalid input. Check dates and hours.")
            return render_template("new_assignment.html")

        if due_date < start_date:
            flash("Due date must be after start date.")
            return render_template("new_assignment.html")

        if total_hours <= 0:
            flash("Total hours must be greater than 0.")
            return render_template("new_assignment.html")

        a = Assignment(
            user_id=current_user.id,
            title=title,
            start_date=start_date,
            due_date=due_date,
            total_hours=total_hours,
        )
        db.session.add(a)
        db.session.commit()

        flash("Assignment saved.")
        return redirect(url_for("dashboard"))

    return render_template("new_assignment.html")

@app.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
@login_required
def delete_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)

    # Security: only delete your own assignments
    if a.user_id != current_user.id:
        flash("You are not allowed to delete this assignment.")
        return redirect(url_for("dashboard"))

    db.session.delete(a)
    db.session.commit()
    flash("Assignment deleted.")
    return redirect(url_for("dashboard"))


@app.route("/assignments/<int:assignment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)

    # Security: only edit your own assignments
    if a.user_id != current_user.id:
        flash("You are not allowed to edit this assignment.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        start_date_raw = request.form.get("start_date") or ""
        due_date_raw = request.form.get("due_date") or ""
        total_hours_raw = (request.form.get("total_hours") or "").strip().replace(",", ".")

        if not title:
            flash("Title is required.")
            return render_template("edit_assignment.html", assignment=a)

        try:
            a.start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
            a.due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            a.total_hours = float(total_hours_raw)
        except ValueError:
            flash("Invalid input. Check dates and hours.")
            return render_template("edit_assignment.html", assignment=a)

        a.title = title

        if a.due_date < a.start_date:
            flash("Due date must be after start date.")
            return render_template("edit_assignment.html", assignment=a)

        if a.total_hours <= 0:
            flash("Total hours must be greater than 0.")
            return render_template("edit_assignment.html", assignment=a)

        db.session.commit()
        flash("Assignment updated.")
        return redirect(url_for("dashboard"))

    return render_template("edit_assignment.html", assignment=a)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)