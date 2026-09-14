# 🚀 ErgoVision  
### AI-Powered Posture & Eye Health Monitoring

ErgoVision is a real-time computer vision system that monitors **posture**, **blink rate**, and **eye fatigue** using AI-based facial landmark detection.  
It helps users maintain healthy screen habits and prevent digital strain.

---

## 🔗 Live Demo

**Try it here:** https://ergovision-zypr.onrender.com

> ⚠️ Hosted on Render's free tier — if the link has been idle, the first load may take 30–60 seconds to wake up. Please allow camera access when prompted; all video processing happens on the server, only your browser accesses the webcam.

## ✨ Features

- 📹 Real-time posture detection  
- 👁️ Blink detection using Eye Aspect Ratio (EAR)  
- 📊 Live dashboard with statistics  
- 🧠 Fatigue level analysis  
- ⏳ 20-20-20 eye rule reminder  
- 📄 PDF session report generation  
- 💾 Session history using SQLite  

---

## 🛠️ Tech Stack

**Backend**
- Python
- Flask
- OpenCV
- MediaPipe FaceMesh
- NumPy
- ReportLab
- SQLite

## 🏗️ Architecture

The browser captures webcam frames using `getUserMedia` and sends them to the Flask backend for processing (posture + blink detection via MediaPipe), which returns annotated frames and live stats. This keeps camera access entirely client-side while detection runs server-side — each visitor gets an isolated, in-memory session so multiple users can use the app concurrently without interfering with each other.

**Frontend**
- HTML
- CSS
- JavaScript (Fetch API)

---

## 📂 Project Structure

```
ErgoVision/
│
├── backend/
│   ├── app/
│   │   ├── modules/
│   │   ├── static/
│   │   │   ├── css/
│   │   │   └── js/
│   │   ├── templates/
│   │   ├── app.py
│   │   └── __init__.py
│   │
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

## ⚙️ Setup & Run

### 1️⃣ Clone the repository

```
git clone https://github.com/Sakshigupta39/ErgoVision.git
cd ErgoVision/backend
```

### 2️⃣ Create Virtual Environment

python -m venv venv

Activate:
#### Windows: venv\Scripts\activate

#### Mac/Linux: source venv/bin/activate

### 3️⃣ Install Dependencies

pip install -r requirements.txt

### 4️⃣ Run the App

python -m app.app
Open in browser: http://127.0.0.1:5000

> For production, the app runs via `gunicorn app.app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT` (see `Procfile`), with `FLASK_DEBUG=false` and `SECRET_KEY` set as environment variables.

### 🎯 Why ErgoVision?
With increasing screen time, poor posture and reduced blinking lead to:

Eye strain
Neck pain
Digital fatigue

ErgoVision provides a real-time AI-based solution to promote healthier screen usage.

## ⚠️ Known Limitations

- Deployed on Render's free tier, which has limited CPU — detection speed and blink-count accuracy may vary under load compared to local runs.
- Session data (SQLite) is stored in-memory/ephemeral storage and resets on server restart or redeploy; this was an accepted trade-off for the current deployment stage.

# 👩‍💻 Author
Sakshi Gupta
Computer Vision & AI Enthusiast