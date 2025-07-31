from flask import(
  Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

bp = Blueprint('menu3', __name__, url_prefix='/menu3')

@bp.route('/')
def menu3():
  return render_template("menu3.html");