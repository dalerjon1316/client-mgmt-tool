import streamlit as st
import sqlite3
import os
import time
from PIL import Image
import hashlib

# --- CONFIG ---
DB_NAME = "objects.db"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- DB SETUP ---


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Create places and objects tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            car_number TEXT NOT NULL,
            place_id INTEGER NOT NULL,
            image_path TEXT,
            FOREIGN KEY (place_id) REFERENCES places(id)
        )
    ''')

    # Create settings table to store hashed password
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Insert default password hash if not set yet (default: "admin123")
    c.execute("SELECT value FROM settings WHERE key = 'admin_password'")
    if c.fetchone() is None:
        default_password = "admin123"
        hashed_pw = hashlib.sha256(default_password.encode()).hexdigest()
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)",
                  ('admin_password', hashed_pw))

    conn.commit()
    conn.close()


init_db()

# --- DB FUNCTIONS ---


def get_password_hash():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'admin_password'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def check_password(entered_password):
    stored_hash = get_password_hash()
    entered_hash = hashlib.sha256(entered_password.encode()).hexdigest()
    return entered_hash == stored_hash


def update_admin_password(new_password):
    new_hash = hashlib.sha256(new_password.encode()).hexdigest()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "UPDATE settings SET value = ? WHERE key = 'admin_password'", (new_hash,))
    conn.commit()
    conn.close()


def get_places():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name FROM places ORDER BY name")
    places = c.fetchall()
    conn.close()
    return places


def add_place(name):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO places (name) VALUES (?)", (name.strip(),))
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        pass


def delete_place(place_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Check if any objects use this place
    c.execute("SELECT COUNT(*) FROM objects WHERE place_id = ?", (place_id,))
    count = c.fetchone()[0]
    if count == 0:
        c.execute("DELETE FROM places WHERE id = ?", (place_id,))
        conn.commit()
        deleted = True
    else:
        deleted = False
    conn.close()
    return deleted


def get_place_id_by_name(name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM places WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def object_exists(client_name, car_number):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM objects WHERE client_name = ? AND car_number = ?",
              (client_name, car_number))
    exists = c.fetchone() is not None
    conn.close()
    return exists


def add_object(client_name, car_number, place_id, image_file):
    image_path = None
    if image_file:
        ext = os.path.splitext(image_file.name)[1]
        timestamp = int(time.time())
        sanitized_name = client_name.replace(" ", "_")
        filename = f"{sanitized_name}_{timestamp}{ext}"
        image_path = os.path.join(IMAGES_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(image_file.read())

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO objects (client_name, car_number, place_id, image_path) VALUES (?, ?, ?, ?)",
              (client_name, car_number, place_id, image_path))
    conn.commit()
    conn.close()


def search_by_client_or_car(term):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT o.client_name, o.car_number, p.name, o.image_path
        FROM objects o
        JOIN places p ON o.place_id = p.id
        WHERE o.client_name LIKE ? OR o.car_number LIKE ?
    ''', (f"%{term}%", f"%{term}%"))
    results = c.fetchall()
    conn.close()
    return results


