from machine import Pin, I2C, PWM, ADC
from ssd1306 import SSD1306_I2C
import dht, time, math
import socket
import network
import machine
import json  # 导入json库
import urequests #连接后，可以使用 urequests 库发送HTTP和HTTPS请求
import ujson

# ========== 参数配置 ==========
# 全局变量用于存储传感器数据
temp1_val = None
hum1_val = None
lux1_val = None
temp2_val = None
hum2_val = None
lux2_val = None
# 全局变量
show_threshold = False  # 初始为正常参数显示模式
# 传感器阈值
TEMP_UPPER_LIMIT = 30.0
TEMP_LOWER_LIMIT = 15.0
HUMIDITY_UPPER_LIMIT = 70.0
HUMIDITY_LOWER_LIMIT = 30.0

# 矩阵键盘配置
ROW_PINS = [38, 37, 36, 35]
row_pins = [Pin(pin, Pin.OUT) for pin in ROW_PINS]
COL_PINS = [39, 40, 41, 42]
col_pins = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in COL_PINS]
KEYBOARD_MATRIX = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]
KEY_FUNCTIONS = {
    "1": ("TEMP_UPPER", "+"),
    "2": ("TEMP_UPPER", "-"),
    "3": ("TEMP_LOWER", "+"),
    "A": ("TEMP_LOWER", "-"),
    "4": ("HUMIDITY_UPPER", "+"),
    "5": ("HUMIDITY_UPPER", "-"),
    "6": ("HUMIDITY_LOWER", "+"),
    "B": ("HUMIDITY_LOWER", "-"),
    "7": ("LUX_UPPER", "+"),
    "8": ("LUX_UPPER", "-"),
    "9": ("LUX_LOWER", "+"),
    "C": ("LUX_LOWER", "-"),
    "*": ("PRINT", None),
    "0": ("RESET", None),
    "#": ("SWITCH", None),
    "D": ("BUZZER", None)
}

# 光敏传感器参数
GAMMA = 0.7
RL10 = 50
Ro = 10000  # 分压电阻10k
Vcc = 3.3  # 电源电压
LUX_LOWER_LIMIT = 100  # 光照下限阈值(lux)
LUX_UPPER_LIMIT = 10000  # 光照上限阈值(lux)

# 硬件引脚（ESP32-S3）
PIN_DHT1 = 11
PIN_DHT2 = 12
PIN_LIGHT1_AO = 8
PIN_LIGHT1_DO = 7
PIN_LIGHT2_AO = 18
PIN_LIGHT2_DO = 15
PIN_BUZZER = 13
PIN_LED_R = 4
PIN_LED_G = 6
PIN_STATUS_LED = 5

# OLED I2C配置
I2C0_SCL = 9
I2C0_SDA = 10
I2C1_SCL = 1
I2C1_SDA = 2

# 巴法云配置
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""
CLIENT_ID = "5bcdd97db89144929f1594d50f7fc29e"
serverIP = 'http://apis.bemfa.com/va/getmsg'    # Http API地址
SERVER_IP = 'bemfa.com'
SERVER_PORT = 8344
TOPIC_TEMP_1 = 'temp004'  # 传感器1温度 (用作传感器1的统一主题)
# TOPIC_HUMI_1 = 'humi004'   # 传感器1湿度
TOPIC_TEMP_2 = 'temp2004'  # 传感器2温度 (用作传感器2的统一主题)
TOPIC_TEMP_3 = 'temp3004'  # (用作各类阈值的统一主题)
TOPIC_TEMP_4='temp4004'
# TOPIC_HUMI_2 = 'humi2004'  # 传感器2湿度
# TOPIC_LIGHT1 = 'light004'  # 光照1
# TOPIC_LIGHT2 = 'light2004' # 光照2
TOPIC_ALARM = 'alarm004'  # 报警主题
ALARM_INTERVAL = 10  # 报警间隔(秒)

