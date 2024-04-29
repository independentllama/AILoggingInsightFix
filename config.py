class Config:
    # OpenAI API Key
    OPENAI_API_KEY = opeapikey

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = '123'
    KAFKA_TOPIC_NAME = 'logging'
    KAFKA_GROUP_ID = 'error-logs-group'
    KAFKA_USERNAME =  username
    KAFKA_PASSWORD =  password

    # Redis Configuration
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
