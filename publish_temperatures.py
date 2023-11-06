import paho.mqtt.client as mqtt
from datetime import datetime
import time
import json
import math
import random
import os

broker_hostname = "localhost"
port = 1883

client = mqtt.Client("TemperaturePublisher")
client.connect(broker_hostname, port)
client.loop_start()

# Store the last temperature for each sensor
last_temperatures = {}


def generate_temperature(hour, sensor_tag):
    """Generates a temperature value that follows a pattern based on the hour of the day."""
    # Define the base temperature and amplitude of fluctuation
    base_temp = 20  # Base temperature to fluctuate around
    amplitude = 3  # Max fluctuation for temperature, +/- around the base

    # Create a sinusoidal fluctuation based on the hour of the day
    temp_fluctuation = amplitude * math.sin((math.pi / 12) * (hour - 12))

    # Introduce some randomness for each sensor
    sensor_variation = random.uniform(-1, 1)
    temperature = base_temp + temp_fluctuation + sensor_variation

    # Ensure that the temperature change is not too abrupt compared to the last value for the same sensor
    last_temperature = last_temperatures.get(sensor_tag, base_temp)
    if abs(temperature - last_temperature) > 2:
        temperature = last_temperature + (2 if temperature > last_temperature else -2)

    # Round to 2 decimal places and update the last known temperature
    temperature = round(temperature, 2)
    last_temperatures[sensor_tag] = temperature

    return temperature


try:
    while True:
        current_hour = datetime.now().hour
        # Asignamos los nombres de los edificios y áreas de acuerdo a la imagen de ejemplo
        sensor_locations = {
            1: {"building_name": "storage_building", "area_name": "storage"},
            2: {"building_name": "production_building", "area_name": "production_hall"},
            3: {"building_name": "production_building", "area_name": "production_hall"},
            4: {"building_name": "production_building", "area_name": "storage"},
        }

        for sensor_number in range(1, 5):  # Asumiendo sensores ID 1 a 4
            temperature = generate_temperature(current_hour, sensor_number)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sensor_tag = f"temp_{sensor_number}"
            payload = json.dumps(
                {
                    "sensor_tag": sensor_tag,
                    "temperature": temperature,
                    "timestamp": timestamp,
                }
            )
            location = sensor_locations[sensor_number]
            topic = f"building/{location['building_name']}/area/{location['area_name']}/sensor/{sensor_tag}/temperature"
            result = client.publish(topic, payload)
            status = result[0]
            if status == 0:
                print(
                    f"Sensor {sensor_tag}: Temperature {temperature} at {timestamp} published to topic '{topic}'"
                )
            else:
                print(f"Failed to send message to topic '{topic}'")
        time.sleep(60)  # Wait a minute before sending the next set of temperatures
finally:
    client.disconnect()
    client.loop_stop()
