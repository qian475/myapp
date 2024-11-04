from flask import Flask, render_template
import mysql.connector

app = Flask(__name__)

def get_data_from_database():
    cnx = mysql.connector.connect(
        host="java-demo-db-mysql.ns-7otl3mb2.svc",
        user="root",
        password="l9h8f24b",
        database="test_db"
    )

    cursor = cnx.cursor()
    cursor.execute("SELECT * FROM test")
    data = cursor.fetchall()
    cursor.close()
    cnx.close()

    return data

@app.route('/')
def index():
    data = get_data_from_database()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)