from datetime import datetime
from flask import request, jsonify, redirect, url_for, render_template, session, abort, send_file, make_response, flash
from app import app, db, razorpay_client
from models import Payment, Course, Student
from routes import login_required, student_required
from dateutil.relativedelta import relativedelta
from io import BytesIO, StringIO
import csv
from pagination import Pagination
from werkzeug.security import check_password_hash
from functools import wraps

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
        
        # Create payment record
        new_payment = Payment(
            student_id=student_id,
            amount=amount,
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
        if payment.payment_status != 'completed':
            payment.transaction_id = razorpay_payment_id
            payment.payment_status = 'completed' if razorpay_payment['status'] == 'captured' else razorpay_payment['status']
            payment.payment_date = datetime.utcnow()
            db.session.commit()
        
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
    if payment and payment.payment_status != 'completed':
        payment.transaction_id = payment['id']
        payment.payment_status = 'completed'
        payment.payment_date = datetime.utcnow()
        db.session.commit()

def handle_failed_payment(payment):
    payment = Payment.query.filter_by(order_id=payment['order_id']).first()
    if payment and payment.payment_status != 'failed':
        payment.payment_status = 'failed'
        db.session.commit()





@app.route('/payment/success')
@login_required
@student_required
def payment_success():
    return render_template('student_side/payment_success.html')

@app.route('/payment/failed')
@login_required
@student_required
def payment_failed():
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

@app.route("/student/payment-receipt/<int:payment_id>")
@login_required
@student_required
def payment_receipt(payment_id):
    student_id = session.get('user_id')
    payment = Payment.query.filter_by(
        payment_id=payment_id,
        student_id=student_id
    ).first_or_404()
    
    student = Student.query.filter_by(student_id=student_id).first()
    course = Course.query.filter_by(course_id=payment.course_id).first()
    
    return render_template(
        'student_side/payment_receipt.html',
        payment=payment,
        student=student,
        course=course,
        now=datetime.now()
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