# ========== 硬件初始化 ==========
i2c0 = I2C(0, scl=Pin(I2C0_SCL), sda=Pin(I2C0_SDA), freq=400000)
i2c1 = I2C(1, scl=Pin(I2C1_SCL), sda=Pin(I2C1_SDA), freq=400000)
oled1 = SSD1306_I2C(128, 64, i2c0, addr=0x3C)
oled2 = SSD1306_I2C(128, 64, i2c1, addr=0x3D)

dht1 = dht.DHT22(Pin(PIN_DHT1))
dht2 = dht.DHT22(Pin(PIN_DHT2))
light1_ao = ADC(Pin(PIN_LIGHT1_AO))
light1_ao.atten(ADC.ATTN_11DB)  # 设置0-3.3V量程
light1_do = Pin(PIN_LIGHT1_DO, Pin.IN)
light2_ao = ADC(Pin(PIN_LIGHT2_AO))
light2_ao.atten(ADC.ATTN_11DB)
light2_do = Pin(PIN_LIGHT2_DO, Pin.IN)

buzzer = PWM(Pin(PIN_BUZZER), freq=1000, duty=0)
led_r = Pin(PIN_LED_R, Pin.OUT, value=0)  # 初始状态
led_g = Pin(PIN_LED_G, Pin.OUT, value=0)
status_led = Pin(PIN_STATUS_LED, Pin.OUT, value=0)
tap_status = "off"  # 初始状态为关闭
buzzer_on = False
tcp_client = None
last_alarm_time = 0


# 键盘控制函数
def adjust_value(param, operation):
    """根据操作调整参数值并打印状态"""
    global TEMP_UPPER_LIMIT, TEMP_LOWER_LIMIT, HUMIDITY_UPPER_LIMIT, HUMIDITY_LOWER_LIMIT, LUX_UPPER_LIMIT, LUX_LOWER_LIMIT

    # 温度参数调整
    if param == "TEMP_UPPER":
        TEMP_UPPER_LIMIT = min(TEMP_UPPER_LIMIT + 1, 50.0) if operation == "+" else max(TEMP_UPPER_LIMIT - 1, 10.0)
        print(f"温度上限: {TEMP_UPPER_LIMIT}℃")
    elif param == "TEMP_LOWER":
        TEMP_LOWER_LIMIT = min(TEMP_LOWER_LIMIT + 1, 30.0) if operation == "+" else max(TEMP_LOWER_LIMIT - 1, 5.0)
        print(f"温度下限: {TEMP_LOWER_LIMIT}℃")

    # 湿度参数调整
    elif param == "HUMIDITY_UPPER":
        HUMIDITY_UPPER_LIMIT = min(HUMIDITY_UPPER_LIMIT + 5, 95.0) if operation == "+" else max(
            HUMIDITY_UPPER_LIMIT - 5, 20.0)
        print(f"湿度上限: {HUMIDITY_UPPER_LIMIT}%")
    elif param == "HUMIDITY_LOWER":
        HUMIDITY_LOWER_LIMIT = min(HUMIDITY_LOWER_LIMIT + 5, 80.0) if operation == "+" else max(
            HUMIDITY_LOWER_LIMIT - 5, 10.0)
        print(f"湿度下限: {HUMIDITY_LOWER_LIMIT}%")

    # 光照参数调整
    elif param == "LUX_UPPER":
        LUX_UPPER_LIMIT = min(LUX_UPPER_LIMIT + 1000, 20000) if operation == "+" else max(LUX_UPPER_LIMIT - 1000, 500)
        print(f"光照上限: {LUX_UPPER_LIMIT}lux")
    elif param == "LUX_LOWER":
        LUX_LOWER_LIMIT = min(LUX_LOWER_LIMIT + 100, 5000) if operation == "+" else max(LUX_LOWER_LIMIT - 1000, 100)
        print(f"光照下限: {LUX_LOWER_LIMIT}lux")

    # 打印所有参数
    elif param == "PRINT":
        show_threshold = not show_threshold
        print(f"切换显示模式: {'阈值显示' if show_threshold else '正常参数显示'}")
        print("当前参数值:")
        print(f"温度上限: {TEMP_UPPER_LIMIT}℃, 温度下限: {TEMP_LOWER_LIMIT}℃")
        print(f"湿度上限: {HUMIDITY_UPPER_LIMIT}%, 湿度下限: {HUMIDITY_LOWER_LIMIT}%")
        print(f"光照上限: {LUX_UPPER_LIMIT}lux, 光照下限: {LUX_LOWER_LIMIT}lux")

    # 重置所有参数到默认值
    elif param == "RESET":
        global TEMP_UPPER_LIMIT, TEMP_LOWER_LIMIT, HUMIDITY_UPPER_LIMIT, HUMIDITY_LOWER_LIMIT, LUX_UPPER_LIMIT, LUX_LOWER_LIMIT
        TEMP_UPPER_LIMIT = 30.0
        TEMP_LOWER_LIMIT = 15.0
        HUMIDITY_UPPER_LIMIT = 70.0
        HUMIDITY_LOWER_LIMIT = 30.0
        LUX_UPPER_LIMIT = 10000
        LUX_LOWER_LIMIT = 100
        print("所有参数已重置为默认值。")

    # 切换程序（可根据需要实现）
    elif param == "SWITCH":
        print("切换")
        global tap_status
        if led_g.value() == 1 and led_r.value() == 0:  # 关龙头
            led_g.value(0)
            led_r.value(1)
            tap_status = "off"
        else:  # 开龙头
            led_g.value(1)
            led_r.value(0)
            tap_status = "on"
        print(f"龙头状态: {tap_status}")
    elif param == "BUZZER":
        print("切换蜂鸣器")
        global buzzer_on
        buzzer_on = not buzzer_on
        if buzzer_on:
            buzzer.duty(512)  # 打开蜂鸣器
        else:
            buzzer.duty(0)  # 关闭蜂鸣器
        print('状态:', 'on' if buzzer_on else 'off')


