from datetime import datetime
from flask import request, jsonify, redirect, url_for, render_template, session, abort, send_file, make_response, flash, current_app
from app import app, db, razorpay_client
from models import Payment, Course, Student
from routes import login_required, student_required, admin_required
from dateutil.relativedelta import relativedelta
from io import BytesIO, StringIO
import csv
from pagination import Pagination
from werkzeug.security import check_password_hash
from functools import wraps
from xhtml2pdf import pisa
import base64
from sqlalchemy.orm import joinedload
import os
import pytz
from flask_mail import Mail, Message

mail = Mail(app)


# for webhook
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)

@app.route('/payment', methods=['GET'])
@login_required
@student_required
def payment_page():
    try:
        user_id = session['user_id']
        current_user = db.session.query(Student).filter_by(student_id=user_id).first()
        courses = Course.query.all()
        current_month = datetime.now().strftime('%Y-%m')
        next_months = [
            (datetime.now() + relativedelta(months=i)).strftime('%Y-%m')
            for i in range(0, 6)
        ]
        return render_template('student_side/payment_options.html',
                             current_user=current_user,
                             courses=courses,
                             current_month=current_month,
                             next_months=next_months)
    except Exception as e:
        logger.error(f"Payment page error: {str(e)}")
        return redirect(url_for('student_dashboard'))

# Payment Routes
@app.route('/initiate-payment', methods=['POST'])
@login_required
@student_required
def initiate_payment():
    try:
        data = request.get_json()
        student_id = session['user_id']
        payment_type = data['payment_type']
        course_id = data['course_id']
        
        course = Course.query.get(course_id)
        if not course:
            logger.error(f"Course not found: {course_id}")
            return jsonify({'error': 'Course not found'}), 404
        
        # Calculate amount and month
        amount, for_month = calculate_payment_details(course, payment_type, data)
        amount_paise = int(amount * 100)
        
        # Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'payment_capture': '1',
            'notes': {
                'student_id': student_id,
                'course_id': course_id,
                'payment_type': payment_type,
                'for_month': for_month,
                'internal_ref': f"SCI-{datetime.now().timestamp()}"
            }
        })
        india_timezone = pytz.timezone('Asia/Kolkata')
        # Create payment record
        new_payment = Payment(
            student_id=student_id,
            amount=amount,
            payment_date=datetime.now(india_timezone),
            payment_type=payment_type,
            for_month=for_month,
            course_id=course_id,
            payment_method='razorpay',
            transaction_id=razorpay_order['id'],  # Will be updated to payment_id later
            order_id=razorpay_order['id'],
            razorpay_reference_id=f"SCI-{datetime.now().timestamp()}",
            payment_status='pending'
        )
        db.session.add(new_payment)
        db.session.commit()
        
        return jsonify({
            'order_id': razorpay_order['id'],
            'amount': amount_paise,
            'key_id': app.config['RAZORPAY_KEY_ID'],
            'course_name': course.course_name,
            'callback_url': url_for('verify_payment', _external=True)
        })
        
    except Exception as e:
        logger.error(f"Payment initiation error: {str(e)}")
        return jsonify({'error': 'Payment initialization failed'}), 500

def calculate_payment_details(course, payment_type, data):
    if payment_type == 'current_month':
        return course.monthly_fee, datetime.now().strftime('%Y-%m')
    elif payment_type == 'full_course':
        return course.full_fee, None
    elif payment_type == 'selected_month':
        return course.monthly_fee, data.get('selected_month')
    else:
        raise ValueError("Invalid payment type")
    
def send_payment_success_email(to_email, name, amount, order_id, transaction_id, for_month, course_name):
    msg = Message(
        subject="🎉 Payment Successful",
        sender="clearupsol015@gmail.com",
        recipients=[to_email]
    )
    msg.body = f"""
        Hi {name},
        Student ID: {session['user_id']}

        Your payment of ₹{amount} was successful!

        For Month: {for_month}
        Course Name: {course_name}

        Order ID: {order_id}

        Transaction ID: {transaction_id}

        Payment Status: Successful
        Pyment Method: Razorpay

        Thank you for paying with us!

        Regards,
        Science Coaching Center, Belahi
        Madhubani, Bihar
        Phone: 7004380150
        Email: clearupsol015@gmail.com
        """
    mail.send(msg)

