import cv2
import matplotlib.pyplot as plt
import time
from crisp_py.camera import Camera, CameraConfig

camera_config = CameraConfig(
    camera_name="primary",
    camera_frame="primary_link",
    resolution=(256, 256),
    camera_color_image_topic="camera/wrist_camera/color/image_raw",
    camera_color_info_topic="camera/wrist_camera/color/camera_info",
)

camera = Camera(config=camera_config, namespace="")
camera.wait_until_ready()

plt.ion()  # Turn on interactive mode
fig, ax = plt.subplots(figsize=(8, 6))
img_display = None

print("Streaming started. Close the window to stop.")

try:
    while True:
        img = camera.current_image
        
        if img is not None:
            # If colors look wrong, swap BGR to RGB
            # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            if img_display is None:
                # First frame: initialize the plot
                img_display = ax.imshow(img)
                ax.set_title("Live Crisp Camera Feed")
                ax.axis('off')
            else:
                # Subsequent frames: just update the data (much faster)
                img_display.set_data(img)
            
            # Update the window
            fig.canvas.draw()
            fig.canvas.flush_events()
        
        time.sleep(0.01)  # Small sleep to prevent CPU hogging

except KeyboardInterrupt:
    print("Stopping stream...")
finally:
    plt.ioff()
    plt.show()