"""Try to follow a "figure eight" target on the yz plane."""

# %%
import matplotlib.pyplot as plt
import numpy as np
import time
import rclpy
from crisp_py.robot import make_robot

# %%
robot = make_robot("panda_left")
robot.wait_until_ready()
right_arm = make_robot("panda_right")
right_arm.wait_until_ready()

# %%
print("Initial end-effector pose and joint values:")
print(robot.end_effector_pose)
print(robot.joint_values)

def sync(robot, right_arm):
    right_arm.set_target_joint(robot.joint_values)
    
print("Ready for follow left arm ")
right_arm.node.create_timer(1.0 / 100.0, lambda: sync(robot, right_arm))
right_arm.controller_switcher_client.switch_controller("joint_impedance_controller")
# %%
print("Going to home position...")
robot.home(blocking=True)
homing_pose = robot.end_effector_pose.copy()


# %%
# Paremeters for the circle
radius = 0.2  # [m]
center = np.array([0.4, 0.0, 0.4])
ctrl_freq = 50.0
sin_freq_y = 0.25  # rot / s
sin_freq_z = 0.125  # rot / s
max_time = 8.0

# %%
robot.controller_switcher_client.switch_controller("cartesian_impedance_controller")


print(f"Left arm joint values: {robot.joint_values}")
print(f"Right arm joint values: {right_arm.joint_values}")

# %%


# %%
# The move_to function will publish a pose to /target_pose while interpolation linearly
print("Moving to center position...")
robot.move_to(position=center, speed=0.15)

# %%
# The set_target will directly publish the pose to /target_pose
ee_poses = []
target_poses = []
ts = []

print("Starting to draw a circle...")
t = 0.0
target_pose = robot.end_effector_pose.copy()
rate = robot.node.create_rate(ctrl_freq)

while True:
    x = center[0]
    y = radius * np.sin(2 * np.pi * sin_freq_y * t) + center[1]
    z = radius * np.sin(2 * np.pi * sin_freq_z * t) + center[2]
    target_pose.position = np.array([x, y, z])

    robot.set_target(pose=target_pose)

    rate.sleep()

    ee_poses.append(robot.end_effector_pose.copy())
    target_poses.append(robot._target_pose.copy())
    
    print(f"Left arm joint values: {robot.joint_values}")
    print(f"Right arm joint values: {right_arm.joint_values}")
    ts.append(t)

    t += 1.0 / ctrl_freq
   


# %%

print("Going back home.")
robot.home()

# %%
robot.shutdown()
