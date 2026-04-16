from flask import Flask, jsonify
app = Flask(__name__)
@app.route('/')
def hello():
    return jsonify({"status": "ok"})
if __name__ == "__main__":
    print("Starting Flask test...")
    app.run(port=5051)