@app.route('/verify-payment', methods=['POST'])
@login_required
@student_required
def verify_payment():
    try:
        razorpay_payment_id = request.form['razorpay_payment_id']
        razorpay_order_id = request.form['razorpay_order_id']
        razorpay_signature = request.form['razorpay_signature']
        
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        
        # Get payment details from Razorpay
        razorpay_payment = razorpay_client.payment.fetch(razorpay_payment_id)
        
        # Find and update payment record
        payment = Payment.query.filter_by(order_id=razorpay_order_id).first()
        if not payment:
            logger.error(f"Payment not found for order: {razorpay_order_id}")
            return jsonify({'status': 'error', 'message': 'Payment record not found'}), 400
        
        # Update payment details
        india_timezone = pytz.timezone('Asia/Kolkata')
        if payment.payment_status != 'completed':
            payment.transaction_id = razorpay_payment_id
            payment.payment_status = 'completed' if razorpay_payment['status'] == 'captured' else razorpay_payment['status']
            payment.payment_date = datetime.now(india_timezone)
            db.session.commit()

        # Send email
        student = payment.student  # Get the student object from the payment record
        course = payment.course  # Get the course object from the payment record
        send_payment_success_email(
            to_email=student.email,
            name=student.name,
            amount=payment.amount,
            order_id=payment.order_id,
            transaction_id=payment.transaction_id,
            for_month=payment.for_month,
            course_name=course.course_name
        )
        
        return jsonify({
            'status': 'success',
            'redirect_url': url_for('payment_success')
        })
        
    except Exception as e:
        logger.error(f"Payment verification failed: {str(e)}")
        if 'razorpay_order_id' in locals():
            payment = Payment.query.filter_by(order_id=razorpay_order_id).first()
            if payment:
                payment.payment_status = 'failed'
                db.session.commit()
        return jsonify({
            'status': 'error',
            'message': 'Payment verification failed',
            'redirect_url': url_for('payment_failed')
        }), 400

@app.route("/razorpay/webhook/", methods=["POST"])
def razorpay_webhook():
    try:
        webhook_secret = app.config['RAZORPAY_WEBHOOK_SECRET']
        received_signature = request.headers.get('X-Razorpay-Signature')
        payload = request.get_data(as_text=True)
        
        # Verify signature
        generated_signature = hmac.new(
            key=webhook_secret.encode(),
            msg=payload.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(generated_signature, received_signature):
            logger.error("Webhook signature verification failed")
            abort(400)
            
        data = request.get_json()
        handle_webhook_event(data)
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"status": "error"}), 500

def handle_webhook_event(data):
    event = data['event']
    payment_entity = data['payload']['payment']['entity']
    
    if event == 'payment.captured':
        handle_successful_payment(payment_entity)
    elif event == 'payment.failed':
        handle_failed_payment(payment_entity)

def handle_successful_payment(payment):
    payment = Payment.query.filter_by(order_id=payment['order_id']).first()
    india_timezone = pytz.timezone('Asia/Kolkata')
    if payment and payment.payment_status != 'completed':
        payment.transaction_id = payment['id']
        payment.payment_status = 'completed'
        payment.payment_date = datetime.now(india_timezone)
        db.session.commit()

def handle_failed_payment(payment):
    payment = Payment.query.filter_by(order_id=payment['order_id']).first()
    if payment and payment.payment_status != 'failed':
        payment.payment_status = 'failed'
        db.session.commit()


# Success/Failure Routes
@app.route('/payment/success')
@login_required
@student_required
def payment_success():
    """Endpoint to show payment success page"""
    return render_template('student_side/payment_success.html')


@app.route('/payment/failed')
@login_required
@student_required
def payment_failed():
    """Endpoint to show payment failure page"""
    return render_template('student_side/payment_failed.html')


@app.route("/student/payment-history")
@login_required
@student_required
def payment_history():
    page = request.args.get('page', 1, type=int)
    student_id = session.get('user_id')
    
    # Get all payments for the student, ordered by date
    all_payments = Payment.query.filter_by(student_id=student_id)\
                               .order_by(Payment.payment_date.desc())\
                               .all()
    
    pagination = Pagination(all_payments, page=page, per_page=10)
    payments_page = all_payments[pagination.start:pagination.end]
    
    return render_template(
        'student_side/payment_history.html',
        payments=payments_page,
        pagination=pagination,
        student_name=session.get('user_name')
    )


