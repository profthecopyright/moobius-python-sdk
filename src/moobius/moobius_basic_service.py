# moobius_basic_service.py

import asyncio
import json
import traceback

from dacite import from_dict

from moobius.basic.ws_client import WSClient
from moobius.basic.ws_payload_builder import WSPayloadBuilder
from moobius.basic.http_api_wrapper import HTTPAPIWrapper
from moobius.basic.types import MessageUp, Action, FeatureCall, Copy, Payload, Character

class MoobiusBasicService:
    def __init__(self, http_server_uri="", ws_server_uri="", service_id="", email="", password="", **kwargs):
        self.http_api = HTTPAPIWrapper(http_server_uri)
        self._ws_client = WSClient(ws_server_uri, handle=self.handle_received_payload)
        self._ws_payload_builder = WSPayloadBuilder()

        self._email = email
        self._password = password

        self._access_token = ""
        self._refresh_token = ""
        self.service_id = service_id

    async def start(self, bind_to_channels=None):
        # Authenticate and get access_token
        self._access_token, self._refresh_token = self.http_api.authenticate(self._email, self._password)
        # print(self.http_api.get_service_list())

        # Connect to websocket server
        await self._ws_client.connect()

        # if no service_id is passed, create a new service
        self.service_id = self.service_id or self.http_api.create_service(description="Generated by MoobiusBasicService")
        
        await self.send_service_login()

        if bind_to_channels:
            print("bind_to_channels", bind_to_channels)
            for channel_id in bind_to_channels:
                self.http_api.bind_service_to_channel(self.service_id, channel_id)
        else:
            pass
        
        await self.on_start()   # fetch user list, send features and database operations, etc.

        asyncio.create_task(self.send_heartbeat())
        # todo: refresh
        # todo: use scheduler

        # Start listening
        while True:
            await asyncio.sleep(1)


    @property
    def access_token(self):
        return self._access_token

    @property
    def refresh_token(self):
        return self._refresh_token


    async def handle_received_payload(self, payload):
        """
        Decode the received payload and handle based on its type.
        """
        payload_data = json.loads(payload)
        payload = from_dict(data_class=Payload, data=payload_data)

        if payload.type == "msg_up":
           await self.on_msg_up(payload.body)
        
        elif payload.type == "action":
           await self.on_action(payload.body)
        
        elif payload.type == "feature_call":
            await self.on_feature_call(payload.body)

        elif payload.type == "copy_client":     # todo: legacy
            await self.on_copy(payload.body)

        else:   # todo: add types (copy_client etc)
            await self.on_unknown_payload(payload)


    # =================== on_xxx, to be override ===================
    async def on_start(self):
        """
        Called when the service is initialized.
        """
        print("Service started. Override this method to perform initialization tasks.")
        pass


    async def on_msg_up(self, msg_up: MessageUp):
        """
        Handle a payload from a user.
        """
        print("MessageUp received:", msg_up)
        pass

    async def on_action(self, action: Action):
        """
        Handle an action from a user.
        """
        print("Action received:", action)
        pass

    async def on_feature_call(self, feature_call: FeatureCall):
        """
        Handle a feature call from a user.
        """
        print("Feature call received:", feature_call)
        pass


    async def on_copy(self, copy: Copy):
        """
        Handle a copy from Moobius.
        """
        print("Copy received:", copy)
        pass


    async def on_unknown_payload(self, payload: Payload):
        """
        Handle an unknown payload.
        """
        print("Unknown payload received:", payload)
        pass

    # =================== send_xxx, to be used ===================
    
    # fetch real users and set features to db
    async def fetch_real_characters(self, channel_id):
        """
        Fetches data from Moobius using HTTP request
        """
        
        data = self.http_api.get_channel_userlist(channel_id, self.service_id)

        if data["code"] == 10000:
            userlist = data["data"]["userlist"]

            return [from_dict(data_class=Character, data=d) for d in userlist]
        else:
            print("fetch_real_characters error", data)

            return []

    async def send_service_login(self):
        payload = self._ws_payload_builder.service_login(self.service_id, self.access_token)
        print("payload", payload)
        await self._ws_client.send(payload)

    async def send_msg_down(self, channel_id, recipients, subtype, message_content, sender):
        payload = self._ws_payload_builder.msg_down(self.service_id, channel_id, recipients, subtype, message_content, sender)
        await self._ws_client.send(payload)

    async def send_update(self, target_client_id, data):
        payload = self._ws_payload_builder.update(self.service_id, target_client_id, data)
        print(payload)
        await self._ws_client.send(payload)

    async def send_update_userlist(self, channel_id, user_list, recipients):
        payload = self._ws_payload_builder.update_userlist(self.service_id, channel_id, user_list, recipients)
        print("send_update_userlist", payload)
        await self._ws_client.send(payload)

    async def send_update_channel_info(self, channel_id, channel_data):
        payload = self._ws_payload_builder.update_channel_info(self.service_id, channel_id, channel_data)
        print(payload)
        await self._ws_client.send(payload)

    async def send_update_playground(self, channel_id, content, recipients):
        payload = self._ws_payload_builder.update_playground(self.service_id, channel_id, content, recipients)
        print(payload)
        await self._ws_client.send(payload)

    async def send_update_features(self, channel_id, feature_data, recipients):
        payload = self._ws_payload_builder.update_features(self.service_id, channel_id, feature_data, recipients)
        print(payload)
        await self._ws_client.send(payload)

    async def send_ping(self):
        payload = self._ws_payload_builder.ping()
        await self._ws_client.send(payload)

    async def send_heartbeat(self):
        """
        Send a ping payload every 30 seconds and check the response.
        """
        while True:
            await asyncio.sleep(30)
            try:
                await self.send_ping()
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed. Attempting to reconnect...")
                await self.send_heartbeat()
                print("Reconnected!")
                break
            except Exception as e:
                traceback.print_exc()
                print("Error occurred:", e)
                await self.send_heartbeat()
                print("Reconnected!")
                break
            '''response = await self.websocket.recv()
            if not json.loads(response).get("status", False):
                await self.send_service_login()'''