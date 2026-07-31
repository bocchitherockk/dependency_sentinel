# --- Imports ---
import json                          # Convertir dictionnaire → JSON
import logging                       # Journalisation
from typing import Any, Optional     # Types (Any = n'importe quel type, Optional = peut être None)
from aiokafka import AIOKafkaProducer  # Client Kafka asynchrone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type  # Retry automatique
from datetime import datetime        # Horodatage

from .config import KafkaConfig      # Notre configuration

# --- Logger ---
logger = logging.getLogger(__name__)  # Crée un logger nommé "events.producer"

# --- Classe ---
class EventProducer:
    """
    Producer Kafka générique avec retry et logging
    """
    
    # 1. Constructeur
    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or KafkaConfig.BOOTSTRAP_SERVERS
        self._producer: Optional[AIOKafkaProducer] = None  
        self._started = False  
    
    # 2. Démarrage
    async def start(self):
        """Démarre le producer (connexion à Kafka)"""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                **KafkaConfig.PRODUCER_CONFIG  
            )
            await self._producer.start() 
            self._started = True
            logger.info(f" Kafka producer started on {self.bootstrap_servers}")
    
    # 3. Arrêt
    async def stop(self):
        """Arrête le producer (ferme la connexion)"""
        if self._producer and self._started:
            await self._producer.stop()
            self._started = False
            logger.info(" Kafka producer stopped")
    
    @retry( 
        stop=stop_after_attempt(3),          
        wait=wait_exponential(multiplier=1, min=1, max=10),  
        retry=retry_if_exception_type(Exception),  
        reraise=True  
    )
    async def publish(self, topic: str, event: dict[str, Any], key: Optional[str] = None):
        """
        Publie un événement sur un topic
        
        Args:
            topic: Nom du topic (ex: "repository.scan.requested")
            event: Dictionnaire avec les données
            key: Clé pour le partitionnement (ex: nom du repository)
        """
        try:
            if "timestamp" not in event:
                event["timestamp"] = datetime.utcnow().isoformat()
            
            # 4b. Envoie le message
            result = await self._producer.send(topic, value=event, key=key)
            metadata = await result  
            
            # 4c. Log du succès
            logger.info(
                f" Event published | Topic: {topic} | "
                f"Key: {key} | Partition: {metadata.partition} | Offset: {metadata.offset}"
            )
            return metadata
            
        except Exception as e:
            # 4d. Log de l'erreur
            logger.error(f" Failed to publish to {topic}: {e}")
            raise 