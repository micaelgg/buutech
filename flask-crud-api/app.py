from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
import os
from sqlalchemy.exc import OperationalError
import time
from datetime import datetime
import json
import socket
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
# Configure database URI from environment variable
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URL")
# Initialize SQLAlchemy with the Flask app
db = SQLAlchemy(app)


# Define the Building model
class Building(db.Model):
    __tablename__ = "buildings"
    building_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)

    # Relationship with Area
    areas = db.relationship("Area", backref="building", lazy=True)


# Define the Area model
class Area(db.Model):
    __tablename__ = "areas"
    area_id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(
        db.Integer, db.ForeignKey("buildings.building_id"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationship with Sensor
    sensors = db.relationship("Sensor", backref="area", lazy=True)


# Define the Sensor model
class Sensor(db.Model):
    __tablename__ = "sensors"
    sensor_id = db.Column(db.Integer, primary_key=True)
    area_id = db.Column(db.Integer, db.ForeignKey("areas.area_id"), nullable=False)
    sensor_tag = db.Column(db.String(255), unique=True, nullable=False)
    sensor_type = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)

    # Relationship with TemperatureRecord
    temperature_records = db.relationship(
        "TemperatureRecord", backref="sensor", lazy=True
    )


# Define the TemperatureRecord model
class TemperatureRecord(db.Model):
    __tablename__ = "temperature_records"
    record_id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(
        db.Integer, db.ForeignKey("sensors.sensor_id"), nullable=False
    )
    temperature = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)


# Initialize database creation function
def initialize_database():
    with app.app_context():
        db.create_all()
        seed_data()  # Seed the database after tables creation


def seed_data():
    sensor_locations = {
        1: {"building_name": "storage_building", "area_name": "storage"},
        2: {"building_name": "production_building", "area_name": "production_hall"},
        3: {"building_name": "production_building", "area_name": "production_hall"},
        4: {"building_name": "production_building", "area_name": "storage"},
    }

    # Create dictionaries to keep track of existing buildings and areas
    existing_buildings = {b.name: b for b in Building.query.all()}
    existing_areas = {(a.building_id, a.name): a for a in Area.query.all()}
    existing_sensors = {s.sensor_id: s for s in Sensor.query.all()}

    for sensor_id, location in sensor_locations.items():
        building_name = location["building_name"]
        area_name = location["area_name"]

        # Check and add building if it doesn't exist
        building = existing_buildings.get(building_name)
        if not building:
            building = Building(
                name=building_name, location="Unknown"
            )  # Use appropriate GPS coordinates or 'Unknown'
            db.session.add(building)
            db.session.commit()  # Commit to get the building_id
            existing_buildings[building_name] = building

        # Check and add area if it doesn't exist within the corresponding building
        area = existing_areas.get((building.building_id, area_name))
        if not area:
            area = Area(
                building_id=building.building_id, name=area_name, description="Unknown"
            )  # Provide a proper description
            db.session.add(area)
            db.session.commit()  # Commit to get the area_id
            existing_areas[(building.building_id, area_name)] = area

        # Check if sensor_id already exists to prevent duplicates
        if sensor_id not in existing_sensors:
            # Add sensor with the updated requirements
            sensor = Sensor(
                sensor_id=sensor_id,
                area_id=area.area_id,
                sensor_tag=f"temp_{sensor_id}",
                sensor_type="thermometer",
                location="GPS COORDINATES",  # Replace with actual GPS coordinates
            )
            db.session.add(sensor)

    # Commit all new sensors at once
    db.session.commit()


# Ensure that database tables are created before starting the application
initialize_database()


def get_sensor_id_from_sensor_tag(sensor_tag):
    """
    Retrieve the sensor_id from the Sensor table based on the given sensor_tag.
    """
    with app.app_context():
        sensor = Sensor.query.filter_by(sensor_tag=sensor_tag).first()
        if sensor:
            return sensor.sensor_id
        else:
            logging.info(f"No Sensor found for sensor_tag {sensor_tag}")
            return None


# MQTT Setup
broker_hostname = os.getenv("BROKER_HOSTNAME", "mos1")
port = 1883
reconnect_delay = 10  # Delay between connection attempts in seconds


# Callback when the client receives a CONNACK response from the server
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT Broker!")
        # Subscribe to all sensors in all areas and buildings
        client.subscribe("building/+/area/+/sensor/+/temperature")
    else:
        logging.warning(f"Failed to connect, return code {rc}\n")


# Callback for when a PUBLISH message is received from the server
def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode())
        sensor_tag = payload["sensor_tag"]
        temperature = float(payload["temperature"])
        timestamp = datetime.strptime(payload["timestamp"], "%Y-%m-%d %H:%M:%S")

        sensor_id = get_sensor_id_from_sensor_tag(sensor_tag)
        if sensor_id is None:
            return  # Exit the function if no sensor_id is found

        new_temperature = TemperatureRecord(
            sensor_id=sensor_id,
            temperature=temperature,  # Make sure this matches the model field name
            timestamp=timestamp,
        )

        db.session.add(new_temperature)
        db.session.commit()
        logging.info(
            f"{datetime.now().strftime('%H:%M:%S')} - Temperature {temperature} for sensor {sensor_tag} saved."
        )
    except Exception as e:
        logging.error(f"Error saving temperature data: {e}")


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
            logging.warning(
                f"Failed to connect to MQTT Broker at {broker_hostname}:{port}, retrying in {reconnect_delay} seconds..."
            )
            time.sleep(reconnect_delay)


# Call the connect_to_mqtt function to ensure MQTT connection is established
connect_to_mqtt()

# Start the Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=4000)
