"""
Amazon Image Extractor — Streamlit App
========================================
Deployable on Streamlit Cloud (free) — share URL with your team.
Uses Selenium + Chrome in headless mode.

LOCAL:
    pip install -r requirements.txt
    streamlit run app.py

STREAMLIT CLOUD:
    Push to GitHub → deploy at share.streamlit.io
"""

import re, json, time, random, csv, io
from datetime import datetime

import requests
import streamlit as st
from PIL import Image
from io import BytesIO

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Amazon Image Extractor",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0f0f1a; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.stApp { background: #0d0d18; }
div[data-testid="stExpander"] {
    border: 1px solid #2a2a45 !important;
    border-radius: 10px !important;
    background: #1a1a2e !important;
}
div[data-testid="stExpander"] summary { background: #1a1a2e !important; }
.stProgress > div > div { background: #3b82f6 !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
MARKETPLACES = {
    "🇩🇪 Germany    (amazon.de)":     "amazon.de",
    "🇺🇸 USA         (amazon.com)":    "amazon.com",
    "🇬🇧 UK          (amazon.co.uk)":  "amazon.co.uk",
    "🇫🇷 France      (amazon.fr)":     "amazon.fr",
    "🇮🇹 Italy       (amazon.it)":     "amazon.it",
    "🇪🇸 Spain       (amazon.es)":     "amazon.es",
    "🇳🇱 Netherlands (amazon.nl)":     "amazon.nl",
    "🇸🇪 Sweden      (amazon.se)":     "amazon.se",
    "🇵🇱 Poland      (amazon.pl)":     "amazon.pl",
    "🇯🇵 Japan       (amazon.co.jp)":  "amazon.co.jp",
    "🇨🇦 Canada      (amazon.ca)":     "amazon.ca",
    "🇦🇺 Australia   (amazon.com.au)": "amazon.com.au",
    "🇮🇳 India       (amazon.in)":     "amazon.in",
    "🇧🇷 Brazil      (amazon.com.br)": "amazon.com.br",
    "🇲🇽 Mexico      (amazon.com.mx)": "amazon.com.mx",
    "🇦🇪 UAE         (amazon.ae)":     "amazon.ae",
    "🇸🇦 Saudi Arabia(amazon.sa)":     "amazon.sa",
    "🇸🇬 Singapore   (amazon.sg)":     "amazon.sg",
    "🇹🇷 Turkey      (amazon.com.tr)": "amazon.com.tr",
    "🇪🇬 Egypt       (amazon.eg)":     "amazon.eg",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def to_fullres(url):
    if not url:
        return url
    return re.sub(r'\._[A-Za-z0-9_,]+_\.', '.', url)


def is_noise(url):
    return bool(re.search(
        r'_SS\d{2,3}_|_SX\d{2,3}_|_AC_US\d{2,3}_|'
        r'sprite|play-button|transparent-pixel|_CR\d|twister-badge', url))


def extract_asin(raw):
    raw = raw.strip()
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", raw)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Z0-9]{10}", raw):
        return raw
    return None


def parse_asins(text):
    return list(dict.fromkeys(
        a for a in (extract_asin(l) for l in text.splitlines()) if a))


# ── Core image extraction ─────────────────────────────────────────────────────

def extract_images(html, driver=None):
    seen = set()
    urls = []
    variant_ids = set()

    def add(raw_url):
        if not raw_url or not raw_url.startswith("http"):
            return
        if is_noise(raw_url):
            return
        full = to_fullres(raw_url)
        if full not in seen:
            seen.add(full)
            urls.append(full)
            m = re.search(r'/images/I/([A-Za-z0-9%+\-]+)\.', full)
            if m:
                variant_ids.add(m.group(1))

    # 1. colorImages["initial"] — selected variant only
    m = re.search(
        r'"colorImages"\s*:\s*\{[^{]*?"initial"\s*:\s*(\[.*?\])\s*[,}]',
        html, re.DOTALL)
    if not m:
        m = re.search(r'"initial"\s*:\s*(\[\s*\{.*?\}\s*\])', html, re.DOTALL)
    if m:
        try:
            for entry in json.loads(m.group(1)):
                for key in ("hiRes", "large", "main", "thumb"):
                    val = entry.get(key)
                    if isinstance(val, str) and val:
                        add(val); break
                    elif isinstance(val, dict) and val:
                        add(list(val.keys())[0]); break
        except Exception:
            pass

    # 2. Selenium thumbnail clicks — catches missing images
    if driver:
        try:
            main_el = None
            try:
                main_el = driver.find_element(By.ID, "landingImage")
            except Exception:
                pass
            thumbs = driver.find_elements(
                By.CSS_SELECTOR,
                "#altImages li.item, #altImages .imageThumbnail")
            for thumb in thumbs:
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", thumb)
                    thumb.click()
                    time.sleep(0.5)
                    if main_el:
                        src = (main_el.get_attribute("data-old-hires") or
                               main_el.get_attribute("src") or "")
                        add(src)
                except Exception:
                    pass
        except Exception:
            pass

    # 3. data-old-hires attributes
    for u in re.findall(r'data-old-hires=["\']([^"\']+)["\']', html):
        add(u)

    # 4. Scoped raw HTML scan
    for vid in variant_ids:
        pat = (r'https://m\.media-amazon\.com/images/I/'
               + re.escape(vid)
               + r'\.[A-Za-z0-9_,]+\.(?:jpg|jpeg|png|webp)')
        for u in re.findall(pat, html):
            add(u)

    return urls


# ── Chrome driver ─────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_driver():
    """
    Cached Chrome driver.
    On Streamlit Cloud: uses system Chromium + system chromedriver (version-matched).
    Locally: falls back to webdriver-manager auto-download.
    """
    import os, shutil

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-infobars")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # System chromium paths (Streamlit Cloud / Linux)
    chromium_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    chromedriver_paths = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
    ]

    chromium_bin    = next((p for p in chromium_paths    if os.path.exists(p)), None)
    chromedriver_bin = next((p for p in chromedriver_paths if os.path.exists(p)), None)

    if chromium_bin and chromedriver_bin:
        opts.binary_location = chromium_bin
        svc = Service(executable_path=chromedriver_bin)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        svc = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=svc, options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"}
    )
    return driver


