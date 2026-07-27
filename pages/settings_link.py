import streamlit as st
import importlib.util
import os

# Thin wrapper — routes File Upload > Settings to the same settings.py logic
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.py")
_spec = importlib.util.spec_from_file_location("settings_link", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
