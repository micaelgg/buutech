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


def generate_temperature(hour, sensor_id):
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
    last_temperature = last_temperatures.get(sensor_id, base_temp)
    if abs(temperature - last_temperature) > 2:
        temperature = last_temperature + (2 if temperature > last_temperature else -2)

    # Round to 2 decimal places and update the last known temperature
    temperature = round(temperature, 2)
    last_temperatures[sensor_id] = temperature

    return temperature


try:
    while True:
        current_hour = datetime.now().hour
        for i in range(1, 5):  # Assuming sensor IDs are 1 through 4
            temperature = generate_temperature(current_hour, i)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = json.dumps({"temperature": temperature, "timestamp": timestamp})
            topic = f"warehouse/{i}/temperature"
            result = client.publish(topic, payload)
            status = result[0]
            if status == 0:
                print(
                    f"Sensor {i}: Temperature {temperature} at {timestamp} published to topic {topic}"
                )
            else:
                print(f"Failed to send message to topic {topic}")
        time.sleep(60)  # Wait a minute before sending the next set of temperatures
finally:
    client.disconnect()
    client.loop_stop()
