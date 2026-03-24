#!/usr/bin/env python3
# Copyright jk-ethz
# Released under GNU AGPL-3.0
# Contact us for other licensing options.

# Developed and tested on system version
# 4.2.1

# Inspired by
# https://github.com/frankaemika/libfranka/issues/63
# https://github.com/ib101/DVK/blob/master/Code/DVK.py

from abc import ABC, abstractmethod
from itertools import count
from time import sleep
import atexit
import argparse
import base64
import hashlib
import logging
import os
from urllib.parse import urljoin
from http import HTTPStatus

import requests


LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base client
# ---------------------------------------------------------------------------

class FrankaClient(ABC):
    def __init__(self, hostname: str, username: str, password: str, protocol: str = 'https'):
        requests.packages.urllib3.disable_warnings()
        self._session = requests.Session()
        self._session.verify = False
        self._hostname = f'{protocol}://{hostname}'
        self._username = username
        self._password = password
        self._logged_in = False
        self._logged_in_token = None
        self._token = None
        self._token_id = None

    @staticmethod
    def _encode_password(username, password):
        bs = ','.join([str(b) for b in hashlib.sha256((f'{password}#{username}@franka').encode('utf-8')).digest()])
        return base64.encodebytes(bs.encode('utf-8')).decode('utf-8')

    def _login(self):
        LOGGER.info(f"\n[{self._hostname}] Logging in...")
        if self._logged_in:
            LOGGER.info(f"[{self._hostname}] Already logged in.")
            return
        login = self._session.post(
            urljoin(self._hostname, '/admin/api/login'),
            json={'login': self._username,
                  'password': self._encode_password(self._username, self._password)},
        )
        if login.status_code != HTTPStatus.OK:
            LOGGER.error(f"[{self._hostname}] Error logging in.")
            raise RuntimeError(f"[{self._hostname}] Error logging in.")
        self._session.cookies.set('authorization', login.text)
        self._logged_in = True
        self._logged_in_token = login.text
        LOGGER.info(f"[{self._hostname}] Successfully logged in.")

    def _logout(self):
        LOGGER.info(f"[{self._hostname}] Logging out...")
        if not self._logged_in:
            LOGGER.error(f"[{self._hostname}] Not logged in.")
            raise RuntimeError(f"[{self._hostname}] Not logged in.")
        logout = self._session.post(urljoin(self._hostname, '/admin/api/logout'))
        if logout.status_code != HTTPStatus.OK:
            LOGGER.error(f"[{self._hostname}] Error logging out.")
            raise RuntimeError(f"[{self._hostname}] Error logging out.")
        self._session.cookies.clear()
        self._logged_in = False
        LOGGER.info(f"[{self._hostname}] Successfully logged out.")

    def _shutdown(self):
        LOGGER.info(f"[{self._hostname}] Shutting down...")
        if not self._is_active_token():
            LOGGER.error(f"[{self._hostname}] Cannot shutdown without an active control token.")
            raise RuntimeError(f"[{self._hostname}] Cannot shutdown without an active control token.")
        try:
            self._session.post(urljoin(self._hostname, '/admin/api/shutdown'), json={'token': self._token})
        except requests.exceptions.RequestException:
            # Server may shut down before sending a complete response — ignore.
            pass
        finally:
            LOGGER.info(f"[{self._hostname}] The robot is shutting down. Please wait for the yellow lights to turn off, then switch the control box off.")

    def _reboot(self):
        LOGGER.info(f"[{self._hostname}] Rebooting...")
        if not self._is_active_token():
            LOGGER.error(f"[{self._hostname}] Cannot reboot without an active control token.")
            raise RuntimeError(f"[{self._hostname}] Cannot reboot without an active control token.")
        try:
            self._session.post(urljoin(self._hostname, '/admin/api/reboot'), json={'token': self._token})
        except requests.exceptions.RequestException:
            # Server may shut down before sending a complete response — ignore.
            pass
        finally:
            LOGGER.info(f"[{self._hostname}] The robot is rebooting. Please wait for the yellow lights to turn off, then switch the control box off and on again.")
            
    def _get_active_token_id(self):
        token_query = self._session.get(urljoin(self._hostname, '/admin/api/control-token'))
        if token_query.status_code != HTTPStatus.OK:
            LOGGER.error(f"[{self._hostname}] Error getting control token status.")
            raise RuntimeError(f"[{self._hostname}] Error getting control token status.")
        json = token_query.json()
        return None if json['activeToken'] is None else json['activeToken']['id']

    def _is_active_token(self):
        active_token_id = self._get_active_token_id()
        return active_token_id is None or active_token_id == self._token_id

    def _request_token(self, physically=False):
        LOGGER.info(f"[{self._hostname}] Requesting a control token...")
        if self._token is not None:
            if self._token_id is None:
                LOGGER.error(f"[{self._hostname}] Token exists but token_id is missing.\"")
                raise RuntimeError(f"[{self._hostname}] Token exists but token_id is missing.")
            LOGGER.info(f"[{self._hostname}] Already having a control token.")
            return
        token_request = self._session.post(
            urljoin(self._hostname, f'/admin/api/control-token/request{"?force" if physically else ""}'),
            json={'requestedBy': self._username},
        )
        if token_request.status_code != HTTPStatus.OK:
            LOGGER.error(f"[{self._hostname}] Error requesting control token.")
            raise RuntimeError(f"[{self._hostname}] Error requesting control token.")
        json = token_request.json()
        self._token = json['token']
        self._token_id = json['id']
        LOGGER.info(f"[{self._hostname}] Received control token is {self._token} with id {self._token_id}.")

    def _release_token(self):
        LOGGER.info(f"[{self._hostname}] Releasing tokens...")
        token_delete = self._session.delete(
            urljoin(self._hostname, '/admin/api/control-token'),
            json={'token': self._token},
        )
        if token_delete.status_code != 200:
            LOGGER.error(f"[{self._hostname}] Error releasing control token.")
            raise RuntimeError(f"[{self._hostname}] Error releasing control token.")
        self._token = None
        self._token_id = None
        LOGGER.info(f"[{self._hostname}] Successfully released control token.")
        self._logged_in_token = None
        LOGGER.info(f"[{self._hostname}] Successfully released login token.")

    def get_logged_in_token(self):
        return self._logged_in_token



