# 🚀 ErgoVision  
### AI-Powered Posture & Eye Health Monitoring

ErgoVision is a real-time computer vision system that monitors **posture**, **blink rate**, and **eye fatigue** using AI-based facial landmark detection.  
It helps users maintain healthy screen habits and prevent digital strain.

---

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

git clone https://github.com/yourusername/ErgoVision.git
cd ErgoVision/backend

### 2️⃣ Create Virtual Environment

python -m venv venv
Activate:

Windows: venv\Scripts\activate

Mac/Linux: source venv/bin/activate

### 3️⃣ Install Dependencies

pip install -r requirements.txt

### 4️⃣ Run the App

python -m app.app
Open in browser: http://127.0.0.1:5000

### 🎯 Why ErgoVision?
With increasing screen time, poor posture and reduced blinking lead to:

Eye strain

Neck pain

Digital fatigue

ErgoVision provides a real-time AI-based solution to promote healthier screen usage.

# 👩‍💻 Author
Sakshi Gupta
Computer Vision & AI Enthusiast