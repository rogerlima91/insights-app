import streamlit as st
import importlib.util
import os

# Thin wrapper — routes Upload Report > Portfolio Overview to the same logic
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_overview.py")
_spec = importlib.util.spec_from_file_location("portfolio_overview_upload", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
