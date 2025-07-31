from flask import(
  Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

bp = Blueprint('menu4', __name__, url_prefix='/menu4')

@bp.route('/')
def menu4():
  return render_template("menu4.html");