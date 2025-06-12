import matplotlib.pyplot as plt
import numpy as np

# 测试点2数据
time = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
temp = [24.5, 24.7, 24.7, 24.9, 25, 25, 25.2, 25.1, 25.2, 25.3, 25.3]
hum = [62.3, 61.8, 61.3, 61.5, 61.5, 61.4, 61.2, 61.4, 61.1, 61.6, 61.1]
lux = [741, 738, 734, 733, 734, 728, 728, 720, 747, 746, 734]
pressure = [989, 989.1, 989.2, 989.3, 989.5, 989.5, 989.7, 989.8, 990.1, 990.2, 990.3]
height = [203.7, 203.1, 202.1, 201.1, 200, 199.4, 197.8, 196.6, 194.3, 193.4, 192.7]

# 创建图形和子图
fig, axs = plt.subplots(5, 1, figsize=(10, 15), sharex=True)

# 绘制温度
axs[0].plot(time, temp, marker='o', color='r', label='Test Point 2')
axs[0].set_ylabel('Temperature (°C)')
axs[0].set_title('Environmental Data over Time #2')
axs[0].legend()
axs[0].grid(True)

# 绘制湿度
axs[1].plot(time, hum, marker='o', color='b', label='Test Point 2')
axs[1].set_ylabel('Humidity (%)')
axs[1].legend()
axs[1].grid(True)

# 绘制光照强度
axs[2].plot(time, lux, marker='o', color='g', label='Test Point 2')
axs[2].set_ylabel('Lux')
axs[2].legend()
axs[2].grid(True)

# 绘制气压
axs[3].plot(time, pressure, marker='o', color='purple', label='Test Point 2')
axs[3].set_ylabel('Pressure (hPa)')
axs[3].legend()
axs[3].grid(True)

# 绘制高度
axs[4].plot(time, height, marker='o', color='orange', label='Test Point 2')
axs[4].set_ylabel('Height (m)')
axs[4].set_xlabel('Time (min)')
axs[4].legend()
axs[4].grid(True)

# 调整布局
plt.tight_layout()
# 显示图形
plt.show()