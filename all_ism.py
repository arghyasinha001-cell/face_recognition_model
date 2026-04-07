import cv2
import face_recognition
import numpy as np
import os
import time
from datetime import datetime
import pyttsx3
from twilio.rest import Client
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================== CONFIGURATION ==================
# Copy config.py.example → config.py and fill in your own credentials.
# config.py is listed in .gitignore and will never be committed.

try:
    import config
    TWILIO_SID        = config.TWILIO_SID
    TWILIO_AUTH_TOKEN = config.TWILIO_AUTH_TOKEN
    TWILIO_FROM       = config.TWILIO_FROM
    TWILIO_TO         = config.TWILIO_TO
    EMAIL_ADDRESS     = config.EMAIL_ADDRESS
    EMAIL_PASSWORD    = config.EMAIL_PASSWORD
    EMAIL_TO          = config.EMAIL_TO
except ImportError:
    print("[WARNING] config.py not found. Alerts (SMS/call/email) will be disabled.")
    print("          Copy config.py.example to config.py and fill in your credentials.")
    TWILIO_SID = TWILIO_AUTH_TOKEN = TWILIO_FROM = TWILIO_TO = None
    EMAIL_ADDRESS = EMAIL_PASSWORD = EMAIL_TO = None

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587

# ====================================================

# ---------------- FOLDER PATHS ----------------
KNOWN_FACES_DIR   = resource_path("known_faces")
UNKNOWN_FACES_DIR = resource_path("unknown_faces")
os.makedirs(KNOWN_FACES_DIR,   exist_ok=True)
os.makedirs(UNKNOWN_FACES_DIR, exist_ok=True)

# ---------------- LOAD / BUILD FACE ENCODINGS ----------------
ENC_PATH   = resource_path("known_encodings.npy")
NAMES_PATH = resource_path("known_names.npy")

if os.path.exists(ENC_PATH) and os.path.exists(NAMES_PATH):
    known_encodings = list(np.load(ENC_PATH,   allow_pickle=True))
    known_names     = list(np.load(NAMES_PATH, allow_pickle=True))
    print(f"[INFO] Loaded {len(known_encodings)} known faces from cache.")
else:
    print("[INFO] Encoding known faces from known_faces/ directory...")
    known_encodings, known_names = [], []

    image_extensions = (".jpg", ".jpeg", ".png")
    for filename in os.listdir(KNOWN_FACES_DIR):
        if filename.lower().endswith(image_extensions):
            path  = os.path.join(KNOWN_FACES_DIR, filename)
            image = face_recognition.load_image_file(path)
            encs  = face_recognition.face_encodings(image)

            if encs:
                known_encodings.append(encs[0])
                known_names.append(os.path.splitext(filename)[0])
                print(f"[INFO]   Encoded: {filename}")
            else:
                print(f"[WARNING] No face found in {filename} – skipping.")

    np.save(ENC_PATH,   known_encodings)
    np.save(NAMES_PATH, known_names)
    print(f"[INFO] Encodings saved ({len(known_encodings)} faces).")

# ---------------- ALERT FUNCTIONS ----------------
def _alerts_configured():
    """Return True only if Twilio credentials are set."""
    return all([TWILIO_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO])

def _email_configured():
    return all([EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_TO])


def send_sms_alert(message):
    if not _alerts_configured():
        print("[SKIP] SMS alert skipped – Twilio not configured.")
        return

    def _send():
        try:
            client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)
            print("[INFO] SMS sent.")
        except Exception as e:
            print("[ERROR] SMS failed:", e)

    threading.Thread(target=_send, daemon=True).start()


def make_call_alert():
    if not _alerts_configured():
        print("[SKIP] Call alert skipped – Twilio not configured.")
        return

    def _call():
        try:
            client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
            twiml = "<Response><Say>Unknown face detected. Please check SMS and email.</Say></Response>"
            client.calls.create(to=TWILIO_TO, from_=TWILIO_FROM, twiml=twiml)
            print("[INFO] Call initiated.")
        except Exception as e:
            print("[ERROR] Call failed:", e)

    threading.Thread(target=_call, daemon=True).start()


def announce_async(text):
    def _announce():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate",   160)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("[ERROR] TTS failed:", e)

    threading.Thread(target=_announce, daemon=True).start()


def send_email_alert(subject, body, attachments):
    if not _email_configured():
        print("[SKIP] Email alert skipped – email credentials not configured.")
        return

    def _send():
        try:
            msg             = MIMEMultipart()
            msg["From"]     = EMAIL_ADDRESS
            msg["To"]       = EMAIL_TO
            msg["Subject"]  = subject
            msg.attach(MIMEText(body, "plain"))

            for path in attachments:
                if not os.path.exists(path):
                    continue
                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(path)}"
                )
                msg.attach(part)

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print("[INFO] Email sent.")
        except Exception as e:
            print("[ERROR] Email failed:", e)

    threading.Thread(target=_send, daemon=True).start()

# ---------------- CAMERA-COVER DETECTION ----------------
def is_camera_covered(frame, threshold=25):
    gray            = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    return mean_brightness < threshold

