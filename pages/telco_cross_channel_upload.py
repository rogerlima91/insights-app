import streamlit as st
import importlib.util
import os

# Mark this page as "upload" mode so telco_cross_channel.py shows empty state / file upload
st.session_state['data_mode'] = 'upload'

# Load and run telco_cross_channel.py in this same Streamlit context
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telco_cross_channel.py")
_spec = importlib.util.spec_from_file_location("telco_cross_channel_upload", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