# ---------------------------------------------------------------------------
# High-level lock/unlock + FCI client
# ---------------------------------------------------------------------------

class FrankaLockUnlock(FrankaClient):
    def __init__(self, hostname: str, username: str, password: str, protocol: str = 'https', relock: bool = False):
        super().__init__(hostname, username, password, protocol=protocol)
        self._relock = relock
        atexit.register(self._cleanup)

    def _cleanup(self):
        if self._relock:
            self._lock_unlock(unlock=False)
        if self._token is not None or self._token_id is not None:
            self._release_token()
        if self._logged_in:
            self._logout()

    def _activate_fci(self):
        LOGGER.info(f"[{self._hostname}] Activating FCI...")
        fci_request = self._session.post(
            urljoin(self._hostname, '/admin/api/control-token/fci'),
            json={'token': self._token},
        )
        if fci_request.status_code != 200:
            LOGGER.error(f"[{self._hostname}] Error activating FCI.")
            raise RuntimeError(f"[{self._hostname}] Error activating FCI.")
        LOGGER.info(f"[{self._hostname}] Successfully activated FCI.")

    def _deactivate_fci(self):
        LOGGER.info(f"[{self._hostname}] Deactivating FCI...")
        if self._token is None:
            LOGGER.error(f"[{self._hostname}] Cannot deactivate FCI without a control token.")
            raise RuntimeError(f"[{self._hostname}] Cannot deactivate FCI without a control token.")

        fci_request = self._session.delete(
            urljoin(self._hostname, '/admin/api/control-token/fci'),
            json={'token': self._token},
        )

        if fci_request.status_code in (200, 204):
            LOGGER.info(f"[{self._hostname}] Successfully deactivated FCI.")
        elif fci_request.status_code in (404, 405):
            LOGGER.warning(f"[{self._hostname}] No dedicated FCI deactivation endpoint. Releasing control token to disable FCI.")
        else:
            LOGGER.error(f"[{self._hostname}] Error deactivating FCI.")
            raise RuntimeError(f"[{self._hostname}] Error deactivating FCI.")

    def _home_gripper(self):
        LOGGER.info(f"[{self._hostname}] Homing the gripper...")
        action = self._session.post(
            urljoin(self._hostname, '/desk/api/gripper/homing'),
            headers={'X-Control-Token': self._token},
        )
        if action.status_code != 200:
            LOGGER.error(f"[{self._hostname}] Error homing gripper.")
            raise RuntimeError(f"[{self._hostname}] Error homing gripper.")
        LOGGER.info(f"[{self._hostname}] Successfully homed the gripper.")

    def get_operating_mode(self) -> str:
        """Get the current operating mode of the robot."""
        response = self._session.get(urljoin(self._hostname, '/admin/api/system'))
        response.raise_for_status()
        return response.json().get('status')

    def _lock_unlock(self, unlock: bool, force: bool = False):
        LOGGER.info(f'[{self._hostname}] {"Unlocking" if unlock else "Locking"} the robot...')
        action = self._session.post(
            urljoin(self._hostname, f'/desk/api/robot/{"open" if unlock else "close"}-brakes'),
            files={'force': force},
            headers={'X-Control-Token': self._token},
        )
        if action.status_code != 200:
            LOGGER.error(f"[{self._hostname}] Error requesting brake open/close action.")
            raise RuntimeError(f"[{self._hostname}] Error requesting brake open/close action.")
        LOGGER.info(f"[{self._hostname}] Successfully {'unlocked' if unlock else 'locked'} the robot.")
        
    def enable_robot(self):
        if not self._logged_in:
            self._login()

        self._request_token(physically=True)

        for _ in range(20):
            if self._is_active_token():
                break
            LOGGER.info(
                f"[{self._hostname}] Please press the button with the (blue) circle on the robot to confirm physical access."
            )
            sleep(1)
        else:
            raise RuntimeError(f"[{self._hostname}] Timed out waiting for active control token.")

        self._lock_unlock(unlock=True)
        self._home_gripper()
        self._activate_fci()

    def unable_robot(self):
        self._deactivate_fci()
        self._lock_unlock(unlock=False)
        
    def reboot_sys(self):
        self.unable_robot()
        sleep(3)
        self.enable_robot()
    

# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(
        description="Interactive Franka Desk control utility."
    )
    parser.add_argument(
        "robot_ip",
        type=str,
        help="IP address of the robot.",
    )
    args = parser.parse_args()

    username = os.getenv("FRANKA_DESK_USERNAME")
    password = os.getenv("FRANKA_DESK_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "Missing user or password. They should be set as environment variables "
            "FRANKA_DESK_USERNAME and FRANKA_DESK_PASSWORD"
        )

    client = FrankaLockUnlock(
        hostname=args.robot_ip,
        username=username,
        password=password,
        relock=True,
    )

    client._login()
    client.enable_robot()

    try:
        LOGGER.info(f"[{client._hostname}] Requesting control of the robot...")
        while True:
            client._request_token(physically=True)
            for _ in range(20):
                if client._is_active_token():
                    LOGGER.info(f"[{client._hostname}] Successfully acquired control over the robot.")
                    LOGGER.info("Commands: r=reboot robot   q=quit")
                    while True:
                        command = input("> Enter command [r/q]: ").strip().lower()
                        
                        if command == "r":
                            client.reboot_sys()
                        elif command == "q":
                            LOGGER.info(f"[{client._hostname}] Quitting program.")
                            return
                        else:
                            LOGGER.warning("Unknown command. Use: r or q.")
                LOGGER.info(
                    f"[{client._hostname}] Please press the button with the (blue) circle on the robot to confirm physical access."
                )
                sleep(1)

            client._cleanup()
    finally:
        if client._token is not None or client._token_id is not None:
            client._release_token()
        if client._logged_in:
            client._logout()


if __name__ == "__main__":
    main()
