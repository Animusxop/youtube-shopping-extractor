# 🛍️ YouTube Shopping Product Extractor

A web application and CLI tool to extract tagged affiliate products (**Amazon, Flipkart, Shopsy**) from YouTube videos and YouTube Shorts directly from YouTube shopping metadata.

---

## ✨ Features

- ⚡ **Single Video Scanner**: Paste any YouTube Short or Video URL to extract all tagged products, ASINs, Flipkart PIDs, product titles, images, and direct affiliate store links.
- 📦 **Batch URL Processor**: Process lists of URLs (or upload a file) in one batch and download an aggregated CSV/JSON report.
- 🖼️ **Interactive Views**: Switch between a responsive Product Card Gallery and an interactive Data Table.
- 📥 **Export Ready**: Instant export to CSV and JSON.
- 💻 **Dual Mode**: Can be run as a Streamlit web app (`app.py`) or as a standalone CLI script (`extract.py`).

---

## 🚀 Quick Start (Local)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Streamlit Web App
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 3. Run via CLI (Optional)
```bash
python extract.py https://www.youtube.com/shorts/7dhfAlKfFnU
```

---

## 🌐 Deploy to Streamlit Community Cloud (Free)

1. **Initialize Git and commit**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: YouTube Shopping Product Extractor"
   ```

2. **Push to GitHub**:
   - Create a repository on GitHub (e.g. `youtube-shopping-extractor`).
   - Push your code:
     ```bash
     git remote add origin https://github.com/<YOUR-USERNAME>/<REPO-NAME>.git
     git branch -M main
     git push -u origin main
     ```

3. **Deploy on Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io) and log in with your GitHub account.
   - Click **New app**.
   - Choose your repository and branch (`main`).
   - Set **Main file path** to `app.py`.
   - Click **Deploy!** 🎉
