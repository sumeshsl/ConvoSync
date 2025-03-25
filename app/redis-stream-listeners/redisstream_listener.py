import redis
import logging, json, os
import time,httpx,traceback, threading
from fastapi import HTTPException


# Redis connection details from environment variables with defaults
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
#REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_STREAM_NAME = os.environ.get('REDIS_STREAM_NAME', 'preprocess_request')
CONSUMER_GROUP = os.environ.get('CONSUMER_GROUP', 'post-processing-grp')
CONSUMER_NAME = os.environ.get('CONSUMER_NAME', 'preprocess_request')
BLOCK_MS = int(os.environ.get('BLOCK_MS', 5000))  # Time to block waiting for new messages



# Define backend microservices URLs
POSTPROCESSING_API_URL = os.environ.get("POSTPROCESSING_URL")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def connect_to_redis():
    """Establish a connection to Redis server with retry logic"""
    max_retries = 5
    retry_count = 0
    backoff_factor = 1.5

    while retry_count < max_retries:
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                decode_responses=True  # Automatically decode response bytes to strings
            )
            # Test the connection
            redis_client.ping()
            logger.info(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return redis_client
        except redis.ConnectionError as e:
            retry_count += 1
            wait_time = backoff_factor ** retry_count
            logger.error(f"Failed to connect to Redis: {e}")
            logger.info(f"Retrying in {wait_time:.1f} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(wait_time)

    raise Exception(f"Could not connect to Redis after {max_retries} attempts")

def setup_consumer_group(redis_client, stream, group):
    """Create consumer group if it doesn't exist"""
    try:
        redis_client.xgroup_create(REDIS_STREAM_NAME, CONSUMER_GROUP, id='0', mkstream=True)
        logger.info(f"Created consumer group '{group}' for stream '{stream}'")
    except redis.ResponseError as e:
        if 'BUSYGROUP' in str(e):
            logger.info(f"Consumer group '{group}' already exists for stream '{stream}'")
        else:
            raise



def redis_polling():
    """Main function to poll Redis stream continuously"""
    redis_client = connect_to_redis()
    setup_consumer_group(redis_client, REDIS_STREAM_NAME, CONSUMER_GROUP)

    # Track last processed ID for recovery
    last_id = '0'  # Start from the beginning
    while True:
        try:
            logger.debug(f"Starting to listen for messages on stream '{REDIS_STREAM_NAME}'")
            messages = redis_client.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={REDIS_STREAM_NAME: '>'},  # Read new messages
                count=10,
                block=5000  # Blocks for 5 sec if no messages are available
            )

            if messages:
                for stream, entries in messages:
                    for entry_id, data in entries:
                        logger.info(f"Processing message {entry_id}: {data}")
                        # Forwarding the request to post procecessing server
                        """Main function that processes data and forwards it in a separate thread."""
                        thread = threading.Thread(target=forward_request, args=(data,))
                        thread.start()
                        # Acknowledge the message after processing
                        redis_client.xack(REDIS_STREAM_NAME, CONSUMER_GROUP, entry_id)
            else:
                logger.debug("No new messages. Polling again...")

            time.sleep(1)
        except Exception as e:
            print(f"Error in Redis polling: {e}")
            time.sleep(5)  # Wait before retrying

def forward_request(ai_query_response):
    logger.info("Forwarding request")
    with httpx.Client() as client:  # Use synchronous `httpx.Client()` instead of `asyncClient`
        try:
            # Ensure `result` is correctly parsed as a dictionary
            if isinstance(ai_query_response["result"], str):
                try:
                    ai_query_response["result"] = json.loads(ai_query_response["result"].replace("'", '"'))
                except json.JSONDecodeError as e:
                    logger.error(f"JSON Decode Error: {str(e)} - Raw Data: {ai_query_response['result']}")
                    ai_query_response["result"] = {"error": "Invalid result format"}

            # Convert `id` to an integer if it's a valid number
            if "id" in ai_query_response and isinstance(ai_query_response["id"], str) and ai_query_response[
                "id"].isdigit():
                ai_query_response["id"] = int(ai_query_response["id"])
            logger.info(f"Formatted Data Before Sending: {ai_query_response}")

            response = client.post(POSTPROCESSING_API_URL, json=ai_query_response)
            if response.status_code != 200:
                raise HTTPException(status_code=500,
                                    detail=f"Failed to send AIQueryResponse to external API: {response.text}")

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP Error: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(status_code=http_err.response.status_code,
                                detail=f"External API Error: {http_err.response.text}")

        except httpx.RequestError as req_err:
            logger.error(f"Request Error: {str(req_err)}")
            raise HTTPException(status_code=500,
                                detail=f"Failed to send request to postprocessing API: {str(req_err)}")

        except ValueError:
            raise HTTPException(status_code=500,
                                detail=f"Invalid JSON received from postprocessing API: {response.text}")

        except Exception as e:
            error_type = type(e).__name__  # Get the exception type
            error_details = traceback.format_exc()  # Get full traceback
            logger.error(f"Exception Type: {error_type}\nDetails: {error_details}")
            raise HTTPException(status_code=500, detail=f"Unexpected error ({error_type}): {str(e)}")

# Keep the main thread alive
try:
    redis_polling()
except KeyboardInterrupt:
    print("Shutting down...")
