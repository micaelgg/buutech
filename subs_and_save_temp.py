import paho.mqtt.client as mqtt

broker_hostname = "localhost"
port = 1883

def on_connect(client, userdata, flags, return_code):
    if return_code == 0:
        print("connected")
        # Subscribe to the temperature topics for all warehouses
        for i in range(4):
            client.subscribe(f"warehouse/{i + 1}/temperature")
    else:
        print("could not connect, return code:", return_code)

def on_message(client, userdata, message):
    warehouse_id = message.topic.split('/')[1]
    temperature = message.payload.decode('utf-8')
    
    # Display the received message
    print(f"Received temperature for Warehouse {warehouse_id}: {temperature}°C")
    
    # Save the temperature to a .txt file
    with open(f"warehouse_{warehouse_id}_temperature.txt", "a") as file:
        file.write(f"{temperature}\n")

client = mqtt.Client("TemperatureSubscriber")
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker_hostname, port)
client.loop_forever()
