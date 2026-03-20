"""Send recording commands for an episode recorder node to start, stop recording, save episodes and quit using the franka pulot buttons."""

import rclpy
from rclpy.node import Node

from franka_buttons_interfaces.msg import FrankaPilotButtonEvent
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String


class ButtonToRecordMessage(Node):
    """Node that subscribes to the button event and toggles the gripper when the circle button is pressed."""

    def __init__(self) -> None:
        super().__init__("button_to_record_message")

        self.create_subscription(
            FrankaPilotButtonEvent,
            "franka_pilot_button_event",
            self.button_callback,
            10,
        )

        self.publisher = self.create_publisher(String, "record_transition", 10)
        self.right_publisher = self.create_publisher(Bool, "franka_buttons/right", 10)
        self.gripper_pub = self.create_publisher(JointState, "trigger/trigger_state_broadcaster/joint_states", 10)
        self.create_timer(1.0 / 50.0, callback=self.publish_gripper_state)
        

        # Add a cooldown to avoid multiple toggles
        self._last_toggle = self.get_clock().now()
        self._cooldown = 0.5

        self.gripper_state = 0.0

        self.get_logger().info("ButtonToRecordMessage node started.")

    def publish_gripper_state(self):
        msg = JointState()
        msg.position = [self.gripper_state]
        msg.effort = [0.0]
        self.gripper_pub.publish(msg)

    def publish_check_false(self):
        self.check_publisher.publish(Bool(data=False))

    def button_callback(self, msg: FrankaPilotButtonEvent):
        """Callback function for the button event.

        If circle pressed, then pass the command to the gripper client to toggle the gripper.
        """
        

        if (self.get_clock().now() - self._last_toggle).nanoseconds < self._cooldown * 1e9:
            return

        if msg.pressed:
            if msg.pressed[0] == "circle":
                self.get_logger().info("Circle button pressed. Sending a record message.")
                self.publisher.publish(String(data="record"))
            if msg.pressed[0] == "check":
                self.get_logger().info("Check button pressed. Sending a save episode message.")
                self.publisher.publish(String(data="save"))
            if msg.pressed[0] == "cross":
                self.get_logger().info("Cross button pressed. Sending a delete episode message.")
                self.publisher.publish(String(data="delete"))
            if msg.pressed[0] == "up":
                self.get_logger().info("UP button pressed. Sending a quit command message.")
                self.publisher.publish(String(data="exit"))
            if msg.pressed[0] == "down":
                self.get_logger().info("Down button pressed. Sending a gripper toggle command.")
                self.gripper_state = 1.0 - self.gripper_state
            if msg.pressed[0] == "right":
                self.get_logger().info("Right button pressed. Sending a check command.")
                self.right_publisher.publish(Bool(data=True))

            self._last_toggle = self.get_clock().now()


def main():
    rclpy.init()
    node = ButtonToRecordMessage()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
