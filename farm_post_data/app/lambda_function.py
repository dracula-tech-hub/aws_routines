"""
Handles all POST requests coming from the farms
"""

import json
import logging
from base64 import b64decode
from datetime import datetime, timezone

from msgpack import unpackb
from typing import Tuple
from rds_db_client import RdsDbClient


class DbClient(RdsDbClient):
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

    def get_storage_unit_id(self, robot_id) -> Tuple[bool, str]:
        """
        Returns the storage unit ID in which the robot currently is

        Returns: (success, robot_id)
        """
        unit_query_result = self._select_query(
            "SELECT unit.id"
            + " FROM app_storageunit AS unit"
            + " JOIN app_robot AS robot ON robot.storage_unit_id = unit.id"
            + " WHERE robot.id = %(robot_id)s",
            {"robot_id": robot_id},
        )

        if not unit_query_result:
            logging.error(f"Couldn't find storage unit for robot with id: {robot_id}")
            return (False, "")

        return (True, unit_query_result[0][0])

    def get_storage_site_id(self, robot_id) -> Tuple[bool, int]:
        """
        Gets the storage site id in which the robot currently is

        Returns: (success, storage_site_id)
        """
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
            return False, 0

        return True, result[0][0]

    def update_heartbeat(self, robot_id, data) -> Tuple[int, str]:
        """
        Updates the heartbeat status of a robot
        FIXME: this needs to be updated and tested

        Returns: (http_status_code, message)
        """
        # Convert connection status number to a representative string
        robot_status = "Not Connected"

        if data["robot_status"] == 1:
            robot_status = "Active"
        elif data["robot_status"] == 2:
            robot_status = "Warning"
        elif data["robot_status"] == 3:
            robot_status = "Error"

        status_time = datetime.fromtimestamp(data["stamp"]["secs"], timezone.utc)

        print(
            f"Robot {data['serial_number']} from {data['farm_name']}"
            + f"is {robot_status} at {status_time.ctime()}"
        )

        query = (
            "UPDATE app_robot SET status = %(status)s, status_timestamp = %(time)s"
            " WHERE id = %(id)s"
        )
        query_data = {
            "status": robot_status,
            "time": status_time,
            "id": robot_id,
        }
        print("DB query: {}".format(query % query_data))

        if self.user_query(query, query_data):
            print("Heartbeat added to database")
            return (200, "")
        else:
            response_text = "Database insertion failed"
            logging.error(response_text)
            return (500, response_text)

    def upload_roslog(self, robot_id, data) -> Tuple[int, str]:
        """
        Uploads a ROS log to the database
        FIXME: this needs to be updated and tested

        Returns: (http_status_code, message)
        """
        # Parse the input data
        print("Decoded roslog: {}".format(data))
        roslog_time = datetime.fromtimestamp(data["stamp"]["secs"], timezone.utc)

        if data["level"] == 4:
            log_level = "WARN"
        elif data["level"] == 8:
            log_level = "ERROR"
        elif data["level"] == 16:
            log_level = "CRIT"
        else:
            log_level = data["level"]

        print(
            f"{log_level}: {data['msg']} from {data['node']} at {roslog_time.ctime()}"
        )

        # Retrieve the storage unit id
        [success, storage_unit_id] = self.get_storage_unit_id(robot_id)

        if not success:
            return (400, "Robot not in any storage unit")

        # Insert the data in the database
        query = (
            "INSERT INTO app_roslog "
            "(robot_id, storage_unit, timestamp, level, node, "
            "file, msg) VALUES (%(robot_id)s, %(farm_id)s, "
            "%(time)s, %(level)s, %(node)s, %(file)s, %(msg)s)"
        )
        query_data = {
            "robot_id": robot_id,
            "storage_unit": storage_unit_id,
            "time": roslog_time,
            "level": data["level"],
            "node": data["node"],
            "file": data["file"],
            "msg": data["msg"],
        }

        print("DB query: {}".format(query % query_data))

        if self.user_query(query, query_data):
            print("Log added to database")
            return (200, "")
        else:
            response_text = "Database insertion failed"
            logging.error(response_text)
            return (500, response_text)

    def upload_survey_report(self, robot_id, storage_unit_id, data) -> Tuple[int, str]:
        """
        Uploads a survey report on the database

        The provided storage unit can be any unit belonging in the same site the
        robot has been assigned to.

        Args:
            - robot_id: ID for the robot
            - storage_unit_id: ID of the storage unit the survey was conducted in

        Returns: (http_status_code, message)
        """
        # Retrieving the storage site id associated to the provided storage unit
        result = self._select_query(
            "SELECT storage_hub_id"
            + " FROM app_storageunit AS unit"
            + " WHERE unit.id = %(storage_unit_id)s",
            {"storage_unit_id": storage_unit_id},
        )

        if not result:
            logging.error(
                f"Couldn't find storage hub for unit with id: {storage_unit_id}"
            )
            return 400, "Storage site not found"

        storage_site_id = result[0][0]

        # Retrieving the storage site id the robot was assigned to
        [success, storage_site_id2] = self.get_storage_site_id(robot_id)

        if not success:
            return (400, "Robot not in any storage site")

        # Checking that the provided storage unit is in the same site as the robot
        if storage_site_id != storage_site_id2:
            return (400, "Invalid storage site id")

        # Parsing input data
        report_time = datetime.fromtimestamp(data["report_time"]["secs"], timezone.utc)
        x_coords, y_coords, z_coords, temperatures, moistures = ([] for _ in range(5))

        for survey_point in data["survey_points"]:
            x_coords.append(survey_point["coordinates"]["x"])
            y_coords.append(survey_point["coordinates"]["y"])
            z_coords.append(survey_point["coordinates"]["z"])
            temperatures.append(survey_point["temperature"])
            moistures.append(survey_point["moisture"])

        def stringify(data):
            return f'{{{", ".join(map(str, data))}}}'

        x_coords_str = stringify(x_coords)
        y_coords_str = stringify(y_coords)
        z_coords_str = stringify(z_coords)
        temperatures_str = stringify(temperatures)
        moistures_str = stringify(moistures)

        nbr_points = [len(data["survey_points"]), 1, 1]
        nbr_points_str = stringify(nbr_points)

        # Inserting data in database
        print(f"Inserting data with robot_id={robot_id}")

        query = (
            "INSERT INTO app_sensordata ("
            "   robot_id,"
            "   storage_unit_id,"
            "   storage_hub_id,"
            "   timestamp,"
            "   x_coord,"
            "   y_coord,"
            "   z_coord,"
            "   temperatures,"
            "   moistures,"
            "   nbr_points,"
            "   resolutions,"
            "   min_coords,"
            "   notified,"
            "   is_default"
            ") VALUES ("
            "   %(robot_id)s,"
            "   %(storage_unit_id)s,"
            "   %(storage_site_id)s,"  # FIXME: redundant, remove when the database has been updated
            "   %(time)s,"
            "   %(x_coords)s,"
            "   %(y_coords)s,"
            "   %(z_coords)s,"
            "   %(temperatures)s,"
            "   %(moistures)s,"
            "   %(nbr_points)s,"
            "   '{0,0,0}',"
            "   '{0,0,0}',"
            "   false,"
            "   false"
            ")"
        )
        query_data = {
            "robot_id": robot_id,
            "storage_unit_id": storage_unit_id,
            "storage_site_id": storage_site_id,
            "time": report_time,
            "x_coords": x_coords_str,
            "y_coords": y_coords_str,
            "z_coords": z_coords_str,
            "temperatures": temperatures_str,
            "moistures": moistures_str,
            "nbr_points": nbr_points_str,
        }

        print(query)
        print(query_data)

        if self.user_query(query, query_data):
            print("Report added to database")
            return (200, "")
        else:
            response_text = "Database insertion failed"
            logging.error(response_text)
            return (500, response_text)


