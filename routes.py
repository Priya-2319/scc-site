from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import Student, Teacher, Manager, Course, Enrollment, Announcement, Schedule, Resource, Message, Query
from app import app, db
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from werkzeug.utils import secure_filename
import os

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", '').strip()
        email = request.form.get("email", '').strip()
        phone = request.form.get("phone", '').strip()
        message = request.form.get("message", '').strip()

        if not all([name, email, message]):
            flash("All fields are required!", "danger")
            return redirect(url_for("contact"))

        new_message = Message(name=name, email=email, phone=phone, message=message)
        db.session.add(new_message)
        db.session.commit()

        flash("Message sent successfully! We will get back to you soon.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/notification')
def notification():
    announcements = Announcement.query.all()
    return render_template('notifications.html', announcements=announcements)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", '').strip()
        username = request.form.get("username", '').strip()
        password = request.form.get("password", '').strip()

        if not all([role, username, password]):
            flash("All fields are required!", "danger")
            return redirect(url_for("login"))
        
        hashed_password = generate_password_hash(password)

        if role == "student":
            student = Student.query.filter_by(student_id=username).first()
            if student:
                if check_password_hash(student.password, password):
                    session["user_id"] = student.student_id
                    session["user_name"] = student.name
                    session["role"] = "student"
                    flash("Login successful!", "success")
                    return render_template("student_side/student_dashboard.html")
                else:
                    flash("Invalid password!", "danger")
                    return redirect(url_for("login"))
            else:
                flash("Invalid username!", "danger")
                return redirect(url_for("login"))

        elif role == "teacher":
            teacher = Teacher.query.filter_by(teacher_id=username).first()
            if teacher:
                if check_password_hash(teacher.password, password):
                    session["user_id"] = teacher.teacher_id
                    session["user_name"] = teacher.name
                    session["role"] = "teacher"
                    flash("Login successful!", "success")
                    return render_template("teacher_side/teacher_dashboard.html")
                else:
                    flash("Invalid password!", "danger")
                    return redirect(url_for("login"))
            else:
                flash("Invalid username!", "danger")
                return redirect(url_for("login"))
            
        elif role == "admin":
            manager = Manager.query.filter_by(email=username).first()
            if manager:
                if check_password_hash(manager.password, password):
                    session["user_id"] = manager.manager_id
                    session["user_name"] = manager.name
                    session["role"] = "admin"
                    flash("Login successful!", "success")
                    return render_template("admin_side/admin_dashboard.html")
                else:
                    flash("Invalid password!", "danger")
                    return redirect(url_for("login"))
            else:
                flash("Invalid username!", "danger")
                return redirect(url_for("login"))
        
        else:
            flash("Invalid role!", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

# ✅ General Authentication Decorator (Requires Login)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:  # Ensure 'user_id' exists in session
            flash("You must be logged in to access this page.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ✅ Student Authentication Decorator
def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "student":  # Check role from session
            flash("Access restricted to students only!", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function

# ✅ Teacher Authentication Decorator
def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "teacher":  # Check role from session
            flash("Access restricted to teachers only!", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function

# ✅ Admin Authentication Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":  # Check role from session
            flash("Access restricted to admins only!", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function

#logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('Logout Successfully', 'info')
    return redirect(url_for('login'))

@app.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin_side/admin_dashboard.html")

@app.route("/add_student", methods=["GET", "POST"])
@login_required
@admin_required
def add_student():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        if not all([student_id, name, email, password, phone]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('add_student'))

        student = Student.query.filter_by(student_id=student_id).first()
        if student:
            flash('Student already exists!', 'danger')
            return redirect(url_for('add_student'))
        
        hashed_password = generate_password_hash(password)

        new_student = Student(student_id=student_id, name=name, email=email, password=hashed_password, phone=phone)
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template("admin_side/crud_temp/add_student.html")

@app.route("/add_teacher", methods=["GET", "POST"])
@login_required
@admin_required
def add_teacher():
    if request.method == 'POST':
        teacher_id = request.form['teacher_id']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        subject = request.form['subject']
        phone = request.form['phone']

        if not all([teacher_id, name, email, password, subject, phone]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('add_teacher'))
        
        teacher = Teacher.query.filter_by(teacher_id=teacher_id).first()
        if teacher:
            flash('Teacher already exists!', 'danger')
            return redirect(url_for('add_teacher'))
        
        hashed_password = generate_password_hash(password)

        new_teacher = Teacher(teacher_id=teacher_id, name=name, email=email, password=hashed_password, subject=subject, phone=phone)
        db.session.add(new_teacher)
        db.session.commit()
        flash('Teacher added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template("admin_side/crud_temp/add_teacher.html")

@app.route("/add_manager", methods=["GET", "POST"])
@login_required
@admin_required
def add_manager():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        if not all([name, email, password, phone]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('add_manager'))
        
        manager = Manager.query.filter_by(email=email).first()
        if manager:
            flash('Manager already exists!', 'danger')
            return redirect(url_for('add_manager'))
        
        hashed_password = generate_password_hash(password)

        new_admin = Manager(name=name, email=email, password=hashed_password, phone=phone)
        db.session.add(new_admin)
        db.session.commit()
        flash('Admin added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template("admin_side/crud_temp/add_manager.html")

@app.route('/admin/courses')
@login_required
@admin_required
def manage_courses():
    courses = Course.query.order_by(Course.course_name).all()
    return render_template('admin_side/courses/manage.html', courses=courses)

@app.route('/admin/courses/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_course():
    if request.method == 'POST':
        course_name = request.form.get('course_name')
        description = request.form.get('description')
        monthly_fee = request.form.get('monthly_fee')
        full_fee = request.form.get('full_fee')
        
        if not all([course_name, monthly_fee, full_fee]):
            flash('Please fill all required fields', 'danger')
            return redirect(request.url)
        
        try:
            new_course = Course(
                course_name=course_name,
                description=description,
                monthly_fee=monthly_fee,
                full_fee=full_fee
            )
            db.session.add(new_course)
            db.session.commit()
            flash('Course added successfully!', 'success')
            return redirect(url_for('manage_courses'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding course: ' + str(e), 'danger')
    
    return render_template('admin_side/courses/add.html')

@app.route('/admin/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        course.course_name = request.form.get('course_name')
        course.description = request.form.get('description')
        course.monthly_fee = request.form.get('monthly_fee')
        course.full_fee = request.form.get('full_fee')
        
        try:
            db.session.commit()
            flash('Course updated successfully!', 'success')
            return redirect(url_for('manage_courses'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating course: ' + str(e), 'danger')
    
    return render_template('admin_side/courses/edit.html', course=course)

@app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    try:
        db.session.delete(course)
        db.session.commit()
        flash('Course deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting course: ' + str(e), 'danger')
    
    return redirect(url_for('manage_courses'))

@app.route('/admin/enrollments')
@login_required
@admin_required
def manage_enrollments():
    enrollments = Enrollment.query.join(Student).join(Course)\
        .order_by(Enrollment.enrollment_date.desc())\
        .all()
    students = Student.query.order_by(Student.name).all()
    courses = Course.query.order_by(Course.course_name).all()
    
    return render_template('admin_side/enrollments/manage.html', 
                         enrollments=enrollments,
                         students=students,
                         courses=courses)

@app.route('/admin/enrollments/add', methods=['POST'])
@login_required
@admin_required
def add_enrollment():
    student_id = request.form.get('student_id')
    course_id = request.form.get('course_id')
    
    if not all([student_id, course_id]):
        flash('Please select both student and course', 'danger')
        return redirect(url_for('manage_enrollments'))
    
    # Check if enrollment already exists
    existing = Enrollment.query.filter_by(
        student_id=student_id,
        course_id=course_id
    ).first()
    
    if existing:
        flash('This student is already enrolled in this course', 'warning')
        return redirect(url_for('manage_enrollments'))
    
    try:
        new_enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            status='active'
        )
        db.session.add(new_enrollment)
        db.session.commit()
        flash('Enrollment added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error adding enrollment: ' + str(e), 'danger')
    
    return redirect(url_for('manage_enrollments'))

@app.route('/admin/enrollments/<int:enrollment_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_enrollment(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    status = request.form.get('status')
    
    if status not in ['active', 'inactive', 'completed']:
        flash('Invalid status', 'danger')
        return redirect(url_for('manage_enrollments'))
    
    try:
        enrollment.status = status
        db.session.commit()
        flash('Enrollment updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating enrollment: ' + str(e), 'danger')
    
    return redirect(url_for('manage_enrollments'))

@app.route('/admin/enrollments/<int:enrollment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_enrollment(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    
    try:
        db.session.delete(enrollment)
        db.session.commit()
        flash('Enrollment deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting enrollment: ' + str(e), 'danger')
    
    return redirect(url_for('manage_enrollments'))

@app.route("/add_announcement", methods=["GET", "POST"])
@login_required
@admin_required
def add_announcement():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        session_user = session.get('user_name')

        new_announcement = Announcement(title=title, content=content, posted_by=session_user)
        db.session.add(new_announcement)
        db.session.commit()
        flash('Announcement posted successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template("admin_side/crud_temp/add_notification.html")

@app.route("/view_notifications")
@login_required
@admin_required
def view_notifications():
    announcements = Announcement.query.all()
    return render_template("admin_side/crud_temp/view_notifications.html", announcements=announcements)

@app.route("/edit_announcement/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_announcement(id):
    announcement = Announcement.query.get_or_404(id)

    if request.method == "POST":
        announcement.title = request.form["title"]
        announcement.content = request.form["content"]
        db.session.commit()
        flash("Announcement updated successfully!", "success")
        return redirect(url_for("view_notifications"))

    return render_template("admin_side/crud_temp/edit_announcement.html", announcement=announcement)

@app.route("/delete_announcement/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def delete_announcement(id):
    announcement = Announcement.query.get_or_404(id)

    db.session.delete(announcement)
    db.session.commit()
    
    flash("Announcement deleted successfully!", "success")
    return redirect(url_for("view_notifications"))


@app.route('/student_dashboard')
@login_required
@student_required
def student_dashboard():
    current_date = datetime.now().strftime("%d-%m-%Y")
    return render_template('student_side/student_dashboard.html', current_date=current_date)

@app.route('/profile', methods=["GET", "POST"])
@login_required
@student_required
def profile():
    student_id = session.get("user_id")
    student = Student.query.filter_by(student_id=student_id).first()
    if not student:
        flash("Student not found!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        email = request.form.get("email", '').strip()
        password = request.form.get("password", '').strip()
        phone = request.form.get("phone", '').strip()

        exist_email = Student.query.filter_by(email=email).first()
        exist_phone = Student.query.filter_by(phone=phone).first()
        hash_password = generate_password_hash(password)

        if email != student.email:
            if exist_email:
                flash("Email already exists!", "danger")
                return redirect(url_for("profile"))
        if phone != student.phone:
            if exist_phone:
                flash("Phone number already exists!", "danger")
                return redirect(url_for("profile"))
        
        student.email = email
        student.password = hash_password
        student.phone = phone
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))
    return render_template("student_side/profile.html", student=student)

@app.route('/my-courses')
@login_required
@student_required
def my_courses():
    student_id = session.get('user_id')
    if not student_id:
        flash('You must be logged in to view this page.', 'danger')
        return redirect(url_for('login'))
    
    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    return render_template('student_side/my_courses.html', enrollments=enrollments, student_id=student_id)

@app.route('/announcements')
@login_required
@student_required
def announcements():
    announcements = Announcement.query.all()
    return render_template('student_side/announcements.html', announcements=announcements)

@app.route('/assignments')
@login_required
@student_required
def assignments():
    return "Assignments Page Coming Soon"

@app.route('/performance')
@login_required
@student_required
def performance():
    return "Performance Page Coming Soon"

@app.route('/resources')
@login_required
@student_required
def resources():
    return "Resources Page Coming Soon"

@app.route('/admin/schedules')
@login_required
@admin_required
def admin_schedules():
    page = request.args.get('page', 1, type=int)
    pagination = Schedule.query.order_by(Schedule.class_date.asc()).paginate(page=page, per_page=10)
    return render_template('admin_side/crud_temp/schedules.html', schedules=pagination.items, pagination=pagination)

@app.route('/admin/schedules/add', methods=['POST'])
@login_required
@admin_required
def add_schedule():
    class_name = request.form.get('class_name')
    class_date = request.form.get('class_date')
    class_time = request.form.get('class_time')
    teacher = request.form.get('teacher')
    description = request.form.get('description')
    
    new_schedule = Schedule(
        class_name=class_name,
        class_date=class_date,
        class_time=class_time,
        teacher=teacher,
        description=description
    )
    
    db.session.add(new_schedule)
    db.session.commit()
    
    flash('Schedule added successfully!', 'success')
    return redirect(url_for('admin_schedules'))

@app.route('/admin/schedules/<int:schedule_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    schedule.class_name = request.form.get('class_name')
    schedule.class_date = request.form.get('class_date')
    schedule.class_time = request.form.get('class_time')
    schedule.teacher = request.form.get('teacher')
    schedule.description = request.form.get('description')
    
    db.session.commit()
    
    flash('Schedule updated successfully!', 'success')
    return redirect(url_for('admin_schedules'))

@app.route('/admin/schedules/<int:schedule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    db.session.delete(schedule)
    db.session.commit()
    
    flash('Schedule deleted successfully!', 'success')
    return redirect(url_for('admin_schedules'))

UPLOAD_FOLDER = 'static/uploads/resources'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/resources')
@login_required
@admin_required
def manage_resources():
    resources = Resource.query.order_by(Resource.date_uploaded.desc()).all()
    return render_template('admin_side/resources/resources.html', resources=resources)

@app.template_filter()
def safe_truncate(s, length=50, default=''):
    if not s:
        return default
    return s[:length] + '...' if len(s) > length else s

@app.route('/admin/resources/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_resource():
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        course_id = request.form.get('course_id', '').strip()
        file = request.files.get('file')

        # Validate required fields
        if not title:
            flash('Title is required', 'danger')
            return redirect(request.url)
            
        if not file or file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)

        # Process file upload
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_type = filename.rsplit('.', 1)[1].lower()
            
            # Create upload directory if not exists
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Generate unique filename to prevent collisions
            unique_filename = f"{datetime.now().timestamp()}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            
            try:
                file.save(filepath)
            except Exception as e:
                flash('Failed to save file', 'danger')
                app.logger.error(f"File save error: {str(e)}")
                return redirect(request.url)

            # Convert course_id to integer or None if empty
            try:
                course_id = int(course_id) if course_id else None
            except ValueError:
                course_id = None

            # Get current manager's ID from session
            manager_id = session.get('user_id')
            if not manager_id:
                flash('Authentication error', 'danger')
                return redirect(url_for('login'))

            # Create resource record
            new_resource = Resource(
                title=title,
                description=description if description else None,
                file_path=filepath.replace('\\', '/'),  # Standardize path
                file_type=file_type,
                course_id=course_id,  # Can be None
                date_uploaded=datetime.now(),
                uploaded_by=manager_id  # Use manager_id instead of name
            )
            
            try:
                db.session.add(new_resource)
                db.session.commit()
                flash('Resource added successfully!', 'success')
                return redirect(url_for('manage_resources'))
            except Exception as e:
                db.session.rollback()
                # Clean up the saved file if DB operation failed
                if os.path.exists(filepath):
                    os.remove(filepath)
                flash('Failed to save resource to database', 'danger')
                app.logger.error(f"Database error: {str(e)}")
                return redirect(request.url)
            
        else:
            flash('Invalid file type. Allowed types: pdf, txt, doc, docx', 'danger')
    
    # For GET requests or if form submission fails
    courses = Course.query.all()
    return render_template('admin_side/resources/add_resource.html', courses=courses)

@app.route('/admin/resources/<int:resource_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    
    # Delete file from filesystem
    if os.path.exists(resource.file_path):
        os.remove(resource.file_path)
    
    db.session.delete(resource)
    db.session.commit()
    
    flash('Resource deleted successfully', 'success')
    return redirect(url_for('manage_resources'))

@app.route('/student/schedule')
@login_required
@student_required
def student_schedule():
    # Get all schedules ordered by date and time
    schedules = Schedule.query.order_by(
        Schedule.class_date.asc(),
        Schedule.class_time.asc()
    ).all()
    
    # Group schedules by date
    schedules_by_date = {}
    for schedule in schedules:
        if schedule.class_date not in schedules_by_date:
            schedules_by_date[schedule.class_date] = []
        schedules_by_date[schedule.class_date].append(schedule)
    
    return render_template('student_side/schedule.html', schedules_by_date=schedules_by_date)

@app.route('/student/resources')
@login_required
@student_required
def student_resources():
    # Get current student
    student_id = session.get('user_id')
    
    # Get enrolled courses
    enrolled_courses = Enrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).with_entities(Enrollment.course_id).all()
    
    enrolled_course_ids = [course.course_id for course in enrolled_courses]
    
    # Get filter parameters
    resource_type = request.args.get('type', '')
    
    # Base query - only resources from enrolled courses or general resources
    query = Resource.query.filter(
        (Resource.course_id.in_(enrolled_course_ids)) | 
        (Resource.course_id.is_(None))
    ).order_by(Resource.date_uploaded.desc())
    
    # Apply type filter
    if resource_type:
        query = query.filter(Resource.file_type == resource_type)
    
    resources = query.all()
    enrolled_courses = Course.query.filter(Course.course_id.in_(enrolled_course_ids)).all()
    
    return render_template('student_side/resources.html',
                         resources=resources,
                         enrolled_courses=enrolled_courses,
                         selected_type=resource_type)

@app.route('/view_students')
@login_required
@admin_required
def view_students():
    students = Student.query.order_by(Student.name).all()
    return render_template('admin_side/view_students.html', students=students)

@app.route('/edit_student/<string:student_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student(student_id):
    student = Student.query.filter_by(student_id=student_id).first_or_404()
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        new_password = request.form.get('password')
        
        # Validate and update
        errors = False
        
        # Check if email is being changed to an existing one
        if email != student.email:
            if Student.query.filter_by(email=email).first():
                flash('Email already exists', 'danger')
                errors = True
        
        # Check if phone is being changed to an existing one
        if phone != student.phone:
            if Student.query.filter_by(phone=phone).first():
                flash('Phone number already exists', 'danger')
                errors = True
        
        if not errors:
            student.name = name
            student.email = email
            student.phone = phone
            
            # Only update password if a new one was provided
            if new_password:
                student.password = generate_password_hash(new_password)
            
            db.session.commit()
            flash('Student updated successfully', 'success')
            return redirect(url_for('view_students'))
    
    return render_template('admin_side/edit_student.html', student=student)
