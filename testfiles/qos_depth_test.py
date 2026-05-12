import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from rclpy.qos import QoSProfile, HistoryPolicy, qos_profile_system_default

class QosExperiment(Node):
    def __init__(self):
        super().__init__('qos_experiment')

        # 1. The Default Publisher (Depth 10)
        self.pub_default = self.create_publisher(
            Int32, 'topic_default', qos_profile_system_default)

        # 2. The Depth 1 Publisher
        depth_1_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1)
        self.pub_depth_1 = self.create_publisher(
            Int32, 'topic_depth_1', depth_1_qos)

        self.timer = self.create_timer(0.5, self.timer_callback)
        self.count = 0

    def timer_callback(self):
        self.count += 1
        msg = Int32()
        msg.data = self.count
        
        self.pub_default.publish(msg)
        self.pub_depth_1.publish(msg)
        self.get_logger().info(f'Broadcasting ID: {self.count}')

def main():
    rclpy.init()
    node = QosExperiment()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()