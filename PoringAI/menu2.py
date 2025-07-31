from flask import(
  Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

bp = Blueprint('menu2', __name__, url_prefix='/menu2')

@bp.route('/')
def menu2():
  return render_template("menu2.html");