# 🛒 Amazon Image Extractor

A Streamlit web app to extract **all full-resolution product images** from any Amazon marketplace — for the selected variant only.

![Python](https://img.shields.io/badge/python-3.9+-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.35+-red)
![Selenium](https://img.shields.io/badge/selenium-4.x-green)

---

## ✨ Features

- ✅ Extracts **all images** for the selected color/size variant only
- ✅ **Full resolution** — strips Amazon size codes automatically
- ✅ **20 marketplaces** — DE, US, UK, FR, IT, ES, NL, SE, PL, JP, CA, AU, IN, BR, MX, AE, SA, SG, TR, EG
- ✅ Paste ASINs or full DP links (mixed is fine)
- ✅ Load from `.txt` / `.csv` file
- ✅ Live progress — results appear one by one
- ✅ Image preview grid per ASIN
- ✅ Export all results as CSV
- ✅ Uses real Chrome — Amazon cannot block it

---

## 🚀 Deploy on Streamlit Cloud (free, shareable URL)

1. **Fork this repo** on GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → select your forked repo
4. Set **Main file path** to `app.py`
5. Click **Deploy** — done!

Your team gets a public URL like `https://yourname-amazon-images.streamlit.app`

---

## 💻 Run locally

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/amazon-image-extractor
cd amazon-image-extractor

# Install
pip install -r requirements.txt

# Run
streamlit run app.py
```

Open http://localhost:8501

---

## 📖 How to use

1. Select marketplace from the sidebar (e.g. 🇩🇪 Germany)
2. Paste ASINs or DP links — one per line:
   ```
   B08SNMP8M1
   https://www.amazon.de/dp/B0FG87H6JB?th=1
   B07ABC5678
   ```
3. Click **⚡ Extract ALL images**
4. Results appear live with image previews
5. Click **📥 Export CSV** to download

---

## 📁 Project structure

```
amazon-image-extractor/
├── app.py                  ← Main Streamlit app
├── requirements.txt        ← Python dependencies
├── packages.txt            ← System packages (Chromium for cloud)
├── .streamlit/
│   └── config.toml         ← Dark theme config
├── .gitignore
└── README.md
```

---

## 🔧 How it works

Amazon blocks regular HTTP requests. This app uses **Selenium** with a real (headless) Chrome browser:

1. **`colorImages["initial"]`** — reads the JSON blob Amazon embeds in the page. The `"initial"` key always contains only the currently selected variant's images.
2. **Thumbnail clicking** — Selenium physically clicks each thumbnail in the alt-images panel and captures the full-res URL that loads. This catches lifestyle shots and infographics not always in the JSON.
3. **Scoped scan** — only picks up image IDs confirmed in step 1, preventing cross-variant contamination.
4. **`to_fullres()`** — strips Amazon size codes (e.g. `._AC_SX679_.`) from every URL → always returns the original full-resolution file.

---

## ⚠️ Notes

- Amazon may occasionally show a CAPTCHA for some ASINs — increase the delay slider if you see failures
- Streamlit Cloud has a 1GB memory limit — tested fine for batches up to ~200 ASINs
- For 500+ ASINs, run locally for better performance
