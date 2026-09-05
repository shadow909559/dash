"""AWS Free Tier Integration for DASH.

Provides access to all AWS free forever services:
- DynamoDB: Device states, config storage (25 GB free)
- Lambda: Cloud relay endpoints (1M requests/month free)
- S3: APK distribution, config backup (5 GB free)
- SNS: Push notifications (1M publishes/month free)
- SQS: Message queue (1M requests/month free)
- API Gateway: REST API (1M calls/month free)
- CloudWatch: Monitoring (10 metrics, 10 alarms free)

All services are ALWAYS FREE within monthly limits.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# AWS region for all services
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
DYNAMODB_TABLE_PREFIX = "dash-"
S3_BUCKET_PREFIX = "dash-"
SNS_TOPIC_PREFIX = "dash-"
SQS_QUEUE_PREFIX = "dash-"
LAMBDA_PREFIX = "dash-"


class AWSFreeTier:
    """AWS Free Tier service manager with lazy initialization."""

    def __init__(self):
        self._session = None
        self._dynamodb = None
        self._s3 = None
        self._sns = None
        self._sqs = None
        self._lambda_client = None
        self._apigateway = None
        self._cloudwatch = None
        self._initialized = False

    def _get_session(self):
        """Get or create boto3 session."""
        if self._session is None:
            try:
                import boto3
                self._session = boto3.Session(region_name=AWS_REGION)
            except ImportError:
                logger.warning("boto3 not installed. AWS services unavailable.")
                return None
        return self._session

    def _get_dynamodb(self):
        """Get DynamoDB resource."""
        if self._dynamodb is None:
            session = self._get_session()
            if session:
                self._dynamodb = session.resource("dynamodb")
        return self._dynamodb

    def _get_s3(self):
        """Get S3 client."""
        if self._s3 is None:
            session = self._get_session()
            if session:
                self._s3 = session.client("s3")
        return self._s3

    def _get_sns(self):
        """Get SNS client."""
        if self._sns is None:
            session = self._get_session()
            if session:
                self._sns = session.client("sns")
        return self._sns

    def _get_sqs(self):
        """Get SQS client."""
        if self._sqs is None:
            session = self._get_session()
            if session:
                self._sqs = session.client("sqs")
        return self._sqs

    def _get_lambda(self):
        """Get Lambda client."""
        if self._lambda_client is None:
            session = self._get_session()
            if session:
                self._lambda_client = session.client("lambda")
        return self._lambda_client

    def _get_apigateway(self):
        """Get API Gateway client."""
        if self._apigateway is None:
            session = self._get_session()
            if session:
                self._apigateway = session.client("apigateway")
        return self._apigateway

    def _get_cloudwatch(self):
        """Get CloudWatch client."""
        if self._cloudwatch is None:
            session = self._get_session()
            if session:
                self._cloudwatch = session.client("cloudwatch")
        return self._cloudwatch

    # ── DynamoDB Operations ──────────────────────────────────────

    async def ensure_dynamodb_table(self, table_name: str) -> bool:
        """Create DynamoDB table if it doesn't exist."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return False

        try:
            from boto3.dynamodb.conditions import Key
            existing = await self._list_dynamodb_tables()
            if table_name in existing:
                return True

            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "device_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "device_id", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",  # Free tier: no charges
            )
            table.wait_until_exists()
            logger.info(f"Created DynamoDB table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create DynamoDB table: {e}")
            return False

    async def _list_dynamodb_tables(self) -> List[str]:
        """List all DynamoDB tables."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return []

        try:
            client = dynamodb.meta.client
            response = client.list_tables()
            return response.get("TableNames", [])
        except Exception as e:
            logger.error(f"Failed to list DynamoDB tables: {e}")
            return []

    async def dynamodb_put(self, table_name: str, item: Dict[str, Any]) -> bool:
        """Put an item into DynamoDB."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return False

        try:
            table = dynamodb.Table(table_name)
            table.put_item(Item=item)
            return True
        except Exception as e:
            logger.error(f"DynamoDB put failed: {e}")
            return False

    async def dynamodb_get(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict]:
        """Get an item from DynamoDB."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return None

        try:
            table = dynamodb.Table(table_name)
            response = table.get_item(Key=key)
            return response.get("Item")
        except Exception as e:
            logger.error(f"DynamoDB get failed: {e}")
            return None

    async def dynamodb_update(self, table_name: str, key: Dict[str, Any],
                              updates: Dict[str, Any]) -> bool:
        """Update an item in DynamoDB."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return False

        try:
            table = dynamodb.Table(table_name)
            update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
            expr_names = {f"#{k}": k for k in updates}
            expr_values = {f":{k}": v for k, v in updates.items()}
            table.update_item(
                Key=key,
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            return True
        except Exception as e:
            logger.error(f"DynamoDB update failed: {e}")
            return False

    async def dynamodb_query(self, table_name: str, key_condition: str,
                             expression_values: Dict, expression_names: Dict = None) -> List[Dict]:
        """Query DynamoDB table."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return []

        try:
            table = dynamodb.Table(table_name)
            kwargs = {
                "KeyConditionExpression": key_condition,
                "ExpressionAttributeValues": expression_values,
            }
            if expression_names:
                kwargs["ExpressionAttributeNames"] = expression_names
            response = table.query(**kwargs)
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"DynamoDB query failed: {e}")
            return []

    async def dynamodb_scan(self, table_name: str) -> List[Dict]:
        """Scan entire DynamoDB table."""
        dynamodb = self._get_dynamodb()
        if not dynamodb:
            return []

        try:
            table = dynamodb.Table(table_name)
            response = table.scan()
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"DynamoDB scan failed: {e}")
            return []

    # ── S3 Operations ────────────────────────────────────────────

    async def s3_upload(self, bucket: str, key: str, data: bytes,
                        content_type: str = "application/octet-stream") -> bool:
        """Upload file to S3."""
        s3 = self._get_s3()
        if not s3:
            return False

        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            return True
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return False

    async def s3_download(self, bucket: str, key: str) -> Optional[bytes]:
        """Download file from S3."""
        s3 = self._get_s3()
        if not s3:
            return None

        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except Exception as e:
            logger.error(f"S3 download failed: {e}")
            return None

    async def s3_list(self, bucket: str, prefix: str = "") -> List[str]:
        """List objects in S3 bucket."""
        s3 = self._get_s3()
        if not s3:
            return []

        try:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            return [obj["Key"] for obj in response.get("Contents", [])]
        except Exception as e:
            logger.error(f"S3 list failed: {e}")
            return []

    # ── SNS Operations ───────────────────────────────────────────

    async def sns_publish(self, topic_arn: str, message: str,
                          subject: str = "DASH Notification") -> bool:
        """Publish message to SNS topic."""
        sns = self._get_sns()
        if not sns:
            return False

        try:
            sns.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject=subject,
            )
            return True
        except Exception as e:
            logger.error(f"SNS publish failed: {e}")
            return False

    async def sns_create_topic(self, name: str) -> Optional[str]:
        """Create SNS topic and return ARN."""
        sns = self._get_sns()
        if not sns:
            return None

        try:
            response = sns.create_topic(Name=name)
            return response["TopicArn"]
        except Exception as e:
            logger.error(f"SNS create topic failed: {e}")
            return None

    # ── SQS Operations ───────────────────────────────────────────

    async def sqs_send(self, queue_url: str, message: str) -> bool:
        """Send message to SQS queue."""
        sqs = self._get_sqs()
        if not sqs:
            return False

        try:
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=message,
            )
            return True
        except Exception as e:
            logger.error(f"SQS send failed: {e}")
            return False

    async def sqs_receive(self, queue_url: str, max_messages: int = 1) -> List[Dict]:
        """Receive messages from SQS queue."""
        sqs = self._get_sqs()
        if not sqs:
            return []

        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=5,
            )
            return response.get("Messages", [])
        except Exception as e:
            logger.error(f"SQS receive failed: {e}")
            return []

    # ── CloudWatch Operations ────────────────────────────────────

    async def cloudwatch_put_metric(self, namespace: str, metric_name: str,
                                     value: float, unit: str = "Count") -> bool:
        """Put a custom metric to CloudWatch."""
        cw = self._get_cloudwatch()
        if not cw:
            return False

        try:
            cw.put_metric_data(
                Namespace=namespace,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                        "Timestamp": datetime.now(timezone.utc),
                    }
                ],
            )
            return True
        except Exception as e:
            logger.error(f"CloudWatch metric failed: {e}")
            return False

    async def cloudwatch_create_alarm(self, alarm_name: str, namespace: str,
                                       metric_name: str, threshold: float,
                                       email: str = None) -> bool:
        """Create a CloudWatch alarm."""
        cw = self._get_cloudwatch()
        if not cw:
            return False

        try:
            cw.put_metric_alarm(
                AlarmName=alarm_name,
                Namespace=namespace,
                MetricName=metric_name,
                Statistic="Average",
                Period=300,
                EvaluationPeriods=1,
                Threshold=threshold,
                ComparisonOperator="GreaterThanThreshold",
                AlarmActions=[],
            )
            return True
        except Exception as e:
            logger.error(f"CloudWatch alarm failed: {e}")
            return False


# Singleton instance
_aws_free_tier: Optional[AWSFreeTier] = None


def get_aws_free_tier() -> AWSFreeTier:
    """Get the AWS Free Tier singleton."""
    global _aws_free_tier
    if _aws_free_tier is None:
        _aws_free_tier = AWSFreeTier()
    return _aws_free_tier