def load_thumb(url, size=(60, 60)):
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        return img
    except Exception:
        return None


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🛒 Amazon Image\nExtractor")
    st.caption("Full-res · Selected variant · Real browser")
    st.divider()

    mp_label = st.selectbox(
        "Marketplace",
        options=list(MARKETPLACES.keys()),
        index=0,
    )
    selected_domain = MARKETPLACES[mp_label]

    delay = st.slider("Delay between ASINs (sec)", 1.0, 15.0, 2.0, 0.5)

    st.divider()
    st.caption("ℹ️ Chrome runs on this server.\nYour team just needs a browser.")


# ── Main UI ───────────────────────────────────────────────────────────────────

st.title("🛒 Amazon Image Extractor")
st.caption("Extracts all full-resolution images for the selected variant · Powered by real Chrome")

asin_input = st.text_area(
    "ASINs or DP links — one per line",
    height=140,
    placeholder=(
        "B08SNMP8M1\n"
        "https://www.amazon.de/dp/B0FG87H6JB?th=1\n"
        "B07ABC5678\n..."
    ),
)

asins = parse_asins(asin_input) if asin_input.strip() else []
if asins:
    st.caption(f"**{len(asins)} ASINs** detected")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    run = st.button(
        "⚡ Extract ALL images",
        type="primary",
        disabled=not asins or not SELENIUM_OK,
        use_container_width=True,
    )
with col2:
    uploaded = st.file_uploader(
        "Load from file", type=["txt", "csv"],
        label_visibility="collapsed")

if uploaded:
    content = uploaded.read().decode("utf-8", errors="ignore")
    st.session_state["file_asins"] = content
    st.rerun()

if not SELENIUM_OK:
    st.error("Selenium not installed. Run: pip install selenium webdriver-manager")

# ── Run extraction ────────────────────────────────────────────────────────────

