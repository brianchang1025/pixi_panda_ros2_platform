#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from franka_msgs.msg import FrankaState # Only needed on Robot PC
from rclpy.qos import qos_profile_system_default

class RobotModeBroadcaster(Node):
    
    def __init__(self):
        super().__init__('robot_mode_broadcaster')
        
        self.robot_mode_topic = 'robot_mode'
        self.robot_state_broadcaster_topic = 'franka_robot_state_broadcaster/robot_state'
        
        self.robot_mode =None
        
        self.frequency = 30.0
        self.timer = self.create_timer(1.0 / self.frequency, self.callback_publish_robot_mode)
       
        self.create_subscription(
            FrankaState,
            self.robot_state_broadcaster_topic,
            self.callback_robot_state_broadcaster,
            qos_profile_system_default)
        
        self.robot_mode_publisher = self.create_publisher(
            Int32, 
            self.robot_mode_topic, 
            qos_profile_system_default)
        
    def callback_robot_state_broadcaster(self, msg : FrankaState):
        self.robot_mode = msg.robot_mode
        
    def callback_publish_robot_mode(self):
        if self.robot_mode is None:
            return
        
        msg = Int32()
        msg.data = self.robot_mode
        self.robot_mode_publisher.publish(msg)

def main():
    rclpy.init()
    node = RobotModeBroadcaster()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
    
if __name__ == '__main__':
    main()