def handle_keyboard():
    global show_threshold  # 声明使用全局变量
    """处理键盘输入"""
    for i, row in enumerate(row_pins):
        for r in row_pins:
            r.value(0)
        row.value(1)
        time.sleep_ms(20)
        for j, col in enumerate(col_pins):
            if col.value() == 1:
                key = KEYBOARD_MATRIX[i][j]
                print(f"按键: {key} 被按下")
                if key == "*":  # 按键 '*' 切换显示模式
                    show_threshold = not show_threshold
                    print(f"切换显示模式: {'阈值显示' if show_threshold else '正常参数显示'}")
                elif key in KEY_FUNCTIONS:  # 处理其他按键
                    param, operation = KEY_FUNCTIONS[key]
                    adjust_value(param, operation)
                return
        row.value(0)
    time.sleep(0.1)


def display_parameters(oled1, oled2):
    """在两个 OLED 上显示参数"""
    global show_threshold  # 声明使用全局变量
    oled1.fill(0)
    oled2.fill(0)

    if show_threshold:
        # 显示阈值
        oled1.text(f"Temp Up: {TEMP_UPPER_LIMIT} C", 0, 0)
        oled1.text(f"Temp Low: {TEMP_LOWER_LIMIT} C", 0, 10)
        oled1.text(f"Hum Up: {HUMIDITY_UPPER_LIMIT}%", 0, 20)
        oled1.text(f"Hum Low: {HUMIDITY_LOWER_LIMIT}%", 0, 30)
        oled1.text(f"Lux Up: {LUX_UPPER_LIMIT}lux", 0, 40)
        oled1.text(f"Lux Low: {LUX_LOWER_LIMIT}lux", 0, 50)

        oled2.text(f"Temp Up: {TEMP_UPPER_LIMIT} C", 0, 0)
        oled2.text(f"Temp Low: {TEMP_LOWER_LIMIT} C", 0, 10)
        oled2.text(f"Hum Up: {HUMIDITY_UPPER_LIMIT}%", 0, 20)
        oled2.text(f"Hum Low: {HUMIDITY_LOWER_LIMIT}%", 0, 30)
        oled2.text(f"Lux Up: {LUX_UPPER_LIMIT}lux", 0, 40)
        oled2.text(f"Lux Low: {LUX_LOWER_LIMIT}lux", 0, 50)
    else:
        # 显示正常参数
        oled1.text(f"Temp1: {temp1_val if temp1_val else 'N/A'}C", 0, 0)
        oled1.text(f"Hum1: {hum1_val if hum1_val else 'N/A'}%", 0, 10)
        oled1.text(f"Lux1: {lux1_val if lux1_val else 'N/A'}lux", 0, 20)

        oled2.text(f"Temp2: {temp2_val if temp2_val else 'N/A'}C", 0, 0)
        oled2.text(f"Hum2: {hum2_val if hum2_val else 'N/A'}%", 0, 10)
        oled2.text(f"Lux2: {lux2_val if lux2_val else 'N/A'}lux", 0, 20)

    oled1.show()
    oled2.show()


