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

app = Flask(__name__)  # Initialize Flask app with the correct name

# CORS(app, resources={
  #  r"/*": {
     #   "origins": [
         #   "https://gozzo-store.web.app",
          #  "https://gozzo-store.firebaseapp.com"
       # ]
#    }
#})

CORS(app)

# Access environment variables
api_key = os.getenv('RAZORPAY_API_KEY')
api_secret = os.getenv('RAZORPAY_API_SECRET')
GMAIL_USER = os.getenv('GMAIL_USER')  # Add this to .env for your Gmail ID
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')  # Add this to .env for your app password

# Initialize Razorpay client
client = razorpay.Client(auth=(api_key, api_secret))

# Route to create an order
@app.route('/create-order', methods=['POST'])
def create_order():
    data = request.get_json()
    fin_total = data.get('amount')  # Amount in INR
    
    if not fin_total:
        return jsonify({'error': 'Amount is required'}), 400
    
    # Convert to paise (100 paise = 1 INR)
    amount_in_paise = int(fin_total * 100)
    
    # Generate unique receipt ID for this order
    receipt = str(uuid.uuid4())
    
    # Create order data
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'payment_capture': '1',  # Automatic capture
        'receipt': receipt
    }
    
    try:
        # Create the Razorpay order
        order = client.order.create(data=order_data)
        # Return only necessary details (like order id)
        return jsonify({'id': order['id'], 'receipt': receipt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to verify the payment status

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.get_json()
        order_id = data.get('razorpay_order_id')
        payment_id = data.get('razorpay_payment_id')
        signature = data.get('razorpay_signature')

        # Check if all values are provided
        if not all([order_id, payment_id, signature]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # Razorpay built-in signature verification
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        return jsonify({"success": True, "message": "Payment verified successfully!"}), 200

    except razorpay.errors.SignatureVerificationError:
        return jsonify({"success": False, "message": "Payment verification failed!"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to send email via Gmail SMTP
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

        if not all([customer_email, customer_name, order_id, order_date, expiry_date, total_amount]):
            return jsonify({"error": "Missing required fields"}), 400

        # Email Content
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

            <p>Best Regards,<br>
            <strong>Pot It Up Team</strong></p>
        </body>
        </html>
        """

        # Set up the MIME structure for the email
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = customer_email
        msg['Subject'] = f"Order Confirmation - {order_id}"
        msg.attach(MIMEText(html_content, 'html'))

        # Connect to Gmail's SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
        server.starttls()  # Secure the connection
        server.login(GMAIL_USER, GMAIL_PASSWORD)

        # Send the email
        server.sendmail(GMAIL_USER, customer_email, msg.as_string())

        # Close the server connection
        server.quit()

        return jsonify({"status": "success", "message": "Email sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Health Check Routes ---

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
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.quit()
        return jsonify({"status": "healthy", "message": "Email service reachable"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

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
        timestamp = data.get('timestamp')  # Used for dispatch/deliver
        info_content = data.get('content')  # Used for info type

        if not all([email_type, customer_email, customer_name, order_id, order_date, total_amount]):
            return jsonify({"error": "Missing required fields"}), 400

        # --- Compose Email Based on Type ---
        if email_type == 'dispatch':
            subject = f"Order Dispatched - {order_id}"
            message_body = f"""
            <p>Dear <strong>{customer_name}</strong>,</p>
            <p>Your order <strong>{order_id}</strong> has been <strong>dispatched</strong> on <strong>{timestamp}</strong>.</p>
            <p>Order Date: {order_date}<br>
            Total Amount: ₹{total_amount}</p>
            <p>You will receive another email once your order is delivered.</p>
            """
        elif email_type == 'deliver':
            subject = f"Order Delivered - {order_id}"
            message_body = f"""
            <p>Dear <strong>{customer_name}</strong>,</p>
            <p>Your order <strong>{order_id}</strong> has been <strong>delivered</strong> on <strong>{timestamp}</strong>.</p>
            <p>Thank you for shopping with <strong>Pot It Up</strong>. We hope you loved it!</p>
            <p>Order Date: {order_date}<br>
            Total Amount: ₹{total_amount}</p>
            """
        elif email_type == 'info':
            if not info_content:
                return jsonify({"error": "Content required for info type"}), 400
            subject = f"Order Update - {order_id}"
            # Sanitize content to prevent scripts/XSS
            allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a']
            allowed_attrs = {'a': ['href', 'title']}
            safe_content = bleach.clean(info_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
            message_body = f"""
            <p>Dear <strong>{customer_name}</strong>,</p>
            {safe_content}
            <p>Order ID: {order_id}<br>
            Order Date: {order_date}<br>
            Total Amount: ₹{total_amount}</p>
            """
        else:
            return jsonify({"error": "Invalid email type"}), 400

        # Full HTML content wrapper
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

        # MIME structure
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = customer_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        # Send email via SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, customer_email, msg.as_string())
        server.quit()

        return jsonify({"status": "success", "message": f"{email_type.capitalize()} email sent successfully"}), 200
        

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# Route to send custom info email directly from admin panel
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

        # Sanitize HTML to prevent XSS
        allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a']
        allowed_attrs = {'a': ['href', 'title']}
        safe_content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, strip=True)

        # Compose email
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

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, customer_email, msg.as_string())
        server.quit()

        return jsonify({"status": "success", "message": "Custom email sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Flask Runner ---
if __name__ == '__main__':
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
