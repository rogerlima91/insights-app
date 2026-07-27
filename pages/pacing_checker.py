import streamlit as st
import importlib.util
import os

# Mark this page as "one-off" pacing checker mode
st.session_state['_lc_source_mode'] = 'one-off'

# Load and run live_campaigns.py in this same Streamlit context
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_campaigns.py")
_spec = importlib.util.spec_from_file_location("live_campaigns_pacing", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