# ========== 光照计算函数（修正版） ==========
def calculate_lux(adc_sensor):
    """精确计算光照强度(Lux) - 修正版"""
    try:
        # 读取ADC原始值（0-4095）
        raw = adc_sensor.read()
        if raw == 0:
            return 0.0  # 避免除以零

        # 转换为电压（0-3.3V）
        voltage = raw / 4095.0 * Vcc

        # 电压接近Vcc时表示光线极弱
        if voltage >= 3.2:
            return 0.0

        # 计算LDR电阻（单位：kΩ）
        resistance = Ro * voltage / (Vcc - voltage)

        # 避免负值或零值
        if resistance <= 0:
            return 0.0

        # 使用LDR特性曲线公式
        lux = math.pow((RL10 * 1000 * math.pow(10, GAMMA) / resistance), (1 / GAMMA))

        # 限制输出范围（0-100,000 lux）
        return min(lux, 100000.0)

    except Exception as e:
        print("光照计算错误:", e)
        return 0.0


def check_light_status(adc_sensor, digital_sensor):
    """检测光照状态"""
    lux = calculate_lux(adc_sensor)
    digital_val = digital_sensor.value()  # 0表示有光，1表示无光
    return lux < LUX_LOWER_LIMIT or lux > LUX_UPPER_LIMIT or digital_val == 0


# ========== 网络通信函数 ==========
def wifi_connect():
    """连接WiFi网络"""
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('Connecting to WiFi...')
        sta_if.active(True)
        sta_if.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(20):
            if sta_if.isconnected():
                print('WiFi connected:', sta_if.ifconfig())
                return True
            time.sleep(0.5)
    return False


def tcp_connect():
    """连接TCP服务器"""
    global tcp_client
    try:
        addr = socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1]
        tcp_client = socket.socket()
        tcp_client.connect(addr)
        tcp_client.settimeout(5)
        # 订阅必要的主题
        subs = [TOPIC_TEMP_1, TOPIC_TEMP_2, TOPIC_TEMP_3,TOPIC_ALARM]
        for topic in subs:
            cmd = f'cmd=1&uid={CLIENT_ID}&topic={topic}\r\n'
            tcp_client.send(cmd.encode())
        status_led.value(1)
        return True
    except Exception as e:
        print('TCP connect failed:', e)
        return False


def send_data(topic, *values):
    """发送数据到云端，可以发送多个数据"""
    global tcp_client
    try:
        if tcp_client:
            msg = "#".join(map(str, values))  # 将多个值转换为字符串并用'#'连接
            cmd = f'cmd=2&uid={CLIENT_ID}&topic={topic}&msg=#{msg}#\r\n'
            tcp_client.send(cmd.encode())
            # print(f"Data sent to {topic}: {values}")
            return True
    except Exception as e:
        print('Send error:', e)
        if tcp_client:
            tcp_client.close()
            tcp_client = None
    return False


# ========== 报警功能 ==========
def send_alarm(sensor_id, alarm_type):
    """发送报警信息"""
    global last_alarm_time
    if time.time() - last_alarm_time > ALARM_INTERVAL:
        message = f"{sensor_id}-{alarm_type}"
        if send_data(TOPIC_ALARM, message):
            last_alarm_time = time.time()
            return True
    return False


