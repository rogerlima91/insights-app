import streamlit as st
import importlib.util
import os

# Mark this page as "ongoing" mode so performance_insights.py can show the right label
st.session_state['_pi_source_mode'] = 'ongoing'

# Load and run performance_insights.py in this same Streamlit context
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "performance_insights.py")
_spec = importlib.util.spec_from_file_location("performance_insights_ongoing", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
