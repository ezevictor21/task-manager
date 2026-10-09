import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for

from config import Config
from models import Task, User, bcrypt, db


app = Flask(__name__)
app.config.from_object(Config)


db.init_app(app)
bcrypt.init_app(app)


# Create database tables
with app.app_context():
    db.create_all()


# Helper: Login required decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))


    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')


        if not all([username, email, password]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))


        if User.query.filter_by(username=username).first():
            flash('Username already taken!', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))


        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))


    return render_template('register.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([username, email, new_password, confirm_password]):
            flash('Please fill in all fields.', 'danger')
            return redirect(url_for('forgot_password'))

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('forgot_password'))

        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('forgot_password'))

        user = User.query.filter_by(username=username).first()
        if not user or user.email.lower() != email.lower():
            flash('Username and email do not match any account.', 'danger')
            return redirect(url_for('forgot_password'))

        user.set_password(new_password)
        db.session.commit()
        flash('Password reset successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('forgot_password.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))


    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()


        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password!', 'danger')


    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# --- Task Routes ---
@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.due_date.asc(), Task.priority.desc()).all()


    stats = {
        'total': len(tasks),
        'pending': sum(1 for t in tasks if t.status == 'Pending'),
        'in_progress': sum(1 for t in tasks if t.status == 'In Progress'),
        'completed': sum(1 for t in tasks if t.status == 'Completed'),
        'done': sum(1 for t in tasks if t.status == 'Completed')
    }
    return render_template('index.html', tasks=tasks, stats=stats)


@app.route('/tasks/new', methods=['GET', 'POST'])
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

        task = Task(
            title=request.form.get('title'),
            description=request.form.get('description', ''),
            due_date=due_date,
            priority=request.form.get('priority', 'Medium'),
            status=request.form.get('status', 'Pending'),
            user_id=session['user_id']
        )
        db.session.add(task)
        db.session.commit()
        flash('Task added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('task_form.html', task=None)


@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        task.title = request.form.get('title')
        task.description = request.form.get('description', '')
        due_date_str = request.form.get('due_date')
        task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        task.priority = request.form.get('priority')
        task.status = request.form.get('status')
        db.session.commit()
        flash('Task updated!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('task_form.html', task=task)


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@app.route('/del/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted!', 'info')
    return redirect(url_for('dashboard'))


@app.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@app.route('/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_complete(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    task.status = 'Completed' if task.status != 'Completed' else 'Pending'
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/tasks/filter')
@login_required
def filter_tasks():
    status = request.args.get('status', 'all')
    priority = request.args.get('priority', 'all')
    search = request.args.get('search', '').strip()


    query = Task.query.filter_by(user_id=session['user_id'])
    if status != 'all':
        query = query.filter_by(status=status)
    if priority != 'all':
        query = query.filter_by(priority=priority)
    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))


    tasks = query.order_by(Task.due_date.asc()).all()
    stats = {'total': len(tasks)}
    return render_template('tasks_list.html', tasks=tasks, stats=stats,
                           selected_status=status, selected_priority=priority, search=search)


@app.route('/admin/users')
@login_required
def admin_users():
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/users')
@login_required
def users():
    users_list = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=users_list)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
