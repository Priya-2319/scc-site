from flask_sqlalchemy import SQLAlchemy
from app import app, db
from datetime import datetime
import os


# User table model
class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(10), nullable=False, unique=True)
    date_registered = db.Column(db.DateTime, server_default=db.func.current_timestamp())

# Teacher table model
class Teacher(db.Model):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(50))
    phone = db.Column(db.String(10), nullable=False, unique=True)
    date_joined = db.Column(db.DateTime, server_default=db.func.current_timestamp())

# Manager table model
class Manager(db.Model):
    __tablename__ = 'managers'
    manager_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(10), nullable=False, unique=True)

# Payment table
class Payment(db.Model):
    __tablename__ = 'payments'
    payment_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(10), db.ForeignKey('students.student_id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    payment_type = db.Column(db.String(20), nullable=False)  # 'monthly', 'full_course', 'selected_month'
    for_month = db.Column(db.String(10), nullable=True)  # Null for full course
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=False, unique=True)
    order_id = db.Column(db.String(100), nullable=False, unique=True)
    razorpay_reference_id = db.Column(db.String(50), unique=True)  # Unique reference ID for Razorpay
    payment_status = db.Column(db.String(10), default='pending', nullable=False)

# Course table model
class Course(db.Model):
    __tablename__ = 'courses'
    course_id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_fee = db.Column(db.Numeric(10, 2), nullable=False)  # Monthly fee
    full_fee = db.Column(db.Numeric(10, 2), nullable=False)  # Full course fee

# Enrollment table model
class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    enrollment_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(10), db.ForeignKey('students.student_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    status = db.Column(db.String(10), default='active', nullable=False)
    
    # Relationships
    student = db.relationship('Student', backref='enrollments')
    course = db.relationship('Course', backref='enrollments')
    
# Announcements table model
class Announcement(db.Model):
    __tablename__ = 'announcements'
    announcement_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    date_posted = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    posted_by = db.Column(db.String(50), nullable=False)

# Schedule Class model
class Schedule(db.Model):
    __tablename__ = 'schedules'
    schedule_id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(50), nullable=False)
    class_time = db.Column(db.String(50), nullable=False)
    class_date = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    teacher = db.Column(db.String(50), nullable=True)

class Resource(db.Model):
    __tablename__ = 'resources'
    resource_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(255))  # For storing file paths
    file_type = db.Column(db.String(20))   # 'pdf', 'text', etc.
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'))  # Optional: link to courses
    date_uploaded = db.Column(db.DateTime, default=datetime.now)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('managers.manager_id'))  # Changed to manager_id
    
    # Relationship - updated to reference Manager instead of User
    course = db.relationship('Course', backref='resources')
    uploader = db.relationship('Manager', backref='uploaded_resources')  # Changed to Manager

class Query(db.Model):
    __tablename__ = 'query'
    query_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(10), db.ForeignKey('students.student_id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_submitted = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    status = db.Column(db.String(10), default='pending', nullable=False)

    # Response fields after status is updated
    response = db.Column(db.Text, nullable=True)
    response_date = db.Column(db.DateTime, nullable=True)

    # Relationships
    student = db.relationship('Student', backref='queries')

class Message(db.Model):
    __tablename__ = 'message'
    message_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(10), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, server_default=db.func.current_timestamp())


with app.app_context():
    db.create_all()
