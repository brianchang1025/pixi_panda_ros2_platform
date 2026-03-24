"""
Dual-arm figure-eight test using crisp_py interface.

This script drives both Franka Panda arms through a figure-eight trajectory in
the YZ plane. It serves as a functional test of the crisp_py robot interface by:

- Initializing two arm controllers (left and right)
- Homing the robots and switching to cartesian impedance control
- Publishing a time-varying target pose that traces a figure-eight
- Recording end-effector and target poses for later plotting
- Returning the arms to home and shutting down

The goal is simply to verify that crisp_py can command the Panda arms and read
state successfully; trajectory accuracy is secondary.
"""

import os 
# %%
import matplotlib.pyplot as plt
import numpy as np

from crisp_py.robot import make_robot

left_arm = make_robot("panda_left")
right_arm = make_robot("panda_right")
print(left_arm._current_joint)
print(right_arm._current_joint)
left_arm.wait_until_ready()
right_arm.wait_until_ready()

# %%
print(left_arm.end_effector_pose)
print(left_arm.joint_values)
print(right_arm.end_effector_pose)
print(right_arm.joint_values)

# %%
print("Going to home position...")
left_arm.home()
right_arm.home()

homing_pose_left= left_arm.end_effector_pose.copy()
homing_pose_right= right_arm.end_effector_pose.copy()


# %%
# Paremeters for the circle
radius = 0.2  # [m]
center = np.array([0.4, 0.0, 0.4])
ctrl_freq = 50.0
sin_freq_y = 0.25  # rot / s
sin_freq_z = 0.125  # rot / s
max_time = 8.0

# %%
left_arm.controller_switcher_client.switch_controller("cartesian_impedance_controller")
right_arm.controller_switcher_client.switch_controller("cartesian_impedance_controller")

script_dir = os.path.dirname(os.path.abspath(__file__))

# %%
# The move_to function will publish a pose to /target_pose while interpolation linearly
left_arm.move_to(position=center, speed=0.15)
right_arm.move_to(position=center, speed=0.15)

# %%
# The set_target will directly publish the pose to /target_pose
ee_poses = []
ee_poses_r = []
target_poses = []
ts = []

print("Starting to draw a circle...")
t = 0.0
target_pose_left = left_arm.end_effector_pose.copy()
target_pose_right = right_arm.end_effector_pose.copy()
rate_left = left_arm.node.create_rate(ctrl_freq)
rate_right = right_arm.node.create_rate(ctrl_freq)

while t < max_time:
    x = center[0]
    y = radius * np.sin(2 * np.pi * sin_freq_y * t) + center[1]
    z = radius * np.sin(2 * np.pi * sin_freq_z * t) + center[2]
    target_pose_left.position = np.array([x, y, z])
    target_pose_right.position = np.array([x, y, z])

    left_arm.set_target(pose=target_pose_left)
    right_arm.set_target(pose=target_pose_right)

    rate_left.sleep()
    rate_right.sleep()

    ee_poses.append(left_arm.end_effector_pose.copy())
    ee_poses_r.append(right_arm.end_effector_pose.copy())
    target_poses.append(left_arm._target_pose.copy())
    ts.append(t)

    t += 1.0 / ctrl_freq

while t < max_time + 1.0:
    # Just wait a bit for the end effector to settle

    rate_left.sleep()
    rate_right.sleep()

    ee_poses.append(left_arm.end_effector_pose.copy())
    ee_poses_r.append(right_arm.end_effector_pose.copy())
    target_poses.append(left_arm._target_pose.copy())
    ts.append(t)

    t += 1.0 / ctrl_freq


print("Done drawing a circle!")


# %%
y_t = [target_pose_sample.position[1] for target_pose_sample in target_poses]
z_t = [target_pose_sample.position[2] for target_pose_sample in target_poses]

# %%
# === Normal params ===
# split recorded end-effector poses into left and right trajectories
# left and right ee pose lists were collected in the motion loop
# convert to separate y/z lists for plotting

y_ee = [ee_pose.position[1] for ee_pose in ee_poses]
z_ee = [ee_pose.position[2] for ee_pose in ee_poses]
y_ee_r = [ee_pose.position[1] for ee_pose in ee_poses_r]
z_ee_r = [ee_pose.position[2] for ee_pose in ee_poses_r]

# %%
fig, ax = plt.subplots(1, 2, figsize=(10, 5))
# plot left and right trajectories alongside the target
ax[0].plot(y_ee, z_ee, label="left current")
ax[0].plot(y_ee_r, z_ee_r, label="right current")
ax[0].plot(y_t, z_t, label="target", linestyle="--")
ax[0].set_xlabel("$y$")
ax[0].set_ylabel("$z$")
ax[0].legend()
ax[1].plot(ts, z_ee, label="left current")
ax[1].plot(ts, z_ee_r, label="right current")
ax[1].plot(ts, z_t, label="target", linestyle="--")
ax[1].set_xlabel("$t$")
ax[1].legend()

for a in ax:
    a.grid()

fig.tight_layout()

plt.show()

# %%

print("Going back home.")
left_arm.home()
right_arm.home()

# %%
left_arm.shutdown()
right_arm.shutdown()
print("Done.")