from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

import os
import uuid
import base64
import requests
import magic
import razorpay
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Handle preflight OPTIONS requests
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

# CORS configuration
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "https://gozzo-store.web.app",
                "https://gozzo-store.firebaseapp.com"
            ]
        }
    }
)

# Environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = "Jishith-droid"
GITHUB_REPO = "GOZZO-uploads"
GITHUB_BRANCH = "main"
GITHUB_DIR = "uploads"

MAX_FILES = 5
MAX_SIZE_MB = 5
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN not set")

# -------------------- ROUTES --------------------

@app.route("/save-image", methods=["POST"])
def save_image():
    files = request.files.getlist("images")

    if not files:
        return jsonify(message="No images provided"), 400
    if len(files) > MAX_FILES:
        return jsonify(message=f"Maximum {MAX_FILES} images allowed"), 400

    uploaded_urls = []

    for file in files:
        if not file or file.filename == "":
            return jsonify(message="Invalid file detected"), 400

        # Size check
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_SIZE_MB * 1024 * 1024:
            return jsonify(message="Image exceeds size limit"), 400

        # MIME check
        header = file.read(2048)
        file.seek(0)
        mime = magic.from_buffer(header, mime=True)
        if mime not in ALLOWED_MIME:
            return jsonify(message=f"Unsupported image type: {mime}"), 400

        # Prepare file
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            return jsonify(message="Missing file extension"), 400

        final_name = f"{uuid.uuid4().hex}{ext}"
        content_b64 = base64.b64encode(file.read()).decode("utf-8")
        github_path = f"{GITHUB_DIR}/{final_name}"

        # GitHub upload
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{github_path}"
        payload = {
            "message": f"Upload image {final_name}",
            "content": content_b64,
            "branch": GITHUB_BRANCH
        }
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }

        r = requests.put(url, json=payload, headers=headers)
        if r.status_code not in (200, 201):
            return jsonify(
                message="GitHub upload failed",
                github_status=r.status_code,
                github_error=r.json()
            ), 502

        raw_url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{github_path}"
        uploaded_urls.append(raw_url)

    return jsonify(message="Upload successful", urls=uploaded_urls), 201

@app.route("/wake", methods=["GET"])
def wake():
    return "OK", 200

# Razorpay setup
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
        return jsonify({"success": True, "message": "Payment verified successfully"}), 200
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"success": False, "message": "Invalid payment signature"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
