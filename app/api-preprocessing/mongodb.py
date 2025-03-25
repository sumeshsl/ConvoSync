import motor.motor_asyncio
import os
MONGO_URI = os.getenv("MONGO_URI")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
database = client.adaptAiDatabase
queries_collection = database.queries
test_va_context = database.test_va_context


async def get_next_id():
    """Fetch the next sequence number for `id` from MongoDB counters."""

    counter = await queries_collection.database.counters.find_one_and_update(
        {"_id": "query_id"},
        {"$inc": {"seq": 1}},  #  Increment `seq` by 1
        return_document=True,
        upsert=True  #  Create document if it doesn't exist
    )

    if counter is None:  #  If document doesn't exist, create it manually
        await queries_collection.database.counters.insert_one({"_id": "query_id", "seq": 1})
        return 1  #  First ID starts at 1

    return counter["seq"]  # Always return a valid `seq`
