import json
import urllib.parse
import pytarallo.Errors as Errors
from typing import Optional

import requests

from pytarallo.AuditEntry import AuditEntry, AuditChanges
from pytarallo.Item import Item
#from src.src.Errors import *

VALID_RESPONSES = [200, 201, 204, 400, 403, 404]


class Tarallo(object):
    """This class handles the Tarallo session"""

    def __init__(self, url: str, token: str):
        """

        :param url: Tarallo URL
        :param token: Token (go to Options > Get token)
        """
        self.url = url.rstrip('/')
        self.token = token.strip()
        self.__session = requests.Session()
        self.response = None

    def __prepare_url(self, url):
        if isinstance(url, str):
            url = '/' + url.lstrip('/')
        else:
            # Best library to join url components: this thing.
            url = '/' + '/'.join(s.strip('/') for s in url)
        return self.url + url

    def __check_response(self):
        if self.response.status_code == 401:
            raise Errors.AuthenticationError
        if self.response.status_code not in VALID_RESPONSES:
            raise Errors.ServerError

    # requests.Session() wrapper methods
    # These guys implement further checks
    def get(self, url) -> requests.Response:
        url = self.__prepare_url(url)
        headers = {"Authorization": "Token " + self.token}
        self.response = self.__session.get(url, headers=headers)
        self.__check_response()
        return self.response

    def delete(self, url) -> requests.Response:
        url = self.__prepare_url(url)
        headers = {"Authorization": "Token " + self.token}
        self.response = self.__session.delete(url, headers=headers)
        self.__check_response()
        return self.response

    def post(self, url, data, headers=None) -> requests.Response:
        if headers is None:
            headers = {}
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = "Token " + self.token 
        url = self.__prepare_url(url)
        self.response = self.__session.post(url, data=data, headers=headers)
        self.__check_response()
        return self.response

    def put(self, url, data, headers=None) -> requests.Response:
        if headers is None:
            headers = {}
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = "Token " + self.token
        url = self.__prepare_url(url)
        self.response = self.__session.put(url, data=data, headers=headers)
        self.__check_response()
        return self.response

    def patch(self, url, data, headers=None) -> requests.Response:
        if headers is None:
            headers = {}
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = "Token " + self.token
        # , cookies={"XDEBUG_SESSION": "PHPSTORM"}
        url = self.__prepare_url(url)
        self.response = self.__session.patch(url, data=data, headers=headers)
        self.__check_response()
        return self.response

    @staticmethod
    def urlencode(part):
        return urllib.parse.quote(part, safe='')

    def status(self):
        """
        Returns the status_code of /v2/session, useful for testing purposes.
        """
        try:
            return self.get('/v2/session').status_code
        except Errors.AuthenticationError:
            return self.response.status_code

    def get_item(self, code, depth_limit=None):
        """This method returns an Item instance recieved from the server"""
        url = '/v2/items/' + self.urlencode(code)
        if depth_limit is not None:
            url += '?depth=' + str(int(depth_limit))
        self.get(url)
        if self.response.status_code == 200:
            item = Item(json.loads(self.response.content))
            return item
        elif self.response.status_code == 404:
            raise Errors.ItemNotFoundError(f"Item {code} doesn't exist")

        def get_product(self, model):
            """returns an instance of Product retrieved from the server

            Args:
                self, model

            Returns:
                Product
            """
            #TODO

    def add_item(self, item):
        """Add an item to the database and eventually update its code
            TODO: change item to ItemToUpload instance"""
        if item.code is not None:  # check whether an item's code was manually added
            self.put([f'/v2/items/{item.code}'],
                     data=json.dumps(item.serializable()))
            added_item_status = self.response.status_code
        else:
            self.post(['/v2/items/'], data=json.dumps(item.serializable()))
            added_item_status = self.response.status_code

        if added_item_status == 201:
            item.code = json.loads(self.response.content)
            item.path = None
            return True
        elif added_item_status == 400 or added_item_status == 404:
            raise Errors.ValidationError
        elif added_item_status == 403:
            raise Errors.NotAuthorizedError

    def add_product(self, product: Product):
        """adds a product to the database or updates its code

        Args:
            self, product: Prodcut

        Returns:
            True if success, Errors exeptions otherwise
        """
        #TODO



    def update_features(self, code: str, features: dict):
        """
        Send updated features to the database (this is the PATCH endpoint)
        """
        self.patch(['/v2/items/', self.urlencode(code),
                    '/features'], json.dumps(features))
        if self.response.status_code == 200 or self.response.status_code == 204:
            return True
        elif self.response.status_code == 400:
            raise Errors.ValidationError("Impossible to update feature/s")
        elif self.response.status_code == 404:
            raise Errors.ItemNotFoundError(f"Item {code} doesn't exist")

    def move(self, code, location):
        """
        Move an item to another location
        """
        move_status = self.put(
            ['v2/items/', self.urlencode(code), '/parent'], json.dumps(location)).status_code
        if move_status == 204 or move_status == 201:
            return True
        elif move_status == 400:
            raise Errors.ValidationError(f"Cannot move {code} into {location}")
        elif move_status == 404:
            response_json = json.loads(self.response.content)
            if 'item' not in response_json:
                raise Errors.ServerError("Server didn't find an item, but isn't telling us which one")
            if response_json['item'] == location:
                raise Errors.LocationNotFoundError
            else:
                raise Errors.ItemNotFoundError(f"Item {response_json['item']} doesn't exist")
        else:
            raise RuntimeError(f"Move failed with {move_status}")

    def remove_item(self, code):
        """
        Remove an item from the database

        :return: True if successful deletion
                 False if deletion failed
        """
        item_status = self.delete(['/v2/items/', self.urlencode(code)]).status_code
        deleted_status = self.get(['/v2/deleted/', self.urlencode(code)]).status_code
        if deleted_status == 200:
            # Actually deleted
            return True
        if item_status == 404 and deleted_status == 404:
            # ...didn't even exist in the first place? Well, ok...
            return None  # Tri-state FTW!
        else:
            return False

    def restore_item(self, code, location):
        """
        Restores a deleted item

        :return: True if item successfully restored
                 False if failed to restore
        """
        item_status = self.put(['/v2/deleted/', self.urlencode(code), '/parent'], json.dumps(location)).status_code
        if item_status == 201:
            return True
        else:
            return False

    def travaso(self, code, location):
        item = self.get_item(code, 1)
        codes = []
        for inner_item in item.contents:
            codes.append(inner_item.code)
        for inner_code in codes:
            self.move(inner_code, location)
        return True

    def get_history(self, code, limit: Optional[int] = None):
        url = f'/v2/items/{self.urlencode(code)}/history'
        if limit is not None:
            url += '?length=' + str(int(limit))
        history = self.get(url)

        if history.status_code == 200:
            result = []
            for entry in history.json():
                try:
                    change = AuditChanges(entry["change"])
                except ValueError:
                    change = AuditChanges.Unknown
                result.append(AuditEntry(entry["user"], change, float(entry["time"]), entry["other"]))
            return result
        elif history.status_code == 404:
            raise Errors.ItemNotFoundError(f"Item {code} doesn\'t exist")
        else:
            raise RuntimeError("Unexpected return code")

    def get_codes_by_feature(self, feature: str, value: str):
        url = f"/v2/features/{self.urlencode(feature)}/{self.urlencode(value)}"
        items = self.get(url)

        if items.status_code == 200:
            return items.json()
        elif items.status_code == 400:
            exception = items.json()
            raise Errors.ValidationError(exception.get('message', 'No message from the server'))
        else:
            raise RuntimeError("Unexpected return code")