def lambda_handler(event, context):
    print("Starting the lambda")

    encoded_msg = b64decode(event["body"])
    unpacked_msg = unpackb(encoded_msg, use_list=True, raw=False)
    print(unpacked_msg)

    known_posts = ["heartbeat", "roslog", "survey_report"]

    if unpacked_msg["post_type"] not in known_posts:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}

    # Connect to the database
    db_client = DbClient()

    if not db_client.is_connected:
        return {
            "statusCode": 503,
            "body": json.dumps("Connection with DB failed"),
        }

    # Retrieve the robot id
    if "serial_number" not in unpacked_msg:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}

    [success, robot_id] = db_client.get_robot_id(unpacked_msg["serial_number"])

    if not success:
        return {"statusCode": 400, "body": json.dumps("Invalid request")}

    # Handle POST requests
    status = 400
    body = "Invalid request"

    if unpacked_msg["post_type"] == "heartbeat":
        status, body = db_client.update_heartbeat(robot_id, unpacked_msg)

    elif unpacked_msg["post_type"] == "roslog":
        status, body = db_client.upload_roslog(robot_id, unpacked_msg)

    elif unpacked_msg["post_type"] == "survey_report":
        if "storage_unit_id" in unpacked_msg:
            storage_unit_id = unpacked_msg["storage_unit_id"]
            status, body = db_client.upload_survey_report(
                robot_id, storage_unit_id, unpacked_msg
            )

    return {"statusCode": status, "body": json.dumps(body)}
