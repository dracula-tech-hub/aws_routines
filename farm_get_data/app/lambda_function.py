"""
Handles all GET requests coming from the farms
"""

import json
import logging
from decimal import Decimal
from typing import Tuple

from rds_db_client import RdsDbClient


class DbClient(RdsDbClient):
    def get_storage_units_detail(self, robot_id) -> Tuple[int, str]:
        """
        Gets info about all storage units in the site the robot is

        Returns: (http_status_code, json_stringified_data)
        """
        # Get the id of the storage site in which the robot is
        result = self._select_query(
            "SELECT site.id"
            + " FROM app_storagesite AS site"
            + " JOIN app_storageunit AS unit ON unit.storage_hub_id = site.id"
            + " JOIN app_robot AS robot ON robot.storage_unit_id = unit.id"
            + " WHERE robot.id = %(robot_id)s",
            {"robot_id": robot_id},
        )

        if not result:
            logging.error(f"Couldn't find storage site for robot with id: {robot_id}")
            return 400, json.dumps("Storage site not found")

        print(result)

        storage_site_id = result[0][0]

        # Get details of all units in this site
        result = self._select_query(
            "SELECT unit.id, unit.name, app_storagetype.name, grain.name,"
            + " unit.height, unit.length, unit.width"
            + " FROM app_storageunit AS unit"
            + " JOIN app_storagetype ON unit.storage_type_id = app_storagetype.id"
            + " JOIN app_graintype AS grain ON unit.grain_type_id = grain.id"
            + " WHERE unit.id IN ("
            + "   SELECT unit.id"
            + "   FROM app_storageunit as unit"
            + "   JOIN app_storagesite as site ON site.id = unit.storage_hub_id"
            + "   WHERE site.id = %(storage_site_id)s"
            + " )",
            {"storage_site_id": storage_site_id},
        )

        if not result:
            logging.error(f"Couldn't find storage units in site: {storage_site_id}")
            return 400, json.dumps("Storage units not found")

        print(result)

        site_details = []

        for unit in result:
            details = []

            for detail in unit:
                if isinstance(detail, Decimal):
                    field = float(detail)
                else:
                    field = detail
                details.append(field)

            site_details.append(details)

        print(site_details)

        return 200, json.dumps(site_details)

    def get_robot_id(self, serial_number: str) -> Tuple[bool, str]:
        """
        Returns the ID of the robot, given its serial number

        Returns: (success, robot_id)
        """
        result = self._select_query(
            "SELECT id FROM app_robot WHERE serial_number = %(serial_number)s",
            {"serial_number": serial_number},
        )

        if not result or result == []:
            logging.error(f"Robot {serial_number} doesn't exist")
            return (False, "")
        else:
            print(f"Found robot {serial_number}")
            return (True, result[0][0])


def lambda_handler(event, context):
    print("Starting the lambda")

    if "queryStringParameters" not in event or event["queryStringParameters"] is None:
        return {
            "statusCode": 400,
            "body": json.dumps("No input data"),
        }

    request_params = event["queryStringParameters"]

    # Connect to the database
    db_client = DbClient()

    if not db_client.is_connected:
        return {
            "statusCode": 503,
            "body": json.dumps("Connection with DB failed"),
        }

    # Retrieve the robot id
    if "serial_number" not in request_params:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}

    [success, robot_id] = db_client.get_robot_id(request_params["serial_number"])

    if not success:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}

    # Handle GET requests
    if "request_type" not in request_params:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}

    if request_params["request_type"] == "storage_units":
        status_code, body = db_client.get_storage_units_detail(robot_id)
        return {"statusCode": status_code, "body": body}
    else:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}
