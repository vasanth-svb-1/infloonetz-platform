from flask import Flask,current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__,static_url_path='/static')

app.config['SECRET_KEY'] = 'your_secret_key_here'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///infloonetz.db?charset=utf8' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_AS_ASCII'] = False


db = SQLAlchemy(app)

from app import routes