import os

class KafkaConfig:
    """Configuration des topics et brokers Kafka"""
    
    #  Kafka server address
    BOOTSTRAP_SERVERS = f'{os.getenv("KAFKA_INTERNAL_HOST")}:{os.getenv("KAFKA_INTERNAL_PORT")}' if os.getenv("USE_DOCKER") == 'true' else f'{os.getenv("KAFKA_LOOPBACK_HOST")}:{os.getenv("KAFKA_LOOPBACK_PORT")}'

    # Topics
    TOPIC_SCAN_STARTED       = "topic-scan-started"
    TOPIC_REPOSITORY_CLONED  = "topic-repository-cloned"
    TOPIC_REPOSITORY_SCANNED = "topic-repository-scanned"
    TOPIC_DEPENDENCIES_QUERIED = "topic-dependencies-queried"
    TOPIC_MANIFEST_FILES_EDITED = "topic-manifest-files-edited"
    TOPIC_SCAN_COMPLETED = "topic-scan-completed"

    # Consumer Groups
    CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE = "consumer-group-repository-storage-service"
    CONSUMER_GROUP_REPOSITORY_SCANNER_SERVICE = "consumer-group-repository-scanner-service"
    CONSUMER_GROUP_SECURITY_ANALYZER_SERVICE = "consumer-group-security-analyzer-service"
    CONSUMER_GROUP_REGISTRY_SERVICE = "consumer-group-registry-service"
    CONSUMER_GROUP_SECURITY_INTELLIGENCE_SERVICE = "consumer-group-security-intelligence-service"

    PRODUCER_CONFIG = {
        "acks": "all",                  # attendre la confirmation de tous les replicas
        "enable_idempotence": True,     # évite les doublons en cas de retry interne réseau
        # Note: compression is not needed in development
        # but if you want to enable it, you need to install the required library (e.g., `python-snappy` for Snappy compression).
        # "compression_type": "snappy",   # compresse les messages
    }

    CONSUMER_CONFIG = {
        "auto_offset_reset": "earliest",                  # Commencer au début
        "enable_auto_commit": False,                      # Commit manuel (contrôle)
        "max_poll_records": 10,                           # 10 messages max par poll
    }