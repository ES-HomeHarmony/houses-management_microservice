import json
import os
import threading
from kafka import KafkaProducer, KafkaConsumer
from app.database import SessionLocal

producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Kafka consumer for receiving responses
consumer = KafkaConsumer(
    'user-validation-response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='houses_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

# Kafka consumer for user creation responses
user_creation_consumer = KafkaConsumer(
    'user-creation-response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='user_creation_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

# Kafka consumer for tenant info responses
tenant_get_info_consumer = KafkaConsumer(
    'tenant_info_response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='tenant_info_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

tenant_id_update_consumer = KafkaConsumer(
    'user-id-update',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='tenant_id_update_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("Kafka consumer initialized and listening...")
print(f"Subscribed topics: {consumer.subscription()}")
print(f"KAFKA_BOOTSTRAP_SERVERS: {os.getenv('KAFKA_BOOTSTRAP_SERVERS')}")

user_cache = {}
user_cache2 = {}
tenant_data_dict = []

# Run the consumer in a separate thread to listen for responses
def start_consumer():
    for message in consumer:
        user_cache["cognito_id"] = message.value.get("cognito_id")
def start_consumer_2():
    for message in user_creation_consumer:
        user_cache2["cognito_id"] = message.value.get("cognito_id")
def start_consumer_3():
    for message in tenant_get_info_consumer:
        tenant_data_dict.append(message.value)
def start_consumer_4():
    from app.routes.tenants_routes import tenant_update_id 
    print("Starting consumer for updating tenant IDs...")
    for message in tenant_id_update_consumer:
        print(message.value)
        with SessionLocal() as db:
            tenant_update_id(
                message.value.get("old_id"),
                message.value.get("new_id"),
                db
            )        
threading.Thread(target=start_consumer, daemon=True).start()
threading.Thread(target=start_consumer_2, daemon=True).start()
threading.Thread(target=start_consumer_3, daemon=True).start()
threading.Thread(target=start_consumer_4, daemon=True).start()