# Greenhouse Environment Remote Monitoring System

This repository contains the open-source code for a greenhouse environment remote monitoring system developed as a bachelor's thesis project. The system uses an ESP32S3 microcontroller, programmed in MicroPython, to monitor temperature, humidity, light intensity, and atmospheric pressure in a greenhouse. It supports real-time data display on OLED screens, remote monitoring via Bemfa Cloud, and user interaction through a mobile app and matrix keyboard.

## Features
- **Sensors**: DHT22 (temperature & humidity), BMP280 (pressure & altitude), light sensors.
- **Microcontroller**: ESP32S3 with Wi-Fi for cloud connectivity.
- **Display**: Dual OLED screens for real-time data visualization.
- **Remote Control**: Mobile app integration with Bemfa Cloud for monitoring and controlling devices (e.g., tap, buzzer).
- **Alarms**: Audio-visual alarms (buzzer and LED) triggered by threshold violations.
- **User Input**: Matrix keyboard for parameter adjustments.

## Hardware Requirements
- ESP32S3 development board
- DHT22 temperature and humidity sensor
- BMP280 barometric pressure sensor
- Light intensity sensor
- Dual OLED displays (I2C interface)
- Matrix keyboard
- Buzzer and LEDs (red, green, status)
- Wi-Fi network for cloud connectivity

## Software Requirements
- MicroPython firmware for ESP32S3
- Thonny IDE for development
- Bemfa Cloud account for remote monitoring



## Usage
- Power on the ESP32S3 to start monitoring.
- View real-time data on OLED displays.
- Use the matrix keyboard to adjust thresholds.
- Access remote data and control devices via the Bemfa Cloud mobile app.
- Alarms trigger automatically when parameters exceed set limits.






