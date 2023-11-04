from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
from os import environ
from sqlalchemy.exc import OperationalError
import time
from datetime import datetime
import json
import socket
import os

# Initialize Flask app
app = Flask(__name__)
# Configure database URI from environment variable
app.config["SQLALCHEMY_DATABASE_URI"] = environ.get("DB_URL")
# Initialize SQLAlchemy with the Flask app
db = SQLAlchemy(app)


# Function to wait for the database to be ready before starting the app
def wait_for_db():
    for _ in range(5):
        try:
            db.create_all()  # Try to initialize the database
            print("Connected to DB and created tables.")
            return
        except OperationalError:
            print("Database not ready, waiting...")
            time.sleep(5)
    print("Could not connect to the database.")
    exit(1)


# Call the wait_for_db function to ensure the database is ready
wait_for_db()


# Define a Temperature model for SQLAlchemy
class Temperature(db.Model):
    __tablename__ = "temperatures"
    id = db.Column(db.Integer, primary_key=True)
    id_sensor = db.Column(db.String(50), nullable=False)
    temperatura = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

    # Method to convert the model to JSON
    def json(self):
        return {
            "id_sensor": self.id_sensor,
            "temperatura": self.temperatura,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }


# Create the tables in the database
db.create_all()

# MQTT Setup
broker_hostname = os.getenv("BROKER_HOSTNAME", "mos1")

port = 1883
reconnect_delay = 10  # Delay between connection attempts in seconds


# Callback when the client receives a CONNACK response from the server
def on_connect(client, userdata, flags, return_code):
    if return_code == 0:
        print("Connected to MQTT Broker!")
        client.subscribe("warehouse/+/temperature")
    else:
        print(f"Failed to connect, return code {return_code}\n")


# Callback for when a PUBLISH message is received from the server
def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode())
        id_sensor = message.topic.split("/")[1]
        temperatura = float(payload["temperature"])
        timestamp = datetime.strptime(payload["timestamp"], "%Y-%m-%d %H:%M:%S")
        new_temperature = Temperature(
            id_sensor=id_sensor, temperatura=temperatura, timestamp=timestamp
        )
        db.session.add(new_temperature)
        db.session.commit()
        print(f"Temperature {temperatura} for sensor {id_sensor} saved.")
    except Exception as e:
        print(f"Error saving temperature data: {e}")


# Initialize MQTT client
client = mqtt.Client("FlaskMQTTSubscriber")
client.on_connect = on_connect
client.on_message = on_message


# Function to handle MQTT connection with retry logic
def connect_to_mqtt():
    while True:
        try:
            client.connect(broker_hostname, port)
            client.loop_start()
            break  # Exit the loop once connected
        except (socket.gaierror, ConnectionRefusedError):
            print(
                f"Failed to connect to MQTT Broker at {broker_hostname}:{port}, retrying in {reconnect_delay} seconds..."
            )
            time.sleep(reconnect_delay)


# Call the connect_to_mqtt function to ensure MQTT connection is established
connect_to_mqtt()

# REST API for CRUD operations on Temperature


# POST endpoint to create a new temperature record
@app.route("/temperatures", methods=["POST"])
def create_temperature():
    try:
        data = request.get_json()
        new_temperature = Temperature(
            id_sensor=data["id_sensor"],
            temperatura=data["temperatura"],
            timestamp=datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S"),
        )
        db.session.add(new_temperature)
        db.session.commit()
        return make_response(jsonify({"message": "Temperature data created"}), 201)
    except Exception as e:
        return make_response(
            jsonify({"message": "Error creating temperature data", "error": str(e)}),
            500,
        )


# GET endpoint to retrieve temperature records
@app.route("/temperatures", methods=["GET"])
def get_temperatures():
    try:
        temperatures = Temperature.query.all()
        return make_response(jsonify([temp.json() for temp in temperatures]), 200)
    except Exception as e:
        return make_response(
            jsonify({"message": "Error getting temperatures", "error": str(e)}), 500
        )


# PUT endpoint to update an existing temperature record
@app.route("/temperatures/<int:id>", methods=["PUT"])
def update_temperature(id):
    try:
        temperature = Temperature.query.get(id)
        if temperature:
            data = request.get_json()
            temperature.id_sensor = data.get("id_sensor", temperature.id_sensor)
            temperature.temperatura = data.get("temperatura", temperature.temperatura)
            temperature.timestamp = data.get("timestamp", temperature.timestamp)
            db.session.commit()
            return make_response(jsonify({"message": "Temperature data updated"}), 200)
        else:
            return make_response(
                jsonify({"message": "Temperature data not found"}), 404
            )
    except Exception as e:
        return make_response(
            jsonify({"message": "Error updating temperature data", "error": str(e)}),
            500,
        )


# DELETE endpoint to delete a temperature record
@app.route("/temperatures/<int:id>", methods=["DELETE"])
def delete_temperature(id):
    try:
        temperature = Temperature.query.get(id)
        if temperature:
            db.session.delete(temperature)
            db.session.commit()
            return make_response(jsonify({"message": "Temperature data deleted"}), 200)
        else:
            return make_response(
                jsonify({"message": "Temperature data not found"}), 404
            )
    except Exception as e:
        return make_response(
            jsonify({"message": "Error deleting temperature data", "error": str(e)}),
            500,
        )


# Start the Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=4000)
