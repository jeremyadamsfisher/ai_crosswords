from flask import Flask
from flask.ext.heroku import Heroku
app = Flask(__name__, instance_relative_config=True)
heroku = Heroku(app)
from app import views
app.config.from_object('config')