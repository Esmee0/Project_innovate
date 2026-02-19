from flask import Flask

app = Flask(__name__)

@app.route("/")

def home():
    return "This is gonna be my solo project!!"

if __name__ == ("__main__"):
    app.run(debug=True)
