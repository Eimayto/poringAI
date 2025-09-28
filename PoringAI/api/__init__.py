from flask import Blueprint, render_template, request, url_for, session
import os, json, requests

bp = Blueprint("api", __name__)

from . import available_bikes
from . import generate_sentence
from . import available_nearby_bikes



def fetch_available_bikes(hub_name: str):
  """내부 API(/available-bikes) 호출"""
  api_url = url_for("api.available_bikes", _external=True)
  try:
    res = requests.get(api_url, params={"hub_name": hub_name}, timeout=5)
    return res.json(), res.status_code
  except Exception as e:
    return {"hub_name": hub_name, "found": False, "available_bikes": 0, "error": str(e)}, 500