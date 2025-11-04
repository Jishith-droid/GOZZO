from flask import Flask, request, jsonify
import razorpay
import uuid
from flask_cors import CORS
from dotenv import load_dotenv
import os
import bleach
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)  # Correct Flask init

CORS(app, resources={
    r"/*": {
        "origins": [
            "https://gozzo-store.web.app",
            "https://gozzo-store.firebaseapp.com"
        ]
    }
})

# Access environment variables
api_key = os.getenv('RAZORPAY_API_KEY')
api_secret = os.getenv('RAZORPAY_API_SECRET')
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')

# Initialize Razorpay client
client = razorpay.Client(auth=(api_key, api_secret))


# ---------- ROUTE: Create Razorpay Order ----------
@app.route('/create-order', methods=['POST'])
def create_order():
    data = request.get_json()
    fin_total = data.get('amount')  # Amount in INR

    if not fin_total:
        return jsonify({'error': 'Amount is required'}), 400

    amount_in_paise = int(float(fin_total) * 100)
    receipt = str(uuid.uuid4())

    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'payment_capture': '1',
        'receipt': receipt
    }

    try:
        order = client.order.create(data=order_data)
        return jsonify({'id': order['id'], 'receipt': receipt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- ROUTE: Verify Payment ----------
@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    payment_id = request.json.get('payment_id')

    if not payment_id:
        return jsonify({'error': 'Payment ID is required'}), 400

    try:
        payment = client.payment.fetchpayment_id)
        if payment['status'] == 'captured':
            return jsonify({"success": True, "message": "Payment verified successfully!"})
        else:
            return jsonify({"success": False, "message": "Payment failed!"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- ROUTE: Send Email ----------
@app.route('/send-email', methods=['POST'])
def send_email():
    try:
        data = request.json
        customer_email = data.get('email')
        customer_name = data.get('customer_name')
        order_id = data.get('order_id')
        order_date = data.get('order_date')
        expiry_date = data.get('expiry_date')
        total_amount = data.get('total_amount')

        # Validate all required fields
        if not all([customer_email, customer_name, order_id, order_date, expiry_date, total_amount]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            }), 400

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #4CAF50;">Order Confirmation</h2>
            <p>Dear <strong>{customer_name}</strong>,</p>
            <p>Thank you for shopping with <strong>Pot It Up</strong>! Your order has been successfully placed.</p>

            <h3>Order Details:</h3>
            <table style="border-collapse: collapse; width: 100%; border: 1px solid #ddd;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 10px; border: 1px solid #ddd;">Order ID</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Order Date</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Expected Delivery Date</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Total Amount</th>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">{order_id}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{order_date}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{expiry_date}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">₹{total_amount}</td>
                </tr>
            </table>

            <p><strong>Note:</strong> This order is non-refundable and non-exchangeable.</p>
            <p>For any queries, contact us at <a href="mailto:potitupspprt@gmail.com">potitupspprt@gmail.com</a>.</p>
            <p>Best Regards,<br><strong>Pot It Up Team</strong></p>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = customer_email
        msg['Subject'] = f"Order Confirmation - {order_id}"
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, customer_email, msg.as_string())

        return jsonify({
            "status": "success",
            "message": "Email sent successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ---------- HEALTH CHECK ROUTES ----------
@app.route('/health/order', methods=['GET'])
def health_order():
    try:
        client.order.all({'count': 1})
        return jsonify({"status": "healthy", "message": "Order service reachable"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/health/payment', methods=['GET'])
def health_payment():
    try:
        client.payment.all({'count': 1})
        return jsonify({"status": "healthy", "message": "Payment service reachable"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/health/email', methods=['GET'])
def health_email():
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
        return jsonify({"status": "healthy", "message": "Email service reachable"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# ---------- ROUTE: Send Admin Email ----------
@app.route('/send-admin-email', methods=['POST'])
def send_admin_email():
    try:
        data = request.json
        email_type = data.get('type')
        customer_email = data.get('email')
        customer_name = data.get('customer_name')
        order_id = data.get('order_id')
        order_date = data.get('order_date')
        total_amount = data.get('total_amount')
        timestamp = data.get('timestamp')
        info_content = data.get('content')

        if not all([email_type, customer_email, customer_name, order_id, order_date, total_amount]):
            return jsonify({"error": "Missing required fields"}), 400

        if email_type == 'dispatch':
            subject = f"Order Dispatched - {order_id}"
            message_body = f"""
            <p>Dear <strong>{customer_name}</strong>,</p>
            <p>Your order <strong>{order_id}</strong> has been <strong>dispatched</strong> on <strong>{timestamp}</strong>.</p>
            <p>Order Date: {order_date}<br>Total Amount: ₹{total_amount}</p>
            <p>You will receive another email once your order is delivered.</p>
            """
        elif email_type == 'deliver':
            subject = f"Order Delivered - {order_id}"
            message_body = f"""
            <p>Dear <strong>{customer_name}</strong>,</p>
            <p>Your order <strong>{order_id}</strong> has been <strong>delivered</strong> on <strong>{timestamp}</strong>.</p>
            <p>Thank you for shopping with <strong>Pot It Up</strong>.</p>
            <p>Order Date: {order_date}<br>Total Amount: ₹{total_amount}</p>
            """
        elif email_type == 'info':
            if not info_content:
                return jsonify({"error": "Content required for info type"}), 400
            allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a']
            allowed_attrs = {'a': ['href', 'title']}
            safe_content = bleach.clean(info_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
            subject = f"Order Update - {order_id}"
            message_body = f"""
            <p>Dear <strong>{customer_name}</strong>,</p>
            {safe_content}
            <p>Order ID: {order_id}<br>Order Date: {order_date}<br>Total Amount: ₹{total_amount}</p>
            """
        else:
            return jsonify({"error": "Invalid email type"}), 400

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            {message_body}
            <hr>
            <p>For any questions, contact us at <a href="mailto:potitupspprt@gmail.com">potitupspprt@gmail.com</a></p>
            <p><strong>Pot It Up Team</strong></p>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = customer_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, customer_email, msg.as_string())

        return jsonify({"status": "success", "message": f"{email_type.capitalize()} email sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- ROUTE: Send Custom User Email ----------
@app.route('/send-user-email', methods=['POST'])
def send_user_email():
    try:
        data = request.json
        customer_email = data.get('email')
        customer_name = data.get('customer_name')
        user_uid = data.get('user_uid')
        content = data.get('content')

        if not all([customer_email, customer_name, user_uid, content]):
            return jsonify({"error": "Missing required fields"}), 400

        allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a']
        allowed_attrs = {'a': ['href', 'title']}
        safe_content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, strip=True)

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <p>Dear <strong>{customer_name}</strong>,</p>
            {safe_content}
            <hr>
            <p><small>User ID: <code>{user_uid}</code></small></p>
            <p>For any questions, contact us at <a href="mailto:potitupspprt@gmail.com">potitupspprt@gmail.com</a></p>
            <p><strong>Pot It Up Team</strong></p>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = customer_email
        msg['Subject'] = "Update from Pot It Up"
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, customer_email, msg.as_string())

        return jsonify({"status": "success", "message": "Custom email sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- FLASK RUNNER ----------
if __name__ == '__main__':
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