def trigger_alarm(alarm_type):
    # 如果蜂鸣器已关闭，跳过报警
    if not buzzer_on:
        return
    """触发蜂鸣器报警"""
    patterns = {
        'TEMP': (2000, 300, 3),  # 温度报警
        'HUM': (1000, 500, 2),  # 湿度报警
        'LIGHT_LOW': (600, 800, 2),  # 光照过低报警
        'LIGHT_HIGH': (1200, 300, 4),  # 光照过高报警
        'ERROR': (500, 1000, 1)  # 错误报警
    }
    freq, duration, repeat = patterns.get(alarm_type, (1000, 300, 1))
    for _ in range(repeat):
        buzzer.freq(freq)
        buzzer.duty(512)
        time.sleep_ms(duration)
        buzzer.duty(0)
        if repeat > 1:
            time.sleep_ms(200)


# ========== 传感器检测 ==========
def check_sensor(sensor, sensor_id):
    """检查传感器数据并触发报警"""
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()

        # 温度检查
        if temp > TEMP_UPPER_LIMIT or temp < TEMP_LOWER_LIMIT:
            trigger_alarm("TEMP")
            send_alarm(sensor_id, "TEMP")
            return temp, hum, 'temp'

        # 湿度检查
        if hum > HUMIDITY_UPPER_LIMIT or hum < HUMIDITY_LOWER_LIMIT:
            trigger_alarm("HUM")
            send_alarm(sensor_id, "HUM")
            return temp, hum, 'hum'

        return temp, hum, None
    except Exception as e:
        print(f"Sensor {sensor_id} error:", e)
        trigger_alarm("ERROR")
        send_alarm(sensor_id, "ERROR")
        return None, None, 'error'


# ========== LED控制逻辑（修正版） ==========
def update_leds(temp1, temp2):
    global tap_status
    """更新LED状态"""
    temp1_ok = temp1 is not None and TEMP_LOWER_LIMIT <= temp1 <= TEMP_UPPER_LIMIT
    temp2_ok = temp2 is not None and TEMP_LOWER_LIMIT <= temp2 <= TEMP_UPPER_LIMIT

    if temp1_ok and temp2_ok:
        led_r.value(1)  # 龙头关：红灯亮
        led_g.value(0)
        tap_status = 'off'
    else:
        led_r.value(0)
        led_g.value(1)  # 龙头开：绿灯亮
        tap_status = 'on'


# ========== OLED显示 ==========
def display_normal(oled, sensor_id, temp, hum, lux):
    """OLED显示传感器数据"""
    oled.fill(0)
    # 标题栏
    oled.text(f'S#{sensor_id}', 0, 0)
    oled.text(f'L:{int(lux)}', 50, 0)
    oled.hline(0, 12, 128, 1)

    # 温湿度数据
    oled.text('Temp:', 0, 20)
    oled.text(f'{temp:.1f} C', 70, 20)

    oled.text('Humid:', 0, 40)
    oled.text(f'{hum:.1f} %', 70, 40)

    # 阈值警告
    if temp is not None:
        if temp > TEMP_UPPER_LIMIT or temp < TEMP_LOWER_LIMIT:
            oled.text('!', 115, 20)
    if hum is not None:
        if hum > HUMIDITY_UPPER_LIMIT or hum < HUMIDITY_LOWER_LIMIT:
            oled.text('!', 115, 40)
    if lux < LUX_LOWER_LIMIT or lux > LUX_UPPER_LIMIT:
        oled.text('!', 115, 0)  # 光照警告

    oled.show()


# ========== 消息处理函数 ==========
def handle_tcp_message():
    
    global tap_status,buzzer_on
    try:
        response = urequests.get(serverIP+'?uid='+CLIENT_ID+'&topic='+TOPIC_TEMP_4+'&type=3')
        #print(response.text)
        parsed = ujson.loads(response.text)
        #print(parsed["data"][0]['msg'])
        data=parsed["data"][0]
        msg=data['msg']
        print(msg)
        if msg=="tapon":
            led_g.value(1)
            led_r.value(0)
            tap_status='on'
        elif msg=="tapoff": 
            led_g.value(0)
            led_r.value(1)
            tap_status='off'
        elif msg=="buzzeron": 
            buzzer.duty(512)
            buzzer_on=True
        elif msg=="buzzeroff": 
            buzzer.duty(0)
            buzzer_on=False


    except UnicodeDecodeError:
        print("Error decoding TCP message.")

