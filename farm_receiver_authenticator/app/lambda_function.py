"""
Lambda to check authentication of all incoming/outgoing AWS communications
"""

import json
import logging
from typing import Dict, Any

from rds_db_client import RdsDbClient


class DatabaseClient(RdsDbClient):
    """
    Database client for robot authentication.
    """

    def validate_robot(
        self,
        serial_number: str,
        identifier: str,
    ) -> bool:
        """
        Validates:
        - robot exists
        - identifier matches
        - robot is activated
        """

        query = """
            SELECT identifier, activated
            FROM app_robot
            WHERE serial_number = %(serial_number)s
        """

        result = self._select_query(
            query,
            {"serial_number": serial_number},
        )

        if not result:
            logging.error(
                "Robot with serial_number=%s does not exist",
                serial_number,
            )
            return False

        db_identifier, activated = result[0]

        if db_identifier != identifier:
            logging.error(
                "Invalid identifier for robot=%s",
                serial_number,
            )
            return False

        if not activated:
            logging.error(
                "Robot=%s is not activated",
                serial_number,
            )
            return False

        logging.info(
            "Robot=%s authenticated successfully",
            serial_number,
        )

        return True


def generate_policy(effect: str, resource: str) -> Dict[str, Any]:
    """
    Generates IAM policy response.
    """

    return {
        "principalId": "user",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }


def lambda_handler(event, context):
    logging.info("Starting authentication lambda")

    parameters = event.get("queryStringParameters") or {}

    serial_number = parameters.get("serial_number")
    identifier = parameters.get("identifier")

    if not serial_number or not identifier:
        logging.error("Missing authentication parameters")

        return {
            "statusCode": 400,
            "body": json.dumps("Missing authentication parameters"),
        }

    logging.info("Authenticating robot=%s", serial_number)

    db_client = DatabaseClient()

    if not db_client.is_connected:
        logging.error("Database connection failed")

        return {
            "statusCode": 503,
            "body": json.dumps("Database connection failed"),
        }

    is_authorized = db_client.validate_robot(
        serial_number,
        identifier,
    )

    effect = "Allow" if is_authorized else "Deny"

    return generate_policy(
        effect=effect,
        resource=event["methodArn"],
    )