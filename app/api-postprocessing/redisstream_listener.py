import redis
import threading
import time
from rediscache import redis_client


# Stream and Consumer Group details
STREAM_NAME = 'preprocess_request'
GROUP_NAME = 'post-processing-grp'
CONSUMER_NAME = 'preprocess_request'

# Ensure the group exists
try:
    redis_client.xgroup_create(STREAM_NAME, GROUP_NAME, id='0', mkstream=True)
except redis.exceptions.ResponseError as e:
    if "BUSYGROUP" not in str(e):
        raise  # Ignore error if group already exists


def redis_polling():
    """Continuously polls Redis stream for new messages."""
    while True:
        try:
            messages = redis_client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: '>'},  # Read new messages
                count=10,
                block=5000  # Blocks for 5 sec if no messages are available
            )

            if messages:
                for stream, entries in messages:
                    for entry_id, data in entries:
                        print(f"Processing message {entry_id}: {data}")
                        #TODO: Process messages
                        # Acknowledge the message after processing
                        redis_client.xack(STREAM_NAME, GROUP_NAME, entry_id)
            else:
                print("No new messages. Polling again...")

        except Exception as e:
            print(f"Error in Redis polling: {e}")
            time.sleep(5)  # Wait before retrying

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