def search_by_place_name(place_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT o.client_name, o.car_number, o.image_path
        FROM objects o
        JOIN places p ON o.place_id = p.id
        WHERE p.name LIKE ?
    ''', (f"%{place_name}%",))
    results = c.fetchall()
    conn.close()
    return results


def get_all_objects():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT o.id, o.client_name, o.car_number, p.name
        FROM objects o
        JOIN places p ON o.place_id = p.id
        ORDER BY o.client_name
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def update_car_number(object_id, new_number):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE objects SET car_number = ? WHERE id = ?",
              (new_number, object_id))
    conn.commit()
    conn.close()


def delete_object(object_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM objects WHERE id = ?", (object_id,))
    conn.commit()
    conn.close()


# --- STREAMLIT APP ---
st.set_page_config(page_title="Client-Car Manager", layout="centered")

# --- AUTH STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- SIDEBAR LOGIN ---
with st.sidebar:
    if not st.session_state.logged_in:
        st.markdown("\U0001F510 **Admin Login**")
        password_input = st.text_input("Enter admin password", type="password")
        if st.button("Login"):
            if check_password(password_input):
                st.session_state.logged_in = True
                st.success("✅ Logged in")
                st.rerun()
            else:
                st.error("❌ Incorrect password")
    else:
        if st.button("\U0001F513 Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- TABS BASED ON AUTH STATE ---
if st.session_state.logged_in:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "\U0001F50D Search", "➕ Add Entry", "\U0001F4CD Manage Places", "✏️ Manage Entries", "\U0001F511 Change Password"
    ])
else:
    tab1, = st.tabs(["\U0001F50D Search"])

# ---------- TAB 1: SEARCH ----------
with tab1:
    st.header("\U0001F50D Search")

    search_type = st.radio("Search by", ["Client/Car Number", "Place"])

    if search_type == "Client/Car Number":
        term = st.text_input("Enter client name or car number")
        if st.button("Search"):
            results = search_by_client_or_car(term)
            if results:
                for i, (client_name, car_number, place, image_path) in enumerate(results, 1):
                    st.subheader(f"{i}. {client_name} — {car_number}")
                    st.caption(f"\U0001F4CD {place}")
                    if image_path and os.path.exists(image_path):
                        st.image(image_path, width=200)
            else:
                st.info("No results found.")
    else:
        place_term = st.text_input("Enter place name")
        if st.button("Search by Place"):
            results = search_by_place_name(place_term)
            if results:
                st.subheader(f"Clients at {place_term}:")
                for i, (client_name, car_number, image_path) in enumerate(results, 1):
                    st.markdown(f"**{i}. {client_name} — {car_number}**")
                    if image_path and os.path.exists(image_path):
                        st.image(image_path, width=150)
            else:
                st.info("No clients found at this place.")

# ---------- ADMIN-ONLY TABS ----------
if st.session_state.logged_in:
    # ---------- TAB 2: ADD CLIENT/CAR ----------
    with tab2:
        st.header("➕ Add New Client Entry")

        if "reset_form" not in st.session_state:
            st.session_state.reset_form = False
        if "file_key" not in st.session_state:
            st.session_state.file_key = str(time.time())

        if st.session_state.reset_form:
            st.session_state.file_key = str(time.time())
            st.session_state.reset_form = False

        client_name = st.text_input("Client Name")
        car_number = st.text_input("Car Number")

        places = get_places()
        place_names = [p[1] for p in places]
        selected_place = st.selectbox(
            "Select Place", place_names + ["➕ Add new place..."])

        new_place_name = ""
        if selected_place == "➕ Add new place...":
            new_place_name = st.text_input("New Place Name")
            final_place = new_place_name.strip()
        else:
            final_place = selected_place.strip()

        image = st.file_uploader("Optional Image", type=[
                                 "jpg", "jpeg", "png"], key=st.session_state.file_key)

        if st.button("Add Entry"):
            if not client_name or not car_number or not final_place:
                st.warning("All fields (except image) are required.")
            elif object_exists(client_name, car_number):
                st.warning(
                    "This client already has that car number registered.")
            else:
                add_place(final_place)
                place_id = get_place_id_by_name(final_place)
                add_object(client_name, car_number, place_id, image)
                st.success(f"Entry for {client_name} ({car_number}) added.")
                st.session_state.reset_form = True

    # ---------- TAB 3: MANAGE PLACES ----------
    with tab3:
        st.header("\U0001F4CD Manage Places")

        new_place_input = st.text_input(
            "New Place Name", key="new_place_input")
        if st.button("Add Place"):
            if new_place_input.strip():
                add_place(new_place_input.strip())
                st.success(f"Place '{new_place_input.strip()}' added.")
            else:
                st.warning("Place name cannot be empty.")

        st.subheader("Current Places")
        all_places = get_places()
        for place_id, name in all_places:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"- {name}")
            with col2:
                if st.button("Delete", key=f"del_place_{place_id}"):
                    success = delete_place(place_id)
                    if success:
                        st.success(f"Deleted place: {name}")
                        st.rerun()
                    else:
                        st.error(f"Can't delete '{name}'. It's in use.")

    # ---------- TAB 4: MANAGE ENTRIES ----------
    with tab4:
        st.header("✏️ Manage Entries")
        all_entries = get_all_objects()

        for entry_id, client_name, car_number, place in all_entries:
            col1, col2, col3 = st.columns([4, 3, 2])
            with col1:
                st.markdown(f"**{client_name} — {car_number}**  ({place})")
            with col2:
                new_number = st.text_input(
                    "New Number", key=f"edit_num_{entry_id}")
                if st.button("Update", key=f"update_{entry_id}"):
                    if new_number.strip():
                        update_car_number(entry_id, new_number.strip())
                        st.success("Car number updated.")
                        st.rerun()
                    else:
                        st.warning("Car number cannot be empty.")
            with col3:
                if st.button("❌ Delete", key=f"delete_{entry_id}"):
                    delete_object(entry_id)
                    st.success("Entry deleted.")
                    st.rerun()

    # ---------- TAB 5: CHANGE PASSWORD ----------
    with tab5:
        st.header("\U0001F511 Change Admin Password")
        current_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")

        if st.button("Update Password"):
            if not check_password(current_pw):
                st.error("❌ Current password is incorrect.")
            elif new_pw != confirm_pw:
                st.error("❌ New passwords do not match.")
            elif len(new_pw) < 4:
                st.warning("⚠️ Password too short.")
            else:
                update_admin_password(new_pw)
                st.success("✅ Password updated.")
