from flask import Flask, request, jsonify
import razorpay
import uuid
import os
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add(
            "Access-Control-Allow-Origin",
            request.headers.get("Origin", "*")
        )
        response.headers.add(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization"
        )
        response.headers.add(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )
        return response, 200

## CORS(app, resources={
##    r"/*": {
##        "origins": [
##            "https://gozzo-store.web.app",
##            "https://gozzo-store.firebaseapp.com"
##        ]
##    }
##})
CORS(app, resources={r"/*": {"origins": "*"}})

api_key = os.getenv("RAZORPAY_API_KEY")
api_secret = os.getenv("RAZORPAY_API_SECRET")

assert api_key, "RAZORPAY_API_KEY missing"
assert api_secret, "RAZORPAY_API_SECRET missing"

client = razorpay.Client(auth=(api_key, api_secret))


@app.route("/create-order", methods=["POST", "OPTIONS"])
def create_order():
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")

    if not amount:
        return jsonify({"error": "Amount is required"}), 400

    try:
        amount_paise = int(float(amount) * 100)
        receipt = f"rcpt_{uuid.uuid4().hex[:10]}"

        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1
        })

        return jsonify({
            "success": True,
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "key": api_key
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    data = request.get_json(silent=True) or {}

    payment_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")

    if not all([payment_id, order_id, signature]):
        return jsonify({"error": "Missing payment verification data"}), 400

    try:
        client.utility.verify_payment_signature({
            "razorpay_payment_id": payment_id,
            "razorpay_order_id": order_id,
            "razorpay_signature": signature
        })

        payment = client.payment.fetch(payment_id)

        if payment.get("status") != "captured":
            return jsonify({"success": False, "message": "Payment not captured"}), 400

        return jsonify({
            "success": True,
            "message": "Payment verified successfully"
        }), 200

    except razorpay.errors.SignatureVerificationError:
        return jsonify({
            "success": False,
            "message": "Invalid payment signature"
        }), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
