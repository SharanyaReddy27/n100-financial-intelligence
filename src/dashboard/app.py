import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Nifty 100 Analytics Dashboard")

st.markdown("""
Welcome to the **Nifty 100 Financial Intelligence Dashboard**.

Use the **Pages** menu in the sidebar to navigate through:

- 🏠 Home
- 🏢 Company Profile
- 🔍 Screener
- 👥 Peer Comparison
- 📊 Trends
- 🏭 Sector Analysis
- 💰 Capital Allocation
- 📄 Annual Reports
""")