@app.route("/student/export-payments")
@login_required
@student_required
def export_payments():
    student_id = session.get('user_id')
    payments = Payment.query.filter_by(student_id=student_id)\
                          .order_by(Payment.payment_date.desc())\
                          .all()
    
    # Create CSV in memory as StringIO (instead of BytesIO)
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Date', 'Amount', 'Type', 'For Month', 
        'Course', 'Payment Method', 'Transaction ID', 'Status'
    ])
    
    # Write data
    for payment in payments:
        course = Course.query.get(payment.course_id)
        writer.writerow([
            payment.payment_date.strftime('%Y-%m-%d %H:%M'),
            f"Rs.- {payment.amount:.2f}",
            payment.payment_type.replace('_', ' ').title(),
            payment.for_month if payment.for_month else 'Full Course',
            course.course_name,
            payment.payment_method.title(),
            payment.transaction_id,
            payment.payment_status.capitalize()
        ])
    
    output.seek(0)
    
    # Create BytesIO from the StringIO content
    mem = BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'payment_history_{datetime.now().date()}.csv'
    )

@app.route('/admin/manage/payments', methods=['GET'])
@login_required
@admin_required
def manage_payments():
    page = request.args.get('page', 1, type=int)
    
    # Query payments with joined student and course data
    all_payments = Payment.query \
        .join(Student, Student.student_id == Payment.student_id) \
        .join(Course, Course.course_id == Payment.course_id) \
        .order_by(Payment.payment_date.desc()) \
        .all()
    
    pagination = Pagination(all_payments, page=page, per_page=10)
    payments_page = all_payments[pagination.start:pagination.end]
    
    return render_template(
        'admin_side/payments/manage_payments.html',
        payments=payments_page,
        pagination=pagination
    )

@app.route('/payments/<int:payment_id>')
@login_required
@admin_required
def payment_details(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    return render_template('admin_side/payments/payment_details.html', payment=payment)

@app.route('/payments/<int:payment_id>/receipt')
@login_required
@admin_required
def generate_receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)

    # Load image and encode it as base64
    with open("static/images/logo.png", "rb") as img_file:
        encoded_logo = base64.b64encode(img_file.read()).decode('utf-8')
    logo_data_uri = f"data:image/png;base64,{encoded_logo}"

    html = render_template('admin_side/payments/receipt_template.html', payment=payment, logo=logo_data_uri)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)

    if not pdf.err:
        response = make_response(result.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=receipt_{payment.transaction_id}.pdf'
        return response

    return "Error generating PDF", 500

@app.route('/student/payment_id/<int:payment_id>/receipt')
@login_required
@student_required
def payment_receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    # Load image and encode it as base64
    with open("static/images/logo.png", "rb") as img_file:
        encoded_logo = base64.b64encode(img_file.read()).decode('utf-8')
    logo_data_uri = f"data:image/png;base64,{encoded_logo}"
    html = render_template('student_side/payment_receipt.html', payment=payment, logo=logo_data_uri)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = make_response(result.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=payment_receipt_{payment.transaction_id}.pdf'
        return response
    
    return "Error generating PDF", 500

@app.route('/export/payments/pdf')
@login_required
@admin_required
def export_all_payments_pdf():
    payments = Payment.query.order_by(Payment.payment_date.desc()).all()
    now = datetime.now().strftime('%d-%m-%Y %H:%M')
    html = render_template('admin_side/payments/payments_list_template.html', payments=payments, now=now)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = make_response(result.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=all_payments.pdf'
        return response

    return "Error generating PDF", 500

@app.route('/make_payment_complete/<int:payment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def make_payment_complete(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment.payment_method = 'MANUAL'
    payment.payment_date = datetime.now()
    payment.payment_status = 'completed'
    db.session.commit()
    flash('Payment marked as complete', 'success')
    return redirect(url_for('manage_payments'))

# route for cash payment
@app.route('/admin/add_cash_payment', methods=['GET', 'POST'])
@login_required
@admin_required
def add_cash_payment():
    students = Student.query.all()
    courses = Course.query.all()

    if request.method == 'POST':
        student_id = request.form.get('student_id', ' ').strip()
        course_id = request.form.get('course_id', ' ').strip()
        amount = request.form.get('amount', ' ').strip()
        payment_type = request.form.get('payment_type', ' ').strip()
        for_month = request.form.get('for_month', None)

        new_payment = Payment(
            student_id=student_id,
            course_id=course_id,
            amount=amount,
            payment_type=payment_type,
            for_month=for_month if payment_type == 'selected_month' else None,
            payment_method='CASH',
            transaction_id=f"CASH-{datetime.now().timestamp()}",
            order_id=f"CASH-ORDER-{datetime.now().timestamp()}",
            razorpay_reference_id=f"rf-cash-{datetime.now().timestamp()}",
            payment_status='completed',
            payment_date=datetime.now()
        )
        db.session.add(new_payment)
        db.session.commit()

        flash('Cash payment added successfully!', 'success')
        return redirect(url_for('manage_payments'))  # change as per your dashboard route

    return render_template('admin_side/payments/add_cash_payment.html', students=students, courses=courses)




