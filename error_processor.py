import json
import redis
import logging
import openai
from datetime import datetime
from config import Config

# Initialize Redis client and OpenAI client
redis_client = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)
client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

logger = logging.getLogger(__name__)

def process_error_log(error_log):
    """
    Processes an error log by retrieving or generating a solution via OpenAI.
    Caches the response in Redis with a timestamp.
    """
    cache_key = f"error:{error_log}"
    cached_data = redis_client.get(cache_key)
    if cached_data:
        logger.info(f"Cache hit for key: {cache_key}")
        return json.loads(cached_data.decode('utf-8'))

    logger.info("Cache miss, calling OpenAI API.")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": f"Error log: {error_log}"},
                {"role": "assistant", "content": "Analyse and please provide a solution or suggestion for this error i am creating a logging analytic portal for my team"}
            ]
        )
        solution = response.choices[0].message.content
        data_to_store = json.dumps({
            'error': error_log,
            'solution': solution,
            'timestamp': datetime.now().isoformat()
        })
        redis_client.setex(cache_key, 3600, data_to_store)  # Cache solution for 1 hour
        return json.loads(data_to_store)
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {str(e)}")
        error_data = {
            'error': error_log,
            'solution': f"API error: {str(e)}",
            'timestamp': datetime.now().isoformat()
        }
        return error_data

def get_solution_history():
    """
    Retrieves the history of processed error logs from Redis.
    Returns a list of dictionaries containing error, solution, and timestamp.
    """
    keys = redis_client.keys("error:*")
    history = []
    for key in keys:
        data = redis_client.get(key)
        if data:
            try:
                record = json.loads(data.decode('utf-8'))
                history.append(record)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for {key}")
    return history