def set_limit_message():
    global TEMP_UPPER_LIMIT, TEMP_LOWER_LIMIT, HUMIDITY_UPPER_LIMIT, HUMIDITY_LOWER_LIMIT, LUX_UPPER_LIMIT, LUX_LOWER_LIMIT
    try:
        response = urequests.get(serverIP+'?uid='+CLIENT_ID+'&topic='+TOPIC_TEMP_3+'&type=3')
        #print(response.text)
        parsed = ujson.loads(response.text)
        #print(parsed["data"][0]['msg'])
        data=parsed["data"][0]
        msg=data['msg']
        print(msg)
        message = msg

        if '=' in message:
            param_name, value_str = message.split('=', 1)
            try:
                value = float(value_str)
                if param_name == 'SETTEMPUPPER':
                    
                    TEMP_UPPER_LIMIT = min(max(value, 10.0), 50.0)
                    print(f"设置温度上限: {TEMP_UPPER_LIMIT}")
                elif param_name == 'SETTEMPLOWER':

                    TEMP_LOWER_LIMIT = min(max(value, 5.0), 30.0)
                    print(f"设置温度下限: {TEMP_LOWER_LIMIT}")
                elif param_name == 'SETHUMIDUPPER':

                    HUMIDITY_UPPER_LIMIT = min(max(value, 20.0), 95.0)
                    print(f"设置湿度上限: {HUMIDITY_UPPER_LIMIT}")
                elif param_name == 'SETHUMIDLOWER':

                    HUMIDITY_LOWER_LIMIT = min(max(value, 10.0), 80.0)
                    print(f"设置湿度下限: {HUMIDITY_LOWER_LIMIT}")
                elif param_name == 'SETLIGHTUPPER':
                    
                    LUX_UPPER_LIMIT = min(max(int(value), 500), 20000)
                    print(f"设置光照上限: {LUX_UPPER_LIMIT}")
                elif param_name == 'SETLIGHTLOWER':
                    
                    LUX_LOWER_LIMIT = min(max(int(value), 100), 5000)
                    print(f"设置光照下限: {LUX_LOWER_LIMIT}")
                else:
                    print(f"未知的阈值参数: {param_name}")  
            except ValueError:
                print(f"无效的数值: {value_str} for {param_name}")
        elif 'RESTORE' in message:
            TEMP_UPPER_LIMIT = 30.0
            TEMP_LOWER_LIMIT = 15.0
            HUMIDITY_UPPER_LIMIT = 70.0
            HUMIDITY_LOWER_LIMIT = 30.0
            LUX_UPPER_LIMIT = 10000
            LUX_LOWER_LIMIT = 100
            print("所有参数已重置为默认值。")

        
    
        
    except UnicodeDecodeError:
        print("Error decoding TCP message.")




# ========== 新增函数用于更新OLED显示 (因为handle_tcp_message中无法直接访问oled1和oled2) ==========
def update_display():
    global temp1_val, hum1_val, lux1_val, temp2_val, hum2_val, lux2_val
    display_normal(oled1, 1, temp1_val or 0, hum1_val or 0, lux1_val)
    display_normal(oled2, 2, temp2_val or 0, hum2_val or 0, lux2_val)


