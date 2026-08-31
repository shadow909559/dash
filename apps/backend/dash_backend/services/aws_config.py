"""AWS Configuration for DASH.

Reads configuration from DynamoDB and SSM Parameter Store.
All services are ALWAYS FREE within monthly limits.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Region
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Resource names (free tier, all ALWAYS FREE)
DYNAMODB_DEVICE_STATES = "dash-device-states"
DYNAMODB_CONFIG = "dash-config"
DYNAMODB_SYNC_LOG = "dash-sync-log"
S3_BUCKET = "dash-storage-752651103716"
SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:752651103716:dash-notifications"
SQS_COMMANDS_URL = "https://sqs.ap-south-1.amazonaws.com/752651103716/dash-commands"
SQS_NOTIFICATIONS_URL = "https://sqs.ap-south-1.amazonaws.com/752651103716/dash-notifications-queue"
CLOUDTRAIL_ARN = "arn:aws:cloudtrail:ap-south-1:752651103716:trail/dash-audit-trail"

# EC2
EC2_INSTANCE_ID = os.getenv("EC2_INSTANCE_ID", "i-0546d2c1b0c7346a5")
EC2_REGION = os.getenv("EC2_REGION", "ap-south-1")
CLOUD_BACKEND_URL = os.getenv("CLOUD_BACKEND_URL", "http://15.206.185.189:8001")

# Local backend
LOCAL_BACKEND_URL = os.getenv("LOCAL_BACKEND_URL", "http://127.0.0.1:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Supabase (cloud relay)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


class AWSConfig:
    """AWS configuration manager. Reads from DynamoDB and falls back to defaults."""

    def __init__(self):
        self._dynamodb = None
        self._config_cache: Dict[str, str] = {}
        self._initialized = False

    def _get_dynamodb(self):
        if self._dynamodb is None:
            try:
                import boto3
                self._dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            except ImportError:
                logger.warning("boto3 not installed")
                return None
        return self._dynamodb

    async def initialize(self):
        """Load config from DynamoDB into cache."""
        if self._initialized:
            return

        dynamodb = self._get_dynamodb()
        if not dynamodb:
            self._initialized = True
            return

        try:
            table = dynamodb.Table(DYNAMODB_CONFIG)
            resp = table.scan()
            for item in resp.get("Items", []):
                self._config_cache[item["key"]] = item["value"]
            logger.info(f"Loaded {len(self._config_cache)} config entries from DynamoDB")
        except Exception as e:
            logger.warning(f"Failed to load config from DynamoDB: {e}")

        self._initialized = True

    async def get(self, key: str, default: str = "") -> str:
        """Get a config value."""
        await self.initialize()
        return self._config_cache.get(key, default)

    async def set(self, key: str, value: str, description: str = ""):
        """Set a config value in DynamoDB."""
        await self.initialize()
        self._config_cache[key] = value

        dynamodb = self._get_dynamodb()
        if dynamodb:
            try:
                table = dynamodb.Table(DYNAMODB_CONFIG)
                table.put_item(Item={
                    "key": key,
                    "value": value,
                    "description": description,
                })
            except Exception as e:
                logger.error(f"Failed to write config: {e}")


# Singleton
_aws_config: Optional[AWSConfig] = None


def get_aws_config() -> AWSConfig:
    global _aws_config
    if _aws_config is None:
        _aws_config = AWSConfig()
    return _aws_config
