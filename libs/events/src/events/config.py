import os

class KafkaConfig:
    """Configuration des topics et brokers Kafka"""
    
    #  Adresse du serveur Kafka
    BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    #  Topics définis dans l'architecture
    TOPIC_SCAN_REQUESTED = "repository.scan.requested"
    TOPIC_LLM_REQUESTS = "llm.requests"
    TOPIC_SCAN_COMPLETED = "repository.scan.completed"
    TOPIC_SCAN_FAILED = "repository.scan.failed"
    
    #  Consumer Groups
    CONSUMER_GROUP_SCANNER = "repository-scanner-group"
    CONSUMER_GROUP_LLM = "llm-service-group"
    CONSUMER_GROUP_GATEWAY = "gateway-group"
    
    PRODUCER_CONFIG = {
    "acks": "all",                  # attendre la confirmation de tous les replicas
    "enable_idempotence": True,     # évite les doublons en cas de retry interne réseau
    "compression_type": "snappy",   # compresse les messages
    }
    
    #  Configuration Consumer
    CONSUMER_CONFIG = {
        "auto_offset_reset": "earliest",                  # Commencer au début
        "enable_auto_commit": False,                      # Commit manuel (contrôle)
        "max_poll_records": 10,                           # 10 messages max par poll
    }