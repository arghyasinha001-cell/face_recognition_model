# 🛡️ FaceGuard Security System

A real-time face-recognition security camera built with Python. It identifies known faces, alerts you about unknown intruders via **SMS, phone call, and email**, and warns you when the camera is covered.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Known-face recognition** | Put photos in `known_faces/` – the system learns them automatically |
| **Unknown-face alerts** | SMS + voice call via Twilio, email with captured images via Gmail |
| **Camera-cover detection** | Fires an alert when the feed goes dark |
| **Text-to-speech** | Local voice announcement on detection |
| **Smart cooldowns** | Prevents alert spam – same face won't re-trigger for 30 s |
| **Tkinter GUI** | Live video feed with Start / Stop / Exit controls |

---

## 📁 Project Structure

```
FaceGuard/
├── all_ism.py            ← Main application
├── config.py             ← YOUR credentials (never committed – see setup)
├── config.py.example     ← Template – copy and fill in
├── requirements.txt
├── .gitignore
├── known_faces/          ← Add photos of people you want recognised here
│   ├── Alice.jpg
│   └── Bob.png
└── unknown_faces/        ← Auto-created; captured intruder images saved here
```

---

## 🚀 Quick Start

### 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8 – 3.11 | 3.12+ not yet supported by `face_recognition` |
| `cmake` | Required to build `dlib` (dependency of `face_recognition`) |
| C++ build tools | Windows: Visual Studio Build Tools; Linux/Mac: `build-essential` / Xcode CLT |
| Webcam | Any USB or built-in camera |

> **Windows users:** Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and select *Desktop development with C++* before proceeding.

> **Linux users:** `sudo apt install cmake build-essential libopenblas-dev liblapack-dev`

### 2. Clone & install

```bash
git clone https://github.com/your-username/FaceGuard.git
cd FaceGuard

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

> Installing `face_recognition` compiles `dlib` from source – this can take **5–10 minutes** on first install.

### 3. Add known faces

Drop clear, front-facing photos into the `known_faces/` folder. Name each file after the person:

```
known_faces/
├── Alice.jpg
└── Bob.png
```

The filename (without extension) becomes the label shown on screen.

### 4. Configure credentials

```bash
cp config.py.example config.py
```

Open `config.py` and fill in your Twilio and Gmail details (see [Credentials Setup](#-credentials-setup) below). `config.py` is listed in `.gitignore` and will never be accidentally committed.

### 5. Run

```bash
python all_ism.py
```

Click **▶ Start Detection** in the window.

---

## 🔑 Credentials Setup

### Twilio (SMS + voice calls)

1. Create a free account at [twilio.com](https://www.twilio.com/try-twilio).
2. Get a free phone number from the Console.
3. Find your **Account SID** and **Auth Token** on the Console dashboard.
4. For Indian numbers on a trial account, verify the recipient at **Console → Verified Caller IDs**.
5. Fill in `config.py`:

```python
TWILIO_SID        = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN = "your_auth_token"
TWILIO_FROM       = "+1XXXXXXXXXX"   # your Twilio number
TWILIO_TO         = "+91XXXXXXXXXX"  # recipient (country code required)
```

### Gmail (email with image attachments)

Gmail requires an **App Password** – your normal password won't work.

1. Enable 2-Factor Authentication on your Google account.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Create a new app password (name it anything, e.g. *FaceGuard*).
4. Copy the 16-character password into `config.py`:

```python
EMAIL_ADDRESS  = "your_sender@gmail.com"
EMAIL_PASSWORD = "xxxx xxxx xxxx xxxx"   # App Password (spaces are fine)
EMAIL_TO       = "recipient@gmail.com"
```

> **Tip:** The sender and recipient can be the same Gmail address if you want to email yourself.

---

## 🔄 Re-encoding Known Faces

If you add or remove photos from `known_faces/`, delete the cached encoding files so they are rebuilt on next run:

```bash
rm known_encodings.npy known_names.npy
# Windows: del known_encodings.npy known_names.npy
```

---

## ⚙️ Tuning

| Variable in `all_ism.py` | Default | Effect |
|---|---|---|
| `tolerance` in `compare_faces` | `0.45` | Lower = stricter matching (fewer false positives) |
| `ALERT_COOLDOWN` | `30` s | Minimum seconds between repeated alerts for the same face |
| `threshold` in `is_camera_covered` | `25` | Mean pixel brightness below which camera is considered covered |
| Frame save interval | `5` s | How often an unknown face image is written to disk |

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `No module named 'face_recognition'` | Run `pip install face_recognition` inside your venv; make sure cmake + build tools are installed first |
| `dlib` fails to compile | Install cmake and C++ build tools (see Prerequisites) |
| Camera not accessible | Ensure no other app (Teams, Zoom, etc.) is using the webcam |
| SMS / call not received | Verify Twilio credentials; on trial accounts the recipient number must be verified |
| Email not sent | Use an App Password, not your account password; check spam folder |
| Faces not recognised | Use clear, well-lit, front-facing photos; delete `.npy` cache and restart |
| `unknown_faces/` filling up fast | Increase the save interval (currently 5 s) or periodically clear the folder |

---

## 📄 License

MIT – see `LICENSE` for details.
