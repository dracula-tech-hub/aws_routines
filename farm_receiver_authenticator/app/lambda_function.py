"""
Lambda to check authentication of all in/out going AWS communications
"""

from rds_db_client import RdsDbClient
import logging


class DatabaseClient(RdsDbClient):
    """
    TODO
    """

    def check_robot_identifier(self, serial_number: str, identifier: str) -> bool:
        """
        Returns whether a serial number exists and matches its identifier
        """
        # Check serial number
        result = self._select_query(
            "SELECT identifier FROM app_robot WHERE serial_number = %(serial_number)s",
            {"serial_number": serial_number},
        )

        if not result or result == []:
            logging.error(f"Robot {serial_number} doesn't exist")
            return False
        else:
            print(f"Found robot {serial_number}")

        # Match identifier
        if result[0][0] != identifier:
            logging.error(f"Wrong identifier string for robot {serial_number}")
            return False
        else:
            print(f"Robot {serial_number} was identified successfully")

        return True

    def check_robot_activation(self, serial_number: str) -> bool:
        """
        Returns whether a robot is activated
        """
        result = self._select_query(
            "SELECT activated FROM app_robot WHERE serial_number = %(serial_number)s",
            {"serial_number": serial_number},
        )

        if not result or result == []:
            logging.error(f"Robot {serial_number} doesn't exist")
            return False

        if result[0][0] == True:
            print(f"Robot {serial_number} is activated")
            return True
        else:
            logging.error(f"Robot {serial_number} is not activated")
            return False


def lambda_handler(event, context):
    print("Start of the lambda...")
    print(event)

    if "queryStringParameters" not in event:
        return {
            "statusCode": 400,
            "body": json.dumps("No input data"),
        }

    parameters = event["queryStringParameters"]

    if "serial_number" not in parameters or "identifier" not in parameters:
        raise Exception("Unauthorized, missing arguments")

    serial_number = parameters["serial_number"]
    identifier = parameters["identifier"]

    print(f"serial_number={serial_number}")
    print(f"identifier={identifier}")

    db_client = DatabaseClient()

    authorise = "Allow"

    if not db_client.check_robot_identifier(serial_number, identifier):
        authorise = "Deny"

    if not db_client.check_robot_activation(serial_number):
        authorise = "Deny"

    return {
        "principalId": "user",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": authorise,
                    "Resource": event["methodArn"],
                }
            ],
        },
    }
