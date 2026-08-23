import json
import logging
from typing import Callable, Optional
from aiokafka import AIOKafkaConsumer

from .config import KafkaConfig

logger = logging.getLogger(__name__)

class EventConsumer:
    """
    Consumer Kafka générique
    """

    # 1. Constructeur
    def __init__(
        self,
        topic: str,                    
        group_id: str,                 
        bootstrap_servers: Optional[str] = None,
        callback: Optional[Callable] = None  
    ):
        self.topic = topic
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or KafkaConfig.BOOTSTRAP_SERVERS
        self.callback = callback
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False

    # 2. Démarrage
    async def start(self):
        """Démarre le consumer"""
        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            **KafkaConfig.CONSUMER_CONFIG
        )
        await self._consumer.start()
        self._running = True
        logger.info(f" Kafka consumer started on {self.topic} (group: {self.group_id})")

    # 3. Arrêt
    async def stop(self):
        """Arrête le consumer"""
        if self._consumer:
            await self._consumer.stop()
            self._running = False
            logger.info(f" Kafka consumer stopped for {self.topic}")

    async def consume(self, callback: Optional[Callable] = None):
        """
        Boucle infinie qui écoute les messages
        
        Args:
            callback: Fonction à appeler pour chaque message reçu
                     Signature: async def callback(key: str, value: dict, msg: ConsumerRecord)
        """
        # Vérification
        if not self._consumer:
            raise RuntimeError("Consumer not started. Call start() first.")
        
        cb = callback or self.callback
        if not cb:
            raise ValueError("No callback provided")
        
        logger.info(f" Listening on {self.topic}")
        
        # Boucle infinie sur les messages
        async for msg in self._consumer:
            try:
                # 4a. Extraire les données
                key = msg.key          
                value = msg.value      

                logger.debug(f"Received message | Partition: {msg.partition} | Offset: {msg.offset}")
                
                # 4b. Appeler la fonction callback
                await cb(key, value, msg)
                
                # 4c. Commiter (valider que le message est traité)
                await self._consumer.commit()
                
            except Exception as e:
                # 4d. En cas d'erreur
                logger.error(f" Error processing message: {e}")
                # Removed 'raise' to prevent silent crash of consumer task