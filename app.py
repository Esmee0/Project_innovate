import os
from collections import defaultdict
from datetime import datetime, timedelta
from datetime import date

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

@app.template_filter("dmy")
def format_dmy(value):
    """Format a date/datetime as dd/mm/yy for templates."""
    if value is None:
        return ""
    # If it's a datetime, take the date part
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d/%m/%y")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r}>"


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    total_hours = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Assignment id={self.id} title={self.title!r} user_id={self.user_id}>"
    
class WorkLog(db.Model):
    __tablename__ = "work_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    assignment_id = db.Column(db.Integer, db.ForeignKey("assignment.id"), nullable=False)
    work_date = db.Column(db.Date, nullable=False)

    # For this project we log "done hours" for that day.
    hours_done = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "assignment_id", "work_date", name="uq_worklog_user_assignment_date"),
    )

    def __repr__(self):
        return f"<WorkLog assignment_id={self.assignment_id} date={self.work_date} hours_done={self.hours_done}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def build_schedule(assignments):
    """
    Returns dict:
      {day: [{"assignment": a, "planned_hours": x, "done": True/False, "done_hours": y}, ...]}

    Behavior:
    - Planned hours are evenly distributed across days.
    - If you mark a day as done, that day's planned hours become 0 remaining and won't be planned again.
    - Remaining hours are re-distributed across remaining (not-done) days between today..due_date.
    """
    today = date.today()
    schedule = defaultdict(list)

    for a in assignments:
        # Safety checks
        if not a.start_date or not a.due_date or a.total_hours is None:
            continue
        if a.due_date < a.start_date:
            continue
        if a.total_hours <= 0:
            continue

        # Load all worklogs for this assignment (current user only)
        logs = (
            WorkLog.query
            .filter_by(user_id=current_user.id, assignment_id=a.id)
            .all()
        )
        done_by_date = {wl.work_date: wl.hours_done for wl in logs if wl.hours_done and wl.hours_done > 0}

        total_done = sum(done_by_date.values())
        remaining_total = max(0.0, a.total_hours - total_done)

        # Days we consider for planning:
        # - from max(start_date, today) to due_date
        plan_start = max(a.start_date, today)
        plan_end = a.due_date

        # If assignment already ended, still show historical days if they exist in schedule_map
        # but we won't plan remaining hours past due_date.
        remaining_days = []
        d = plan_start
        while d <= plan_end:
            # If user already logged work on that day, treat it as done (no new planned hours)
            if d not in done_by_date:
                remaining_days.append(d)
            d += timedelta(days=1)

        hours_per_remaining_day = (remaining_total / len(remaining_days)) if remaining_days else 0.0

        # Build schedule entries for all days between start and due (inclusive), but
        # show only days from start..due where we might want to view/checkbox.
        d = a.start_date
        while d <= a.due_date:
            done_hours = done_by_date.get(d, 0.0)
            is_done = done_hours > 0

            planned = 0.0
            if d in remaining_days:
                planned = hours_per_remaining_day

            schedule[d].append(
                {
                    "assignment": a,
                    "planned_hours": planned,
                    "done": is_done,
                    "done_hours": done_hours,
                }
            )
            d += timedelta(days=1)

    return dict(sorted(schedule.items(), key=lambda x: x[0]))


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/schedule/toggle", methods=["POST"])
@login_required
def schedule_toggle():
    assignment_id = int(request.form.get("assignment_id"))
    work_date_raw = request.form.get("work_date") or ""  # expects YYYY-MM-DD from hidden input
    action = request.form.get("action") or "check"

    a = Assignment.query.get_or_404(assignment_id)
    if a.user_id != current_user.id:
        flash("Not allowed.")
        return redirect(url_for("schedule"))

    try:
        work_date_val = datetime.strptime(work_date_raw, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date.")
        return redirect(url_for("schedule"))

    # Compute what the "planned" hours should be right now for that day,
    # so checking it will log that amount.
    schedule_map = build_schedule([a])
    day_items = schedule_map.get(work_date_val, [])
    planned_hours = 0.0
    for item in day_items:
        if item["assignment"].id == a.id:
            planned_hours = float(item["planned_hours"])
            break

    wl = (
        WorkLog.query
        .filter_by(user_id=current_user.id, assignment_id=a.id, work_date=work_date_val)
        .first()
    )

    if action == "uncheck":
        if wl:
            db.session.delete(wl)
            db.session.commit()
        return redirect(url_for("schedule"))

    # action == "check"
    if planned_hours <= 0:
        # If there's nothing planned (e.g. already done or outside planning window),
        # we still allow a tiny log, but better to block to avoid weirdness.
        flash("Nothing to check off for that day.")
        return redirect(url_for("schedule"))

    if not wl:
        wl = WorkLog(user_id=current_user.id, assignment_id=a.id, work_date=work_date_val, hours_done=planned_hours)
        db.session.add(wl)
    else:
        wl.hours_done = planned_hours  # overwrite with current planned
    db.session.commit()

    return redirect(url_for("schedule"))


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


@app.route("/schedule")
@login_required
def schedule():
    assignments = (
        Assignment.query
        .filter_by(user_id=current_user.id)
        .order_by(Assignment.due_date.asc())
        .all()
    )

    schedule_map = build_schedule(assignments)
    return render_template("schedule.html", schedule_map=schedule_map)


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