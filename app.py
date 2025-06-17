from flask import Flask, request, jsonify
import razorpay
import uuid
from flask_cors import CORS
from dotenv import load_dotenv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)  # Initialize Flask app with the correct name
CORS(app)  # Enable CORS for all routes

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
    payment_id = request.json.get('payment_id')
    
    if not payment_id:
        return jsonify({'error': 'Payment ID is required'}), 400

    try:
        # Fetch the payment details from Razorpay using the payment ID
        payment = client.payment.fetch(payment_id)
        
        # Check if the payment status is 'captured' (which means successful)
        if payment['status'] == 'captured':
            # Payment was successful
            # You can now update your order status in the database
            return jsonify({"success": True, "message": "Payment verified successfully!"})
        else:
            # Payment failed
            return jsonify({"success": False, "message": "Payment failed!"})

    except Exception as e:
        # Handle any errors (e.g., invalid payment ID or API error)
        return jsonify({'error': str(e)}), 500

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
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Secure the connection
        server.login(GMAIL_USER, GMAIL_PASSWORD)

        # Send the email
        server.sendmail(GMAIL_USER, customer_email, msg.as_string())

        # Close the server connection
        server.quit()

        return jsonify({"status": "success", "message": "Email sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
