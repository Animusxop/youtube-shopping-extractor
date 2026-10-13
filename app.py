import re
import json
import time
import pandas as pd
import streamlit as st
from extract import extract_video_id, fetch_page, extract_products

st.set_page_config(
    page_title="YouTube Shopping Product Extractor",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for polished aesthetic
st.markdown(
    """
    <style>
    /* Metric Card Styling */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02));
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 18px 22px;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
        backdrop-filter: blur(8px);
    }
    
    /* Product Card Grid */
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 18px;
        margin-top: 15px;
        margin-bottom: 25px;
    }
    
    .product-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 14px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
    }
    
    .product-card:hover {
        transform: translateY(-3px);
        border-color: rgba(255, 255, 255, 0.28);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    
    .product-thumb-container {
        width: 100%;
        height: 180px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 12px;
    }
    
    .product-thumb {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-right: 6px;
    }
    
    .badge-amazon {
        background: #ff990022;
        color: #ff9900;
        border: 1px solid #ff990066;
    }
    
    .badge-flipkart {
        background: #2874f022;
        color: #4b8df8;
        border: 1px solid #2874f066;
    }
    
    .badge-shopsy {
        background: #84299322;
        color: #d869ec;
        border: 1px solid #84299366;
    }
    
    .badge-other {
        background: rgba(255, 255, 255, 0.1);
        color: #eee;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .product-title {
        font-size: 0.92rem;
        font-weight: 500;
        line-height: 1.35;
        margin: 10px 0 8px 0;
        color: #f0f0f0;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        min-height: 2.5em;
    }
    
    .product-id-tag {
        font-family: monospace;
        font-size: 0.75rem;
        color: #888;
        margin-bottom: 12px;
    }
    
    .store-btn {
        display: block;
        text-align: center;
        padding: 8px 14px;
        border-radius: 8px;
        background: #e63946;
        color: white !important;
        text-decoration: none !important;
        font-size: 0.85rem;
        font-weight: 600;
        transition: background 0.2s ease;
    }
    .store-btn:hover {
        background: #f1525f;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------- Sidebar -----------------
with st.sidebar:
    st.title("🛍️ YT Shopping")
    st.markdown(
        """
        Extract affiliate product tags (Amazon, Flipkart, Shopsy) from any YouTube Short or Video directly from YouTube metadata.
        """
    )
    st.divider()

    st.subheader("⚙️ Settings")
    request_timeout = st.slider("Request Timeout (seconds)", min_value=5, max_value=30, value=15, step=1)

    st.divider()
    st.markdown("### 📌 Features")
    st.markdown(
        """
        - ⚡ **Instant Extraction**: ASINs, Flipkart PIDs, product titles & thumbnails
        - 🔗 **Direct Store Links**: Direct links to buy/inspect products
        - 📦 **Batch Processing**: Inspect multiple video URLs simultaneously
        - 📥 **Export Ready**: Export to CSV & JSON with one click
        """
    )

    st.divider()
    st.caption("Powered by Streamlit & Python • YouTube Shopping Extractor")

# ----------------- App Header -----------------
st.title("🛍️ YouTube Shopping Product Extractor")
st.markdown("Inspect and export tagged affiliate products (Amazon, Flipkart, Shopsy) from YouTube videos and Shorts.")

tabs = st.tabs(["⚡ Single Video Scanner", "📦 Batch URL Scanner", "🚀 Deploy to Streamlit Cloud"])

# =========================================================================
# TAB 1: Single Video Scanner
# =========================================================================
with tabs[0]:
    col_input, col_sample = st.columns([4, 1])
    sample_url = "https://www.youtube.com/shorts/7dhfAlKfFnU"

    with col_sample:
        st.write("")
        st.write("")
        use_sample = st.button("Use Sample URL", use_container_width=True)

    with col_input:
        default_val = sample_url if use_sample else ""
        url_input = st.text_input(
            "Enter YouTube Video or Shorts URL:",
            value=default_val,
            placeholder="e.g. https://www.youtube.com/shorts/7dhfAlKfFnU or https://www.youtube.com/watch?v=...",
        )

    col_btn, _ = st.columns([2, 5])
    with col_btn:
        run_extract = st.button("🔍 Extract Products", type="primary", use_container_width=True)

    if run_extract or (use_sample and url_input):
        if not url_input.strip():
            st.warning("⚠️ Please provide a valid YouTube URL.")
        else:
            with st.spinner("Fetching YouTube metadata and parsing shopping tags..."):
                try:
                    video_id = extract_video_id(url_input)
                    html = fetch_page(video_id, timeout=request_timeout)
                    data = extract_products(html)
                    st.session_state["single_result"] = {
                        "video_id": video_id,
                        "url": url_input.strip(),
                        "data": data,
                    }
                except Exception as e:
                    st.error(f"❌ Failed to extract products: {str(e)}")

    if "single_result" in st.session_state:
        res = st.session_state["single_result"]
        vid = res["video_id"]
        data = res["data"]
        products = data.get("products", [])

        st.divider()

        # Top section: Video embed preview + Metrics
        col_video, col_metrics = st.columns([1, 1.4])

        with col_video:
            st.markdown(f"#### 📺 Video Preview (`{vid}`)")
            yt_watch_url = f"https://www.youtube.com/watch?v={vid}"
            st.video(yt_watch_url)
            st.caption(f"[Open on YouTube]({yt_watch_url})")

        with col_metrics:
            st.markdown("#### 📊 Extracted Product Overview")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Unique", data["total_unique"])
            m2.metric("Amazon Products", data["amazon_count"])
            m3.metric("Flipkart / Shopsy", data["flipkart_count"])

            st.markdown(
                f"""
                - **Video ID**: `{vid}`
                - **Shopping Renderer Tags**: `{data.get('product_renderer_count', 0)}`
                - **Unique ASINs (Amazon)**: `{len(data.get('amazon_asins', []))}`
                - **Unique PIDs (Flipkart/Shopsy)**: `{len(data.get('flipkart_pids', []))}`
                """
            )

        st.divider()

        if not products:
            st.info("ℹ️ No shopping tags or affiliate products were detected in this video.")
        else:
            # Controls: Search, Platform filter & View Switch
            col_search, col_filter, col_view = st.columns([2, 1.5, 1.5])
            with col_search:
                search_query = st.text_input("🔎 Search by Title or ID", placeholder="Filter products...")
            with col_filter:
                platforms_available = ["All"] + sorted(list({p["platform"] for p in products if p.get("platform")}))
                selected_platform = st.selectbox("Filter Platform", platforms_available)
            with col_view:
                view_mode = st.radio("Display View", ["Card Gallery", "Data Table"], horizontal=True)

            # Filter data
            filtered_products = products
            if selected_platform != "All":
                filtered_products = [p for p in filtered_products if p.get("platform") == selected_platform]
            if search_query.strip():
                q = search_query.lower().strip()
                filtered_products = [
                    p for p in filtered_products
                    if q in (p.get("title") or "").lower() or q in (p.get("product_id") or "").lower() or q in (p.get("merchant") or "").lower()
                ]

            st.markdown(f"**Showing {len(filtered_products)} of {len(products)} products**")

            # Gallery View
            if view_mode == "Card Gallery":
                cards_html = ['<div class="product-grid">']
                for p in filtered_products:
                    title = p.get("title") or "Unnamed Product"
                    merchant = p.get("merchant") or p.get("platform") or "Store"
                    platform = p.get("platform", "Other")
                    pid = p.get("product_id") or "N/A"
                    url = p.get("url") or "#"
                    thumb = p.get("thumbnail") or "https://via.placeholder.com/300x200?text=No+Image"

                    badge_class = "badge-other"
                    if platform == "Amazon":
                        badge_class = "badge-amazon"
                    elif platform == "Flipkart":
                        badge_class = "badge-flipkart"
                    elif platform == "Shopsy":
                        badge_class = "badge-shopsy"

                    card = f"""
                    <div class="product-card">
                        <div>
                            <div class="product-thumb-container">
                                <img src="{thumb}" class="product-thumb" alt="{title}" loading="lazy"/>
                            </div>
                            <span class="badge {badge_class}">{merchant}</span>
                            <div class="product-title" title="{title}">{title}</div>
                            <div class="product-id-tag">ID: {pid}</div>
                        </div>
                        <div>
                            <a href="{url}" target="_blank" class="store-btn">View on {platform if platform != 'Other' else 'Store'} ↗</a>
                        </div>
                    </div>
                    """
                    cards_html.append(card)
                cards_html.append('</div>')
                st.markdown("\n".join(cards_html), unsafe_allow_html=True)

            # Data Table View
            else:
                table_data = []
                for p in filtered_products:
                    table_data.append({
                        "Thumbnail": p.get("thumbnail") or "",
                        "Platform": p.get("platform") or "Other",
                        "Merchant": p.get("merchant") or "",
                        "Product ID": p.get("product_id") or "",
                        "Title": p.get("title") or "",
                        "Store URL": p.get("url") or "",
                    })
                df = pd.DataFrame(table_data)

                st.dataframe(
                    df,
                    column_config={
                        "Thumbnail": st.column_config.ImageColumn("Image", help="Product thumbnail preview"),
                        "Store URL": st.column_config.LinkColumn("Product Link", display_text="Visit Store"),
                        "Title": st.column_config.TextColumn("Product Title", width="large"),
                        "Product ID": st.column_config.TextColumn("Product ID / ASIN"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

            # Export actions
            st.subheader("📥 Export Results")
            exp_col1, exp_col2, _ = st.columns([1.5, 1.5, 3])

            export_df = pd.DataFrame(filtered_products)
            csv_data = export_df.to_csv(index=False).encode("utf-8")
            json_data = json.dumps(filtered_products, indent=2).encode("utf-8")

            with exp_col1:
                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=f"yt_products_{vid}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with exp_col2:
                st.download_button(
                    label="📦 Download JSON",
                    data=json_data,
                    file_name=f"yt_products_{vid}.json",
                    mime="application/json",
                    use_container_width=True,
                )


# =========================================================================
# TAB 2: Batch URL Scanner
# =========================================================================
with tabs[1]:
    st.subheader("📦 Batch Video Product Extraction")
    st.markdown("Paste multiple YouTube URLs (one per line) or upload a text file with links.")

    batch_text = st.text_area(
        "YouTube URLs (one per line):",
        placeholder="https://www.youtube.com/shorts/7dhfAlKfFnU\nhttps://www.youtube.com/watch?v=...\nhttps://youtu.be/...",
        height=140,
    )

    uploaded_file = st.file_uploader("Or upload a .txt / .csv file containing URLs", type=["txt", "csv"])

    urls_to_process = []
    if uploaded_file is not None:
        try:
            content = uploaded_file.read().decode("utf-8")
            urls_to_process.extend([line.strip() for line in content.splitlines() if line.strip()])
        except Exception as e:
            st.error(f"Error reading file: {e}")

    if batch_text.strip():
        urls_to_process.extend([line.strip() for line in batch_text.splitlines() if line.strip()])

    urls_to_process = list(dict.fromkeys(urls_to_process))  # deduplicate

    if urls_to_process:
        st.info(f"Detected **{len(urls_to_process)}** unique URLs ready for extraction.")

    start_batch = st.button("🚀 Start Batch Extraction", type="primary", disabled=not bool(urls_to_process))

    if start_batch and urls_to_process:
        progress_bar = st.progress(0)
        status_text = st.empty()

        all_batch_rows = []
        summary_rows = []

        total_vids = len(urls_to_process)
        for i, url in enumerate(urls_to_process):
            status_text.text(f"Processing ({i + 1}/{total_vids}): {url}")
            progress_bar.progress((i + 1) / total_vids)

            try:
                vid = extract_video_id(url)
                html = fetch_page(vid, timeout=request_timeout)
                res = extract_products(html)

                summary_rows.append({
                    "Video URL": url,
                    "Video ID": vid,
                    "Status": "Success",
                    "Total Products": res["total_unique"],
                    "Amazon Count": res["amazon_count"],
                    "Flipkart Count": res["flipkart_count"],
                })

                for prod in res.get("products", []):
                    all_batch_rows.append({
                        "Video URL": url,
                        "Video ID": vid,
                        "Platform": prod.get("platform", "Other"),
                        "Merchant": prod.get("merchant", ""),
                        "Product ID": prod.get("product_id", ""),
                        "Title": prod.get("title", ""),
                        "Store URL": prod.get("url", ""),
                        "Thumbnail": prod.get("thumbnail", ""),
                    })
            except Exception as e:
                summary_rows.append({
                    "Video URL": url,
                    "Video ID": "N/A",
                    "Status": f"Error: {str(e)}",
                    "Total Products": 0,
                    "Amazon Count": 0,
                    "Flipkart Count": 0,
                })
            time.sleep(0.3)  # Gentle delay to avoid rate-limiting

        status_text.success("✅ Batch extraction finished!")
        st.session_state["batch_summary"] = summary_rows
        st.session_state["batch_products"] = all_batch_rows

    if "batch_summary" in st.session_state:
        st.divider()
        st.markdown("### 📊 Batch Summary")
        sum_df = pd.DataFrame(st.session_state["batch_summary"])
        st.dataframe(sum_df, use_container_width=True, hide_index=True)

        batch_prods = st.session_state["batch_products"]
        if batch_prods:
            st.markdown("### 🛍️ Consolidated Product Catalog")
            prods_df = pd.DataFrame(batch_prods)

            st.dataframe(
                prods_df,
                column_config={
                    "Store URL": st.column_config.LinkColumn("Product Link", display_text="Visit Store"),
                    "Thumbnail": st.column_config.ImageColumn("Preview"),
                },
                use_container_width=True,
                hide_index=True,
            )

            csv_all = prods_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Consolidated CSV Report",
                data=csv_all,
                file_name="youtube_batch_products_report.csv",
                mime="text/csv",
            )


# =========================================================================
# TAB 3: Deploy to Streamlit Cloud
# =========================================================================
with tabs[2]:
    st.subheader("🚀 Deploying to Streamlit Community Cloud")
    st.markdown(
        """
        You can host this application online for free using **Streamlit Community Cloud** with your GitHub account.
        Here is the quick 4-step deployment process:
        """
    )

    st.markdown(
        """
        #### Step 1: Initialize Git and Commit
        Open your terminal in this project folder and run:
        ```bash
        git init
        git add .
        git commit -m "Initial commit: YouTube Shopping Product Extractor"
        ```

        #### Step 2: Push to GitHub
        1. Create a new repository on [GitHub](https://github.com/new) (e.g. `youtube-shopping-extractor`).
        2. Link your local repo and push:
        ```bash
        git remote add origin https://github.com/<YOUR_USERNAME>/youtube-shopping-extractor.git
        git branch -M main
        git push -u origin main
        ```

        #### Step 3: Deploy on Streamlit Cloud
        1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
        2. Click **New app**.
        3. Select your repository: `<YOUR_USERNAME>/youtube-shopping-extractor`.
        4. Set Main file path: `app.py`.
        5. Click **Deploy!** 🚀

        Your app will be live with a shareable URL like:
        `https://<your-app-name>.streamlit.app`
        """
    )