# ========== 主程序 ==========
def main():
    global tcp_client
    global temp1_val, hum1_val, lux1_val, temp2_val, hum2_val, lux2_val

    # 初始化显示
    oled1.fill(0)
    oled1.text("Initializing...", 0, 20)
    oled1.show()
    oled2.fill(0)
    oled2.text("Initializing...", 0, 20)
    oled2.show()

    # 连接网络
    if not wifi_connect():
        oled1.fill(0)
        oled1.text("WiFi Error!", 0, 30)
        oled1.show()
        return

    # 连接TCP
    if not tcp_connect():
        oled1.fill(0)
        oled1.text("TCP Error!", 0, 30)
        oled1.show()
        return

    last_upload = time.time()
    while True:
        # 处理键盘输入
        handle_keyboard()
        # 读取传感器
        lux1_val = calculate_lux(light1_ao)
        lux2_val = calculate_lux(light2_ao)

        temp1_val, hum1_val, _ = check_sensor(dht1, 1)
        temp2_val, hum2_val, _ = check_sensor(dht2, 2)

        # 根据显示模式选择显示内容
        # display_parameters(oled1, oled2)
        # 处理来自 App Inventor 客户端的连接和数据 (非阻塞方式)

        if tcp_client:
            try:
                data = tcp_client.recv(1024)
                
                if data:
                    message = data.decode('utf-8').strip()
                    if message.startswith('{') and message.endswith('}'):
                        '''
                        handle_control_message(message)
                        '''
                    elif message.startswith('SET'):
                        ... # 处理阈值设置消息
                handle_tcp_message()
                set_limit_message()

            except:
                pass  # 忽略接收超时
        # 根据显示模式选择显示内容
        if show_threshold:
            display_parameters(oled1, oled2)  # 同时传递 oled1 和 oled2
        else:

            # OLED显示
            display_normal(oled1, 1, temp1_val or 0, hum1_val or 0, lux1_val)
            display_normal(oled2, 2, temp2_val or 0, hum2_val or 0, lux2_val)
        # 光照报警
        if lux1_val < LUX_LOWER_LIMIT or lux1_val > LUX_UPPER_LIMIT:
            alarm_type = "LIGHT_LOW" if lux1_val < LUX_LOWER_LIMIT else "LIGHT_HIGH"
            trigger_alarm(alarm_type)
            send_alarm(1, alarm_type)

        if lux2_val < LUX_LOWER_LIMIT or lux2_val > LUX_UPPER_LIMIT:
            alarm_type = "LIGHT_LOW" if lux2_val < LUX_LOWER_LIMIT else "LIGHT_HIGH"
            trigger_alarm(alarm_type)
            send_alarm(2, alarm_type)
        # 更新LED状态
        update_leds(temp1_val, temp2_val)

        # 数据上传（每5秒）
        if time.time() - last_upload > 5:
            # 上传传感器 1 数据
            data1_upload = []
            if temp1_val is not None:
                data1_upload.append(f"{temp1_val:.1f}")
            if hum1_val is not None:
                data1_upload.append(f"{hum1_val:.1f}")
            data1_upload.append(str(int(lux1_val)))
            data1_upload.append(tap_status)  # 添加 tap_status
            send_data(TOPIC_TEMP_1, *data1_upload)

            # 上传传感器 2 数据
            data2_upload = []
            if temp2_val is not None:
                data2_upload.append(f"{temp2_val:.1f}")
            if hum2_val is not None:
                data2_upload.append(f"{hum2_val:.1f}")
            data2_upload.append(str(int(lux2_val)))
            data2_upload.append(tap_status)  # 添加 tap_status
            send_data(TOPIC_TEMP_2, *data2_upload)

            # 上传阈值数据到 TOPIC_TEMP_3
            threshold_data = [
                f"{TEMP_UPPER_LIMIT:.1f}",
                f"{TEMP_LOWER_LIMIT:.1f}",
                f"{HUMIDITY_UPPER_LIMIT:.1f}",
                f"{HUMIDITY_LOWER_LIMIT:.1f}",
                str(int(LUX_UPPER_LIMIT)),
                str(int(LUX_LOWER_LIMIT))
            ]
            send_data(TOPIC_TEMP_3, *threshold_data)
            last_upload = time.time()
        
        time.sleep(1)
        


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        # 系统关闭清理
        buzzer.duty(0)
        led_g.value(0)
        led_r.value(0)
        status_led.value(0)
        if tcp_client:
            tcp_client.close()
        oled1.fill(0)
        oled2.fill(0)
        oled1.text("System Off", 0, 30)
        oled2.text("System Off", 0, 30)
        oled1.show()
        oled2.show()