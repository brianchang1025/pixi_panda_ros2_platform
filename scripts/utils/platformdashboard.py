import time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState, CameraInfo
from std_msgs.msg import Int32
from utils.utils import ArmConfig

class RobotDashboard(Node):
    def __init__(self, use_camera: bool, arms: list[ArmConfig]):
        super().__init__('robot_dashboard')
        
        # 1. State and Heartbeat Tracking
        self.status_dict = {f"{arm.namespace} Panda Arm": "STALE" for arm in arms}
        self.heartbeats = {f"{arm.namespace}_arm": 0.0 for arm in arms}
        
        if use_camera:
            self.status_dict.update({"Wrist Camera": "STALE", "3rd-Person Camera": "STALE"})
            self.heartbeats.update({"wrist_cam": 0.0, "third_cam": 0.0})

        # 2. Setup Subscriptions
        for arm in arms:
            self.create_subscription(JointState, f'/{arm.namespace}/joint_states', 
                                     lambda msg, a=arm.namespace: self._update_hb(f"{a}_arm", msg), 10)
            self.create_subscription(Int32, f'/{arm.namespace}/robot_mode', 
                                     lambda msg, a=arm.namespace: self._robot_mode_callback(msg, a), 10)
        
        if use_camera:
            self.create_subscription(CameraInfo, '/camera/wrist_camera/color/camera_info', 
                                     lambda msg: self._update_hb("wrist_cam", msg), 10)
            self.create_subscription(CameraInfo, '/camera/third_person_camera/color/camera_info', 
                                     lambda msg: self._update_hb("third_cam", msg), 10)

        # 3. Watchdog Timer (Check every 1 second)
        self.create_timer(1.0, self._check_heartbeats)

    def _update_hb(self, key, msg):
        """Generic heartbeat updater for any incoming topic."""
        self.heartbeats[key] = time.time()

    def _robot_mode_callback(self, msg, namespace):
        modes = {4: "COLLISION", 5: "EMERGENCY STOP"}
        self.status_dict[f"{namespace} Panda Arm"] = modes.get(msg.data, "ACTIVE")

    def _check_heartbeats(self):
        """Timer callback that detects silent hardware."""
        now = time.time()
        timeout = 2.0  # Seconds before marking as DISCONNECTED

        # Check Arms
        for arm_key, last_time in self.heartbeats.items():
            if "arm" in arm_key:
                name = arm_key.replace("_arm", " Panda Arm")
                if now - last_time > timeout:
                    self.status_dict[name] = "DISCONNECTED"
                else:
                    self.status_dict[name] = "ACTIVE"

        # Check Cameras
        if "wrist_cam" in self.heartbeats:
            if now - self.heartbeats["wrist_cam"] > timeout:
                self.status_dict["Wrist Camera"] = "DISCONNECTED"
            else:
                self.status_dict["Wrist Camera"] = "ACTIVE"
        if "third_cam" in self.heartbeats:
            if now - self.heartbeats["third_cam"] > timeout:
                self.status_dict["3rd-Person Camera"] = "DISCONNECTED"
            else:
                self.status_dict["3rd-Person Camera"] = "ACTIVE"

    def get_status_list(self):
        return list(self.status_dict.items())