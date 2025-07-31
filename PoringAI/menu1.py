from flask import(
  Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

bp = Blueprint('menu1', __name__, url_prefix='/menu1')

@bp.route('/')
def menu1():
  return render_template("menu1.html");