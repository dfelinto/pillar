from application import app
from application.controllers.shots import index

@app.route("/")
def homepage():
    """Very minimal setup that returns the shot index view"""
    return index()