# ---------------- GLOBALS ----------------
video                  = None
running                = False
last_saved_time        = 0
last_unknown_encoding  = None
last_alert_time        = 0
ALERT_COOLDOWN         = 30   # seconds between repeated alerts for the same unknown face

camera_cover_alert_sent = False

# ---------------- FACE PROCESSING ----------------
def process_frame(frame):
    global last_saved_time, last_unknown_encoding, last_alert_time

    # Work on a quarter-size copy for speed; scale locations back up by 4×
    small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb, model="hog")
    encodings      = face_recognition.face_encodings(rgb, face_locations)

    for face_encoding, loc in zip(encodings, face_locations):
        name = "Unknown"

        if len(known_encodings) > 0:
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.45)
            if True in matches:
                best = int(np.argmin(face_recognition.face_distance(known_encodings, face_encoding)))
                name = known_names[best]

        top, right, bottom, left = [v * 4 for v in loc]

        if name == "Unknown":
            color = (0, 0, 255)
            ts    = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save a cropped image of the unknown face (at most every 5 s)
            if time.time() - last_saved_time > 5:
                crop = frame[top:bottom, left:right]
                if crop.size > 0:   # guard against zero-area crops at frame edge
                    path = os.path.join(UNKNOWN_FACES_DIR, f"unknown_{ts}.jpg")
                    cv2.imwrite(path, crop)
                    last_saved_time = time.time()
                    print("[INFO] Unknown face saved:", path)

            # Fire alert only for a genuinely new face and after cooldown
            new_face = (
                last_unknown_encoding is None or
                face_recognition.face_distance([last_unknown_encoding], face_encoding)[0] > 0.55
            )
            cooldown_elapsed = (time.time() - last_alert_time) > ALERT_COOLDOWN

            if new_face and cooldown_elapsed:
                alert = "ALERT: Unknown face detected"
                announce_async(alert)
                send_sms_alert(alert)
                make_call_alert()

                recent = sorted(
                    [
                        os.path.join(UNKNOWN_FACES_DIR, f)
                        for f in os.listdir(UNKNOWN_FACES_DIR)
                        if f.endswith(".jpg")
                    ],
                    key=os.path.getmtime,
                    reverse=True
                )[:3]

                send_email_alert(
                    subject=alert,
                    body=f"Unknown face detected at {ts}. Images attached.",
                    attachments=recent
                )

                last_unknown_encoding = face_encoding
                last_alert_time       = time.time()
        else:
            color = (0, 255, 0)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
        cv2.putText(
            frame, name,
            (left + 6, bottom - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            (255, 255, 255), 1
        )

    return frame

# ---------------- GUI FUNCTIONS ----------------
def start_camera():
    global video, running
    if running:
        return

    video = cv2.VideoCapture(0)
    if not video.isOpened():
        messagebox.showerror("Error", "Cannot access the camera. Check that no other app is using it.")
        return

    running = True
    update_frame()


def stop_camera():
    global running, video
    running = False
    if video:
        video.release()
        video = None
    video_label.configure(image="")


def update_frame():
    global running, video, camera_cover_alert_sent

    if not running:
        return

    ret, frame = video.read()
    if not ret:
        print("[WARNING] Failed to read frame from camera.")
        # Try to recover rather than silently stopping
        root.after(500, update_frame)
        return

    # Camera-cover check
    if is_camera_covered(frame):
        if not camera_cover_alert_sent:
            alert = "ALERT: Camera appears to be covered"
            announce_async(alert)
            send_sms_alert(alert)
            make_call_alert()
            send_email_alert(
                subject="Camera Covered Alert",
                body="The camera appears to be covered or is fully dark.",
                attachments=[]
            )
            camera_cover_alert_sent = True
    else:
        camera_cover_alert_sent = False

    frame = process_frame(frame)

    rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img    = Image.fromarray(rgb)
    imgtk  = ImageTk.PhotoImage(image=img)

    video_label.imgtk = imgtk          # keep a reference so GC doesn't collect it
    video_label.configure(image=imgtk)

    video_label.after(10, update_frame)


def exit_app():
    stop_camera()
    root.destroy()

# ---------------- TKINTER GUI ----------------
root = tk.Tk()
root.title("FaceGuard Security System")
root.resizable(False, False)

video_label = tk.Label(root)
video_label.pack()

btns = tk.Frame(root)
btns.pack(pady=10)

tk.Button(btns, text="▶  Start Detection", command=start_camera,  bg="#2e7d32", fg="white", width=16).grid(row=0, column=0, padx=5)
tk.Button(btns, text="⏹  Stop Camera",    command=stop_camera,   bg="#c62828", fg="white", width=16).grid(row=0, column=1, padx=5)
tk.Button(btns, text="✕  Exit",           command=exit_app,       bg="#37474f", fg="white", width=16).grid(row=0, column=2, padx=5)

root.protocol("WM_DELETE_WINDOW", exit_app)   # clean up on window-close

root.mainloop()
