from flask import Flask, render_template, request, jsonify
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import json
import os
import base64
import datetime

app = Flask(__name__)

# ── Load contacts from config ──────────────────────────────────────────────────
CONFIG_FILE = 'contacts.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "sender_email": "",
        "sender_password": "",
        "sender_name": "",
        "contacts": [],
        "police_email": ""
    }

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/setup')
def setup():
    return render_template('setup.html')

@app.route('/api/save_contacts', methods=['POST'])
def save_contacts():
    data = request.get_json()
    save_config(data)
    return jsonify({"status": "saved", "message": "Contacts saved successfully!"})

@app.route('/api/get_contacts')
def get_contacts():
    config = load_config()
    # Don't send password to frontend
    safe = {k: v for k, v in config.items() if k != 'sender_password'}
    safe['configured'] = bool(config.get('sender_email') and config.get('contacts'))
    return jsonify(safe)

@app.route('/api/send_sos', methods=['POST'])
def send_sos():
    data = request.get_json()
    config = load_config()

    lat  = data.get('lat', 'Unknown')
    lng  = data.get('lng', 'Unknown')
    audio_b64 = data.get('audio', None)
    timestamp = datetime.datetime.now().strftime("%d %B %Y, %I:%M:%S %p")
    maps_link = f"https://maps.google.com/?q={lat},{lng}"

    # Build email HTML body
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#cc0000;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="margin:0;font-size:28px;">🚨 SOS EMERGENCY ALERT</h1>
        <p style="margin:6px 0 0;font-size:14px;">This is an automated emergency message</p>
      </div>
      <div style="background:#fff3f3;border:2px solid #cc0000;padding:24px;border-radius:0 0 8px 8px;">
        <p style="font-size:16px;color:#333;">
          <strong>{config.get('sender_name','Someone')}</strong> has triggered an SOS emergency alert.
          Immediate assistance may be required.
        </p>
        <div style="background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:16px 0;">
          <h3 style="color:#cc0000;margin:0 0 12px;">📍 Last Known Location</h3>
          <p style="margin:4px 0;"><strong>Latitude:</strong> {lat}</p>
          <p style="margin:4px 0;"><strong>Longitude:</strong> {lng}</p>
          <p style="margin:12px 0 4px;"><strong>📌 Open in Google Maps:</strong></p>
          <a href="{maps_link}" style="background:#cc0000;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block;">
            View Location on Map
          </a>
        </div>
        <div style="background:#fff8e1;border:1px solid #ffc107;border-radius:8px;padding:12px;margin:12px 0;">
          <p style="margin:0;color:#856404;"><strong>⏰ Alert Time:</strong> {timestamp}</p>
        </div>
        {"<p style='color:#333;font-size:14px;'>🎙️ <strong>Audio recording is attached</strong> to this email.</p>" if audio_b64 else ""}
        <hr style="margin:20px 0;border:1px solid #eee;">
        <p style="color:#888;font-size:12px;text-align:center;">
          This alert was sent automatically by the SafeGuard SOS system.<br>
          Please take this seriously and contact the person or emergency services immediately.
        </p>
      </div>
    </div>
    """

    # Collect all recipients
    recipients = list(config.get('contacts', []))
    if config.get('police_email'):
        recipients.append(config['police_email'])

    if not recipients:
        return jsonify({"status": "error", "message": "No emergency contacts configured!"})

    if not config.get('sender_email') or not config.get('sender_password'):
        return jsonify({"status": "error", "message": "Email not configured! Please go to Setup page."})

    sent_count = 0
    errors = []

    for recipient in recipients:
        try:
            msg = MIMEMultipart('alternative')
            msg['From']    = f"{config.get('sender_name','SOS Alert')} <{config['sender_email']}>"
            msg['To']      = recipient
            msg['Subject'] = f"🚨 EMERGENCY SOS ALERT from {config.get('sender_name','Someone')} — {timestamp}"

            msg.attach(MIMEText(html_body, 'html'))

            # Attach audio if present
            if audio_b64:
                try:
                    audio_data = base64.b64decode(audio_b64.split(',')[1] if ',' in audio_b64 else audio_b64)
                    part = MIMEBase('audio', 'webm')
                    part.set_payload(audio_data)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', filename=f'sos_audio_{timestamp.replace(" ","_").replace(",","")}.webm')
                    msg.attach(part)
                except Exception as ae:
                    errors.append(f"Audio attach error: {str(ae)}")

            # Send via Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(config['sender_email'], config['sender_password'])
                server.sendmail(config['sender_email'], recipient, msg.as_string())
            sent_count += 1

        except Exception as e:
            errors.append(f"Failed to send to {recipient}: {str(e)}")

    if sent_count > 0:
        return jsonify({
            "status": "success",
            "message": f"SOS sent to {sent_count} contact(s)!",
            "sent": sent_count,
            "errors": errors
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to send SOS!",
            "errors": errors
        })

if __name__ == '__main__':
    print("\n✅ SafeGuard SOS running at http://localhost:5000\n")
    app.run(debug=True)
    