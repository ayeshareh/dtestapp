import streamlit as st
import os
import json
import pandas as pd
import glob
from datetime import datetime
import requests
import re

# -------------------------------
# GEMINI API CONFIG (FIXED)
# -------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

if not GEMINI_API_KEY:
    st.error("❌ No Gemini API key found. Add it to Streamlit Secrets as `GEMINI_API_KEY`.")
    st.stop()

MODEL = "gemini-1.5-flash"   # ✅ stable working model
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"

# -------------------------------
# SAFE GEMINI API CALL (FIXED)
# -------------------------------
def gemini_chat(prompt: str):

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        response = requests.post(GEMINI_URL, json=payload)
    except Exception as e:
        st.error(f"❌ Could not reach Gemini API: {e}")
        return None

    if response.status_code != 200:
        st.error(f"❌ Gemini API Error {response.status_code}: {response.text}")
        return None

    try:
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        st.error(f"❌ Invalid response format from Gemini: {e}")
        return None
