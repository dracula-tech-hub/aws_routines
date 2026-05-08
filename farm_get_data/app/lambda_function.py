"""
Handles all GET requests coming from the farms
"""

import json
import logging
from decimal import Decimal
from typing import Tuple, List, Any

from rds_db_client import RdsDbClient


class DbClient(RdsDbClient):

    def get_storage_units_detail(self, robot_id: int) -> Tuple[int, str]:
        """
        Gets info about all storage units in the site where the robot is.

        Returns:
            (http_status_code, json_stringified_data)
        """

        # Get storage site ID for the robot
        query = """
            SELECT site.id
            FROM app_robot AS robot
            JOIN app_storageunit AS unit
                ON robot.storage_unit_id = unit.id
            JOIN app_storagesite AS site
                ON unit.storage_hub_id = site.id
            WHERE robot.id = %(robot_id)s
        """

        result = self._select_query(query, {"robot_id": robot_id})

        if not result:
            logging.error("Storage site not found for robot_id=%s", robot_id)
            return 400, json.dumps("Storage site not found")

        storage_site_id = result[0][0]

        # Get all storage units in the site
        query = """
            SELECT
                unit.id,
                unit.name,
                storage_type.name,
                grain.name,
                unit.height,
                unit.length,
                unit.width
            FROM app_storageunit AS unit
            JOIN app_storagetype AS storage_type
                ON unit.storage_type_id = storage_type.id
            JOIN app_graintype AS grain
                ON unit.grain_type_id = grain.id
            WHERE unit.storage_hub_id = %(storage_site_id)s
        """

        result = self._select_query(
            query,
            {"storage_site_id": storage_site_id},
        )

        if not result:
            logging.error(
                "No storage units found for storage_site_id=%s",
                storage_site_id,
            )
            return 400, json.dumps("Storage units not found")

        site_details: List[List[Any]] = [
            [
                float(field) if isinstance(field, Decimal) else field
                for field in unit
            ]
            for unit in result
        ]

        return 200, json.dumps(site_details)

    def get_robot_id(self, serial_number: str) -> Tuple[bool, str]:
        """
        Returns the ID of the robot given its serial number.

        Returns:
            (success, robot_id)
        """

        query = """
            SELECT id
            FROM app_robot
            WHERE serial_number = %(serial_number)s
        """

        result = self._select_query(
            query,
            {"serial_number": serial_number},
        )

        if not result:
            logging.error("Robot with serial_number=%s not found", serial_number)
            return False, ""

        logging.info("Found robot with serial_number=%s", serial_number)

        return True, result[0][0]


def lambda_handler(event, context):
    logging.info("Starting lambda")

    request_params = event.get("queryStringParameters")

    if not request_params:
        return {
            "statusCode": 400,
            "body": json.dumps("No input data"),
        }

    serial_number = request_params.get("serial_number")
    request_type = request_params.get("request_type")

    if not serial_number or not request_type:
        return {
            "statusCode": 400,
            "body": json.dumps("Invalid request"),
        }

    # Connect to database
    db_client = DbClient()

    if not db_client.is_connected:
        return {
            "statusCode": 503,
            "body": json.dumps("Connection with DB failed"),
        }

    # Get robot ID
    success, robot_id = db_client.get_robot_id(serial_number)

    if not success:
        return {
            "statusCode": 400,
            "body": json.dumps("Invalid request"),
        }

    # Handle request types
    request_handlers = {
        "storage_units": db_client.get_storage_units_detail,
    }

    handler = request_handlers.get(request_type)

    if not handler:
        return {
            "statusCode": 400,
            "body": json.dumps("Invalid request"),
        }

    status_code, body = handler(robot_id)

    return {
        "statusCode": status_code,
        "body": body,
    }