if run and asins:
    st.divider()

    stat_cols = st.columns(4)
    s_total   = stat_cols[0].empty()
    s_found   = stat_cols[1].empty()
    s_failed  = stat_cols[2].empty()
    s_imgs    = stat_cols[3].empty()

    def render_stats(results):
        s_total.metric("ASINs",       len(results))
        s_found.metric("Found",       sum(1 for r in results if r["status"] == "found"))
        s_failed.metric("Failed",     sum(1 for r in results if r["status"] == "failed"))
        s_imgs.metric("Total images", sum(len(r["images"]) for r in results))

    progress_bar = st.progress(0)
    status_text  = st.empty()
    results_area = st.container()

    results = []

    try:
        status_text.info("🚀 Launching Chrome...")
        driver = get_driver()

        for i, asin in enumerate(asins):
            status_text.info(
                f"⏳ [{i+1}/{len(asins)}]  Fetching **{asin}** from `{selected_domain}`...")
            progress_bar.progress(i / len(asins))

            images = []
            try:
                driver.get(f"https://www.{selected_domain}/dp/{asin}?th=1")
                try:
                    WebDriverWait(driver, 12).until(
                        EC.presence_of_element_located((By.ID, "altImages")))
                except Exception:
                    try:
                        WebDriverWait(driver, 8).until(
                            EC.presence_of_element_located((By.ID, "landingImage")))
                    except Exception:
                        pass
                time.sleep(1.2)
                images = extract_images(driver.page_source, driver)
            except Exception:
                pass

            status = "found" if images else "failed"
            results.append({
                "asin": asin, "domain": selected_domain,
                "images": images, "status": status,
            })
            render_stats(results)
            progress_bar.progress((i + 1) / len(asins))

            with results_area:
                r = results[-1]
                label = (f"✅  **{r['asin']}** — {len(r['images'])} images (this variant)"
                         if r["status"] == "found"
                         else f"❌  **{r['asin']}** — no images found")

                with st.expander(label, expanded=(r["status"] == "found")):
                    if r["images"]:
                        cols_per_row = 5
                        for row_start in range(0, len(r["images"]), cols_per_row):
                            row_imgs = r["images"][row_start:row_start + cols_per_row]
                            img_cols = st.columns(len(row_imgs))
                            for ci, img_url in enumerate(row_imgs):
                                with img_cols[ci]:
                                    thumb = load_thumb(img_url, (120, 120))
                                    if thumb:
                                        st.image(thumb, use_container_width=True)
                                    else:
                                        st.markdown("🖼")
                                    st.caption(f"#{row_start + ci + 1}")

                        st.divider()
                        st.markdown("**Image URLs:**")
                        for j, url in enumerate(r["images"], 1):
                            c = st.columns([0.05, 0.85, 0.1])
                            c[0].caption(f"#{j}")
                            c[1].code(url, language=None)
                            c[2].link_button("Open", url)

                        st.text_area(
                            "All URLs (select all → copy)",
                            value="\n".join(r["images"]),
                            height=80,
                            key=f"urls_{r['asin']}",
                            label_visibility="collapsed",
                        )

            if i < len(asins) - 1:
                time.sleep(delay + random.uniform(0.3, 1.0))

    except Exception as e:
        st.error(f"Error: {e}")

    finally:
        progress_bar.progress(1.0)
        found = sum(1 for r in results if r["status"] == "found")
        imgs  = sum(len(r["images"]) for r in results)
        status_text.success(
            f"✅ Done — {found}/{len(results)} ASINs · {imgs} images total")

    st.session_state["last_results"] = results

# ── Export CSV ────────────────────────────────────────────────────────────────

if "last_results" in st.session_state:
    results = st.session_state["last_results"]
    output  = io.StringIO()
    writer  = csv.writer(output)
    writer.writerow(["ASIN", "Marketplace", "Image_Number", "Image_URL"])
    for r in results:
        if r["images"]:
            for j, url in enumerate(r["images"], 1):
                writer.writerow([r["asin"], r["domain"], j, url])
        else:
            writer.writerow([r["asin"], r["domain"], "", ""])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with col3:
        st.download_button(
            label="📥 Export CSV",
            data=output.getvalue(),
            file_name=f"amazon_images_{ts}.csv",
            mime="text/csv",
            use_container_width=True,
        )
