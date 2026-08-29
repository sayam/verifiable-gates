import flask

app = flask.Flask(__name__)


@app.route("/x")
def x() -> str:
    return str(eval(flask.request.args["q"]))  # noqa: S307
