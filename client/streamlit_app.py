import streamlit as st
import requests
import json
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".session.json")

# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Feeds App", page_icon="📸", layout="centered")

st.markdown("""
<style>
/* Gradient background */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #5b247a 0%, #1bcedf 100%);
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

/* Cards / containers */
[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 16px;
    padding: 1rem;
}

/* Main content text */
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3 {
    color: #ffffff !important;
}

/* Buttons */
button[kind="primary"], .stButton>button {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
}
.stButton>button:hover {
    opacity: 0.85;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Token persistence helpers
# ---------------------------------------------------------------------------

def _save_session(token: str, user: dict):
    """Persist token & user to a local file so it survives page refresh."""
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "user": user}, f)


def _load_session() -> tuple:
    """Load token & user from local file if it exists."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
            return data.get("token"), data.get("user")
        except (json.JSONDecodeError, IOError):
            pass
    return None, None


def _clear_session():
    """Remove persisted session file."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "token" not in st.session_state:
    saved_token, saved_user = _load_session()
    st.session_state.token = saved_token
    st.session_state.user = saved_user
    st.session_state.page = "feed" if saved_token else "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "login"
if "show_upload" not in st.session_state:
    st.session_state.show_upload = False

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _auth_header() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_register(email: str, password: str) -> requests.Response:
    return requests.post(
        f"{API_BASE}/auth/register",
        json={"email": email, "password": password},
    )


def api_login(email: str, password: str) -> requests.Response:
    return requests.post(
        f"{API_BASE}/auth/jwt/login",
        data={"username": email, "password": password},
    )


def api_get_me() -> requests.Response:
    return requests.get(f"{API_BASE}/users/me", headers=_auth_header())


def api_get_feed() -> requests.Response:
    return requests.get(f"{API_BASE}/feed", headers=_auth_header())


def api_upload(file, caption: str) -> requests.Response:
    return requests.post(
        f"{API_BASE}/upload",
        headers=_auth_header(),
        files={"file": (file.name, file.getvalue(), file.type)},
        data={"caption": caption},
    )


def api_delete_post(post_id: str) -> requests.Response:
    return requests.delete(
        f"{API_BASE}/posts/{post_id}",
        headers=_auth_header(),
    )


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def go_to(page: str):
    st.session_state.page = page


def logout():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.page = "login"
    _clear_session()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def login_page():
    st.title("🔐 Login")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please fill in all fields.")
            return
        resp = api_login(email, password)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.token = data["access_token"]
            me = api_get_me()
            if me.status_code == 200:
                st.session_state.user = me.json()
            _save_session(st.session_state.token, st.session_state.user)
            st.session_state.page = "feed"
            st.rerun()
        elif resp.status_code == 400:
            st.error("Invalid email or password.")
        else:
            st.error(f"Login failed ({resp.status_code}).")

    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Register", use_container_width=True):
        go_to("register")
        st.rerun()


def register_page():
    st.title("📝 Register")

    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register", use_container_width=True)

    if submitted:
        if not email or not password or not confirm:
            st.error("Please fill in all fields.")
            return
        if password != confirm:
            st.error("Passwords do not match.")
            return
        resp = api_register(email, password)
        if resp.status_code == 201:
            st.success("Registration successful! Please log in.")
            go_to("login")
            st.rerun()
        elif resp.status_code == 400:
            detail = resp.json().get("detail", "Registration failed.")
            st.error(str(detail))
        else:
            st.error(f"Registration failed ({resp.status_code}).")

    st.markdown("---")
    st.write("Already have an account?")
    if st.button("Back to Login", use_container_width=True):
        go_to("login")
        st.rerun()


def feed_page():
    # --- Sidebar ---
    with st.sidebar:
        user = st.session_state.user or {}
        st.markdown(f"**Logged in as**  \n{user.get('email', 'Unknown')}")
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()

    st.title("📸 Feeds")

    # --- Upload toggle button ---
    if st.button("➕ Upload new feed", use_container_width=True):
        st.session_state.show_upload = not st.session_state.show_upload
        st.rerun()

    # --- Upload section (shown/hidden via state) ---
    if st.session_state.show_upload:
        with st.container():
            uploaded_file = st.file_uploader(
                "Choose an image or video",
                type=["png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "avi", "webm"],
            )
            caption = st.text_input("Caption (optional)")
            if st.button("Upload", use_container_width=True, key="upload_btn"):
                if uploaded_file is None:
                    st.warning("Please select a file first.")
                else:
                    with st.spinner("Uploading..."):
                        resp = api_upload(uploaded_file, caption)
                    if resp.status_code == 200:
                        st.success("Uploaded successfully!")
                        st.session_state.show_upload = False
                        st.rerun()
                    else:
                        detail = resp.json().get("detail", "Upload failed.")
                        st.error(str(detail))

    st.markdown("---")

    # --- Feed listing ---
    resp = api_get_feed()
    if resp.status_code != 200:
        st.error("Failed to load feed.")
        return

    posts = resp.json().get("posts", [])

    if not posts:
        st.info("No posts yet. Upload your first feed!")
        return

    for post in posts:
        with st.container():
            # Media
            file_type = post.get("file_type", "image")
            url = post.get("url", "")
            if file_type == "video":
                st.video(url)
            else:
                st.image(url, use_container_width=True)

            # Caption & metadata
            caption_text = post.get("caption", "")
            if caption_text:
                st.markdown(f"**{caption_text}**")
            st.caption(post.get("created_at", ""))

            # Delete button (only for owner)
            if post.get("is_owner"):
                if st.button("🗑️ Delete", key=f"del_{post['id']}"):
                    resp = api_delete_post(post["id"])
                    if resp.status_code == 200:
                        st.success("Post deleted.")
                        st.rerun()
                    else:
                        st.error("Failed to delete post.")

            st.markdown("---")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

page = st.session_state.page

if page == "login":
    login_page()
elif page == "register":
    register_page()
elif page == "feed":
    if st.session_state.token is None:
        go_to("login")
        st.rerun()
    else:
        # Validate token is still valid
        me_resp = api_get_me()
        if me_resp.status_code == 401:
            logout()
            st.rerun()
        else:
            feed_page()
else:
    go_to("login")
    st.rerun()
