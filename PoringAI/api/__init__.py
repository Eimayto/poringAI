from flask import Blueprint

bp = Blueprint("api", __name__)

from . import available_bikes
from . import generate_sentence