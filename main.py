from machine import Pin, I2C, PWM, ADC, SoftI2C
from ssd1306 import SSD1306_I2C
import dht, time, math
import socket
import network
import machine
import json
import urequests
import ujson
import bmp280

# ========== 参数配置 ==========
# 全局变量用于存储传感器数据
temp1_val = None
hum1_val = None
lux1_val = None
pressure1_val = None
height1_val = None
temp2_val = None
hum2_val = None
lux2_val = None
pressure2_val = None
height2_val = None

# 交互与状态变量
show_threshold = False
tap_status = "off"
buzzer_on = False
last_switch_time = 0
SWITCH_INTERVAL = 2
manual_override = False
manual_override_timeout = 30
last_manual_time = 0
last_alarm_time = 0
last_temp_alarm_time = 0
last_handled_message = None  # 新增：缓存最近处理的控制消息
last_limit_message = None    # 新增：缓存最近处理的阈值消息
alarms=[]
# 数据记录变量
record_count = 0
MAX_RECORDS = 10
RECORD_INTERVAL = 600  # 10分钟（秒）
last_record_time = 0

# 传感器阈值
TEMP_UPPER_LIMIT = 30.0
TEMP_LOWER_LIMIT = 15.0
HUMIDITY_UPPER_LIMIT = 70.0
HUMIDITY_LOWER_LIMIT = 30.0
LUX_LOWER_LIMIT = 100
LUX_UPPER_LIMIT = 10000

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
    "1": ("TEMP_UPPER", "+"), "2": ("TEMP_UPPER", "-"), "3": ("TEMP_LOWER", "+"), "A": ("TEMP_LOWER", "-"),
    "4": ("HUMIDITY_UPPER", "+"), "5": ("HUMIDITY_UPPER", "-"), "6": ("HUMIDITY_LOWER", "+"), "B": ("HUMIDITY_LOWER", "-"),
    "7": ("LUX_UPPER", "+"), "8": ("LUX_UPPER", "-"), "9": ("LUX_LOWER", "+"), "C": ("LUX_LOWER", "-"),
    "*": ("PRINT", None), "0": ("RESET", None), "#": ("SWITCH", None), "D": ("BUZZER", None)
}

# 光敏传感器参数
GAMMA = 0.7
RL10 = 50
Ro = 10000
Vcc = 3.3

# 硬件引脚（ESP32-S3）
PIN_DHT1 = 11
PIN_DHT2 = 12
PIN_LIGHT1_AO = 8
PIN_LIGHT1_DO = 7
PIN_LIGHT2_AO = 10
PIN_LIGHT2_DO = 9
PIN_BUZZER = 13
PIN_LED_R = 4
PIN_LED_G = 6
PIN_STATUS_LED = 5

# OLED I2C配置
I2C0_SCL = 15
I2C0_SDA = 18
I2C1_SCL = 1
I2C1_SDA = 2

# 巴法云配置
WIFI_SSID = "Lover3"
WIFI_PASS = "hf201809"
CLIENT_ID = "5bcdd97db89144929f1594d50f7fc29e"
serverIP = 'http://apis.bemfa.com/va/getmsg'
SERVER_IP = 'bemfa.com'
SERVER_PORT = 8344
TOPIC_TEMP_1 = 'temp004'
TOPIC_TEMP_2 = 'temp2004'
TOPIC_TEMP_3 = 'temp3004'
TOPIC_TEMP_4 = 'temp4004'
TOPIC_TEMP_5 = 'temp5004'
TOPIC_ALARM = 'alarm004'
ALARM_INTERVAL = 1

# ========== 硬件初始化 ==========
try:
    i2c0_oled = I2C(0, scl=Pin(I2C0_SCL), sda=Pin(I2C0_SDA), freq=400000)
    i2c1_oled = I2C(1, scl=Pin(I2C1_SCL), sda=Pin(I2C1_SDA), freq=400000)
    oled1 = SSD1306_I2C(128, 64, i2c0_oled, addr=0x3C)
    oled2 = SSD1306_I2C(128, 64, i2c1_oled, addr=0x3C)

    bmp_i2c = SoftI2C(sda=Pin(16), scl=Pin(17))
    BMP1 = bmp280.BMP280(bmp_i2c)
    BMP2 = bmp280.BMP280(bmp_i2c)

    dht1 = dht.DHT22(Pin(PIN_DHT1))
    dht2 = dht.DHT22(Pin(PIN_DHT2))
    light1_ao = ADC(Pin(PIN_LIGHT1_AO))
    light1_ao.atten(ADC.ATTN_11DB)
    light1_do = Pin(PIN_LIGHT1_DO, Pin.IN)
    light2_ao = ADC(Pin(PIN_LIGHT2_AO))
    light2_ao.atten(ADC.ATTN_11DB)
    light2_do = Pin(PIN_LIGHT2_DO, Pin.IN)
    buzzer = PWM(Pin(PIN_BUZZER), freq=1000, duty=0)
    led_r = Pin(PIN_LED_R, Pin.OUT, value=1)
    led_g = Pin(PIN_LED_G, Pin.OUT, value=1)
    status_led = Pin(PIN_STATUS_LED, Pin.OUT, value=1)
    tcp_client = None
except Exception as e:
    print(f"Hardware initialization error: {e}")
    raise

# ========== 函数定义 ==========
def adjust_value(param, operation):
    global TEMP_UPPER_LIMIT, TEMP_LOWER_LIMIT, HUMIDITY_UPPER_LIMIT, HUMIDITY_LOWER_LIMIT, LUX_UPPER_LIMIT, LUX_LOWER_LIMIT
    global tap_status, last_switch_time, manual_override, last_manual_time, buzzer_on, show_threshold

    current_time = time.time()
    if param in ["SWITCH", "BUZZER"] and current_time - last_switch_time < SWITCH_INTERVAL:
        return

    if param == "TEMP_UPPER":
        old_value = TEMP_UPPER_LIMIT
        TEMP_UPPER_LIMIT = min(old_value + 1, 60.0) if operation == "+" else max(old_value - 1, 0.0)
        if TEMP_UPPER_LIMIT < TEMP_LOWER_LIMIT:
            TEMP_LOWER_LIMIT = TEMP_UPPER_LIMIT
            print(f"温度下限已同步调整为: {TEMP_LOWER_LIMIT}℃")
        print(f"温度上限: {TEMP_UPPER_LIMIT}℃")
    elif param == "TEMP_LOWER":
        old_value = TEMP_LOWER_LIMIT
        TEMP_LOWER_LIMIT = min(old_value + 1, 40.0) if operation == "+" else max(old_value - 1, -20.0)
        if TEMP_LOWER_LIMIT > TEMP_UPPER_LIMIT:
            TEMP_UPPER_LIMIT = TEMP_LOWER_LIMIT
            print(f"温度上限已同步调整为: {TEMP_UPPER_LIMIT}℃")
        print(f"温度下限: {TEMP_LOWER_LIMIT}℃")
    elif param == "HUMIDITY_UPPER":
        old_value = HUMIDITY_UPPER_LIMIT
        HUMIDITY_UPPER_LIMIT = min(old_value + 2, 95.0) if operation == "+" else max(old_value - 2, 20.0)
        if HUMIDITY_UPPER_LIMIT < HUMIDITY_LOWER_LIMIT:
            HUMIDITY_LOWER_LIMIT = HUMIDITY_UPPER_LIMIT
            print(f"湿度下限已同步调整为: {HUMIDITY_LOWER_LIMIT}%")
        print(f"湿度上限: {HUMIDITY_UPPER_LIMIT}%")
    elif param == "HUMIDITY_LOWER":
        old_value = HUMIDITY_LOWER_LIMIT
        HUMIDITY_LOWER_LIMIT = min(old_value + 2, 80.0) if operation == "+" else max(old_value - 2, 10.0)
        if HUMIDITY_LOWER_LIMIT > HUMIDITY_UPPER_LIMIT:
            HUMIDITY_UPPER_LIMIT = HUMIDITY_LOWER_LIMIT
            print(f"湿度上限已同步调整为: {HUMIDITY_UPPER_LIMIT}%")
        print(f"湿度下限: {HUMIDITY_LOWER_LIMIT}%")
    elif param == "LUX_UPPER":
        old_value = LUX_UPPER_LIMIT
        LUX_UPPER_LIMIT = min(old_value + 500, 20000) if operation == "+" else max(old_value - 500, 500)
        if LUX_UPPER_LIMIT < LUX_LOWER_LIMIT:
            LUX_LOWER_LIMIT = LUX_UPPER_LIMIT
            print(f"光照下限已同步调整为: {LUX_LOWER_LIMIT}lux")
        print(f"光照上限: {LUX_UPPER_LIMIT}lux")
    elif param == "LUX_LOWER":
        old_value = LUX_LOWER_LIMIT
        LUX_LOWER_LIMIT = min(old_value + 100, 5000) if operation == "+" else max(old_value - 100, 10)
        if LUX_LOWER_LIMIT > LUX_UPPER_LIMIT:
            LUX_UPPER_LIMIT = LUX_LOWER_LIMIT
            print(f"光照上限已同步调整为: {LUX_UPPER_LIMIT}lux")
        print(f"光照下限: {LUX_LOWER_LIMIT}lux")
    elif param == "PRINT":
        show_threshold = not show_threshold
        print(f"切换显示模式: {'阈值显示' if show_threshold else '正常参数显示'}")
        print("当前参数值:")
        print(f"温度上限: {TEMP_UPPER_LIMIT}℃, 温度下限: {TEMP_LOWER_LIMIT}℃")
        print(f"湿度上限: {HUMIDITY_UPPER_LIMIT}%, 湿度下限: {HUMIDITY_LOWER_LIMIT}%")
        print(f"光照上限: {LUX_UPPER_LIMIT}lux, 光照下限: {LUX_LOWER_LIMIT}lux")
    elif param == "RESET":
        TEMP_UPPER_LIMIT = 30.0
        TEMP_LOWER_LIMIT = 15.0
        HUMIDITY_UPPER_LIMIT = 70.0
        HUMIDITY_LOWER_LIMIT = 30.0
        LUX_UPPER_LIMIT = 10000
        LUX_LOWER_LIMIT = 100
        print("所有参数已重置为默认值。")
    elif param == "SWITCH":
        print("切换龙头 (按键优先级)")
        manual_override = True
        last_manual_time = current_time
        if tap_status == "on":
            tap_status = "off"
            led_g.value(1)
            led_r.value(0)
        else:
            tap_status = "on"
            led_g.value(0)
            led_r.value(1)
        last_switch_time = current_time
    elif param == "BUZZER":
        print("切换蜂鸣器")
        buzzer_on = not buzzer_on
        if buzzer_on:
            buzzer.duty(512)
            trigger_alarm(["MANUAL"])  # 手动触发报警
        else:
            buzzer.duty(0)
        print('状态:', 'on' if buzzer_on else 'off')
        last_switch_time = current_time

def handle_keyboard():
    global show_threshold
    for i, row in enumerate(row_pins):
        for r in row_pins:
            r.value(0)
        row.value(1)
        time.sleep_ms(20)
        for j, col in enumerate(col_pins):
            if col.value() == 1:
                key = KEYBOARD_MATRIX[i][j]
                print(f"按键: {key} 被按下")
                if key == "*":
                    show_threshold = not show_threshold
                    print(f"切换显示模式: {'阈值显示' if show_threshold else '正常参数显示'}")
                elif key in KEY_FUNCTIONS:
                    param, operation = KEY_FUNCTIONS[key]
                    adjust_value(param, operation)
                return
        row.value(0)
    time.sleep(0.1)

def display_parameters(oled1, oled2):
    oled1.fill(0)
    oled2.fill(0)
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
    oled1.show()
    oled2.show()

def calculate_lux(adc_sensor):
    try:
        raw = adc_sensor.read()
        if raw == 0:
            return 0.0
        voltage = raw / 4095.0 * Vcc
        if voltage >= 3.2:
            return 0.0
        resistance = Ro * voltage / (Vcc - voltage)
        if resistance <= 0:
            return 0.0
        lux = math.pow((RL10 * 1000 * math.pow(10, GAMMA) / resistance), (1 / GAMMA))
        return min(lux, 100000.0)
    except Exception as e:
        print("光照计算错误:", e)
        return 0.0

def check_light_status(adc_sensor, digital_sensor):
    lux = calculate_lux(adc_sensor)
    digital_val = digital_sensor.value()
    return lux < LUX_LOWER_LIMIT or lux > LUX_UPPER_LIMIT or digital_val == 0

def wifi_connect():
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
    global tcp_client
    try:
        addr = socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1]
        tcp_client = socket.socket()
        tcp_client.connect(addr)
        tcp_client.settimeout(5)
        subs = [TOPIC_TEMP_1, TOPIC_TEMP_2, TOPIC_TEMP_3, TOPIC_ALARM]
        for topic in subs:
            cmd = f'cmd=1&uid={CLIENT_ID}&topic={topic}\r\n'
            tcp_client.send(cmd.encode())
        status_led.value(0)
        return True
    except Exception as e:
        print('TCP connect failed:', e)
        status_led.value(1)
        if tcp_client:
            tcp_client.close()
            tcp_client = None
        return False

def send_data(topic, *values):
    global tcp_client
    try:
        if tcp_client:
            msg = "#".join(map(str, values))
            cmd = f'cmd=2&uid={CLIENT_ID}&topic={topic}&msg=#{msg}#\r\n'
            tcp_client.send(cmd.encode())
            return True
    except Exception as e:
        print('Send error:', e)
        if tcp_client:
            tcp_client.close()
            tcp_client = None
    return False

def send_alarm(alarms):
    global last_alarm_time
    if time.time() - last_alarm_time > ALARM_INTERVAL and alarms:
        message = "\t".join(alarms)
        if send_data(TOPIC_ALARM, message):
            last_alarm_time = time.time()
            return True
    return False

def trigger_alarm(alarm_types):
    global last_temp_alarm_time
    global alarms
    if not alarm_types:  # 如果没有报警类型，直接返回
        return

#     # 冷却时间检查
#     current_time = time.time()
#     if current_time - last_temp_alarm_time < ALARM_COOLDOWN:
#         print(f"[alarm] 冷却中，跳过报警 (剩余时间: {ALARM_COOLDOWN - (current_time - last_temp_alarm_time):.1f}s)")
#         return

    # 基本报警模式：频率 (Hz), 持续时间 (ms), 重复次数
    patterns = {
        'TEMP': (700, 300, 1),        # 哒（单短音，700 Hz，300 ms）
        'HUM': (700, 300, 2),         # 哒-哒（两短音，700 Hz，300 ms）
        'LIGHT_LOW':(1000, 300, 3),  # 滴-滴-滴-滴（三短音，1000 Hz，300 ms）
        'LIGHT_HIGH': (1000, 300, 4),  # 滴-滴-滴-滴（四短音，1000 Hz，300 ms）
        'ERROR': (500, 1000, 1),       # 哒（单长音，500 Hz，1000 ms）
        'MANUAL': (500, 1000, 2),      # 哒-哒（两长音，500 Hz，1000 ms）
        'OTHERS': (500, 1000, 3)       # 哒-哒（三长音，500 Hz，1000 ms）
    }

    # 优先级顺序（仅用于单一报警时选择模式）
    priority = ['TEMP', 'HUM', 'LIGHT_LOW', 'LIGHT_HIGH', 'MANUAL', 'ERROR']
    
    # 如果是多种参数报警，合并为 OTHERS
#     if len(alarm_types) > 1:
#         alarm_description = "OTHERS"
#         freq, duration, repeat = patterns['OTHERS']

    # 单一报警，按优先级选择模式
    if len(alarms)>1:
        alarm_description = "OTHERS"
        freq, duration, repeat = patterns['OTHERS']
        
    else:        
        primary_alarm = None
        for alarm in priority:
            if alarm in alarm_types:
                primary_alarm = alarm
                freq, duration, repeat = patterns[primary_alarm]
    
        alarm_description = primary_alarm
        if not primary_alarm:
            print(f"[alarm] 无有效报警类型: {alarm_types}")
            return

    
    

    # 触发报警
    print(f"[alarm] 触发报警: {alarm_description}, {freq} Hz, {duration} ms, {repeat} 次")
    for _ in range(repeat):
        buzzer.freq(freq)
        buzzer.duty(512)
        buzzer_on=True
        time.sleep_ms(duration)
        buzzer.duty(0)
        buzzer_on=False
        time.sleep_ms(150)

    #last_temp_alarm_time = current_time

def check_sensor(sensor, sensor_id):
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
        alarms = []
        if temp > TEMP_UPPER_LIMIT:
            alarms.append(f"{sensor_id}-温度过高")
            trigger_alarm("TEMP")
        if temp < TEMP_LOWER_LIMIT:
            alarms.append(f"{sensor_id}-温度过低")
            trigger_alarm("TEMP")
        if hum > HUMIDITY_UPPER_LIMIT:
            alarms.append(f"{sensor_id}-湿度过高")
            trigger_alarm("HUM")
        if hum < HUMIDITY_LOWER_LIMIT:
            alarms.append(f"{sensor_id}-湿度过低")
            trigger_alarm("HUM")
        return temp, hum, alarms if alarms else None
    except Exception as e:
        print(f"Sensor {sensor_id} error:", e)
        trigger_alarm("ERROR")
        return None, None, ['error']

def save_to_csv():
    global temp1_val, hum1_val, lux1_val, pressure1_val, height1_val
    global temp2_val, hum2_val, lux2_val, pressure2_val, height2_val, tap_status, buzzer_on
    
    try:
        t = time.localtime()
        timestamp = f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        
        # 合并调试日志为一行
        vars_info = [
            f"temp1={temp1_val}({type(temp1_val).__name__})",
            f"hum1={hum1_val}({type(hum1_val).__name__})",
            f"lux1={lux1_val}({type(lux1_val).__name__})",
            f"pressure1={pressure1_val}({type(pressure1_val).__name__})",
            f"height1={height1_val}({type(height1_val).__name__})",
            f"temp2={temp2_val}({type(temp2_val).__name__})",
            f"hum2={hum2_val}({type(hum2_val).__name__})",
            f"lux2={lux2_val}({type(lux2_val).__name__})",
            f"pressure2={pressure2_val}({type(pressure2_val).__name__})",
            f"height2={height2_val}({type(height2_val).__name__})"
        ]
        print(f"[csv] 变量状态: {', '.join(vars_info)}")
        
        def format_value(val, is_float=True):
            if val is None:
                return "N/A"
            try:
                val_float = float(val)
                return f"{val_float:.1f}" if is_float else f"{int(val_float)}"
            except (ValueError, TypeError) as e:
                print(f"[csv] 格式化失败: {val} (类型: {type(val).__name__}, 错误: {e})")
                return "N/A"
        
        sensor1_data = [
            timestamp,
            format_value(temp1_val),
            format_value(hum1_val),
            format_value(lux1_val, is_float=False),
            format_value(pressure1_val),
            format_value(height1_val),
            str(tap_status),
            str(buzzer_on)
        ]
        
        sensor2_data = [
            timestamp,
            format_value(temp2_val),
            format_value(hum2_val),
            format_value(lux2_val, is_float=False),
            format_value(pressure2_val),
            format_value(height2_val),
            str(tap_status),
            str(buzzer_on)
        ]
        
        sensor1_file = "/sensor1_test.csv"
        sensor2_file = "/sensor2_test.csv"
        
        header = "Timestamp,Temp(C),Hum(%),Lux,Pressure(hPa),Height(m),Tap_Status,Buzzer_On\n"
        
        with open(sensor1_file, 'a') as f:
            f.write(header)
            f.write(','.join(str(x) for x in sensor1_data) + '\n')
        
        with open(sensor2_file, 'a') as f:
            f.write(header)
            f.write(','.join(str(x) for x in sensor2_data) + '\n')
        
        print(f"[csv] 数据已保存到 {sensor1_file} 和 {sensor2_file}")
    
    except Exception as e:
        print(f"[csv] 保存数据失败: {e}")

def update_leds(temp1, temp2):
    global tap_status, buzzer_on, manual_override, last_manual_time
    current_time = time.time()
    
    if (temp1 is not None and temp1 > TEMP_UPPER_LIMIT) or (temp2 is not None and temp2 > TEMP_UPPER_LIMIT):
        tap_status = 'on'
        buzzer_on = True
        led_g.value(0)
        led_r.value(1)
        print(f"温度超上限: tap_status 强制设为 on (优先级最高)")
        return

    if not manual_override or (current_time - last_manual_time >= manual_override_timeout):
        temp1_ok = temp1 is not None and temp1 <= TEMP_UPPER_LIMIT
        temp2_ok = temp2 is not None and temp2 <= TEMP_UPPER_LIMIT
        if temp1_ok and temp2_ok:
            tap_status = 'off'
            led_g.value(1)
            led_r.value(0)
        else:
            tap_status = 'on'
            buzzer_on = True
            led_g.value(0)
            led_r.value(1)
        #print(f"温度控制: tap_status 设为 {tap_status} (优先级最低)")
    else:
        print(f"手动/远程锁定: 温度控制被忽略 (剩余时间: {manual_override_timeout - (current_time - last_manual_time):.1f}s)")

def display_normal(oled, sensor_id, temp, hum, lux, pressure, height):
    oled.fill(0)
    oled.text(f'S#{sensor_id}', 0, 0)
    oled.text(f'L:{int(lux) if lux is not None else 0}', 50, 0)
    oled.hline(0, 12, 128, 1)
    oled.text('Temp:', 0, 15)
    oled.text(f'{temp:.1f} C' if temp is not None else 'N/A', 70, 15)
    oled.text('Humid:', 0, 30)
    oled.text(f'{hum:.1f} %' if hum is not None else 'N/A', 70, 30)
    pressure_str = f'{pressure:.1f}hPa' if pressure is not None else 'N/A'
    height_str = f'{height}m' if height is not None else 'N/A'
    oled.text(f'P:{pressure_str}', 0, 45)
    oled.text(f'H:{height_str}', 0, 55)
    if temp is not None and (temp > TEMP_UPPER_LIMIT or temp < TEMP_LOWER_LIMIT):
        oled.text('!', 115, 20)
    if hum is not None and (hum > HUMIDITY_UPPER_LIMIT or hum < HUMIDITY_LOWER_LIMIT):
        oled.text('!', 115, 40)
    if lux is not None and (lux < LUX_LOWER_LIMIT or lux > LUX_UPPER_LIMIT):
        oled.text('!', 115, 0)
    oled.show()

def handle_tcp_message():
    global tap_status, buzzer_on, temp1_val, temp2_val, last_switch_time, manual_override, last_manual_time, last_handled_message
    try:
        response = urequests.get(serverIP + '?uid=' + CLIENT_ID + '&topic=' + TOPIC_TEMP_4 + '&type=3')
        parsed = ujson.loads(response.text)
        data = parsed["data"][0]
        msg = data['msg']
        
#         # 检查是否为已处理的消息
#         if msg == last_handled_message:
#             print(f"[remote] 跳过重复消息: {msg}")
#             return
        
        current_time = time.time()
        #print(f"[remote] Received message: {msg}")
        
        # 远程控制仅在按键间隔后生效
        if current_time - last_switch_time >= SWITCH_INTERVAL:
            if msg == "tapon" and tap_status != "on":
                tap_status = 'on'
                led_g.value(0)
                led_r.value(1)
                manual_override = True
                last_manual_time = current_time
                last_switch_time = current_time
                print(f"[remote] 远程控制: tap_status 设为 on (优先级中)")
            elif msg == "tapoff" and tap_status != "off":
                tap_status = 'off'
                led_g.value(1)
                led_r.value(0)
                manual_override = True
                last_manual_time = current_time
                last_switch_time = current_time
                print(f"[remote] 远程控制: tap_status 设为 off (优先级中)")
            elif msg == "buzzeron" and not buzzer_on:
                buzzer.duty(512)
                buzzer_on = True
                print(f"[remote] 蜂鸣器开启")
            elif msg == "buzzeroff" and buzzer_on:
                buzzer.duty(0)
                buzzer_on = False
                print(f"[remote] 蜂鸣器关闭")
            
            # 更新已处理的消息
            last_handled_message = msg
        
        update_leds(temp1_val, temp2_val)
        time.sleep(0.1)

    except Exception as e:
        print(f"[remote] TCP message error: {e}")

def set_limit_message():
    global TEMP_UPPER_LIMIT, TEMP_LOWER_LIMIT, HUMIDITY_UPPER_LIMIT, HUMIDITY_LOWER_LIMIT, LUX_UPPER_LIMIT, LUX_LOWER_LIMIT, last_limit_message
    try:
        response = urequests.get(serverIP + '?uid=' + CLIENT_ID + '&topic=' + TOPIC_TEMP_5 + '&type=3')
        parsed = ujson.loads(response.text)
        data = parsed["data"][0]
        msg = data['msg']
        
        # 检查是否为已处理的消息
        if msg == last_limit_message:
            #print(f"[remote] 跳过重复阈值消息: {msg}")
            return
        
        #print(f"[remote] 处理阈值消息: {msg}")
        
        if '=' in msg:
            param_name, value_str = msg.split('=', 1)
            try:
                value = float(value_str)
                if param_name == 'SETTEMPUPPER':
                    TEMP_UPPER_LIMIT = min(max(value, 0.0), 60.0)
                    if TEMP_UPPER_LIMIT < TEMP_LOWER_LIMIT:
                        TEMP_LOWER_LIMIT = TEMP_UPPER_LIMIT
                        print(f"[remote] 温度下限已同步调整为: {TEMP_LOWER_LIMIT}")
                    print(f"[remote] 设置温度上限: {TEMP_UPPER_LIMIT}")
                elif param_name == 'SETTEMPLOWER':
                    TEMP_LOWER_LIMIT = min(max(value, -20.0), 40.0)
                    if TEMP_LOWER_LIMIT > TEMP_UPPER_LIMIT:
                        TEMP_UPPER_LIMIT = TEMP_LOWER_LIMIT
                        print(f"[remote] 温度上限已同步调整为: {TEMP_UPPER_LIMIT}")
                    print(f"[remote] 设置温度下限: {TEMP_LOWER_LIMIT}")
                elif param_name == 'SETHUMIDUPPER':
                    HUMIDITY_UPPER_LIMIT = min(max(value, 20.0), 95.0)
                    if HUMIDITY_UPPER_LIMIT < HUMIDITY_LOWER_LIMIT:
                        HUMIDITY_LOWER_LIMIT = HUMIDITY_UPPER_LIMIT
                        print(f"[remote] 湿度下限已同步调整为: {HUMIDITY_LOWER_LIMIT}")
                    print(f"[remote] 设置湿度上限: {HUMIDITY_UPPER_LIMIT}")
                elif param_name == 'SETHUMIDLOWER':
                    HUMIDITY_LOWER_LIMIT = min(max(value, 10.0), 80.0)
                    if HUMIDITY_LOWER_LIMIT > HUMIDITY_UPPER_LIMIT:
                        HUMIDITY_UPPER_LIMIT = HUMIDITY_LOWER_LIMIT
                        print(f"[remote] 湿度上限已同步调整为: {HUMIDITY_UPPER_LIMIT}")
                    print(f"[remote] 设置湿度下限: {HUMIDITY_LOWER_LIMIT}")
                elif param_name == 'SETLIGHTUPPER':
                    LUX_UPPER_LIMIT = min(max(int(value), 500), 20000)
                    if LUX_UPPER_LIMIT < LUX_LOWER_LIMIT:
                        LUX_LOWER_LIMIT = LUX_UPPER_LIMIT
                        print(f"[remote] 光照下限已同步调整为: {LUX_LOWER_LIMIT}")
                    print(f"[remote] 设置光照上限: {LUX_UPPER_LIMIT}")
                elif param_name == 'SETLIGHTLOWER':
                    LUX_LOWER_LIMIT = min(max(int(value), 10), 5000)
                    if LUX_LOWER_LIMIT > LUX_UPPER_LIMIT:
                        LUX_UPPER_LIMIT = LUX_LOWER_LIMIT
                        print(f"[remote] 设置光照上限: {LUX_UPPER_LIMIT}")
                    print(f"[remote] 设置光照下限: {LUX_LOWER_LIMIT}")
            except ValueError:
                print(f"[remote] 无效的数值: {value_str} for {param_name}")
        elif 'RESTORE' in msg:
            
            TEMP_UPPER_LIMIT = 30.0
            TEMP_LOWER_LIMIT = 15.0
            HUMIDITY_UPPER_LIMIT = 70.0
            HUMIDITY_LOWER_LIMIT = 30.0
            LUX_UPPER_LIMIT = 10000
            LUX_LOWER_LIMIT = 100
            
            print("[remote] 所有参数已重置为默认值。")
        
        # 更新已处理的消息
        last_limit_message = msg

    except Exception as e:
        print(f"[remote] Error setting threshold: {e}")

def update_display():
    global show_threshold, temp1_val, hum1_val, lux1_val, temp2_val, hum2_val, lux2_val
    global pressure1_val, height1_val, pressure2_val, height2_val
    if show_threshold:
        display_parameters(oled1, oled2)
    else:
        display_normal(oled1, 1, temp1_val, hum1_val, lux1_val, pressure1_val, height1_val)
        display_normal(oled2, 2, temp2_val, hum2_val, lux2_val, pressure2_val, height2_val)

def main():
    global tcp_client, temp1_val, hum1_val, lux1_val, temp2_val, hum2_val, lux2_val
    global pressure1_val, height1_val, pressure2_val, height2_val
    global record_count, last_record_time
    global last_handled_message
    global alarms
    oled1.fill(0)
    oled1.text("Initializing...", 0, 20)
    oled1.show()
    oled2.fill(0)
    oled2.text("Initializing...", 0, 20)
    oled2.show()

    if not wifi_connect():
        oled1.fill(0)
        oled1.text("WiFi Error!", 0, 30)
        oled1.show()
        return
    if not tcp_connect():
        oled1.fill(0)
        oled1.text("TCP Error!", 0, 30)
        oled1.show()
        return

    last_upload = time.time()
    last_record_time = time.time()
    has_saved = False
    last_handled_message=''
    while True:
        handle_keyboard()
        if tcp_client:
            try:
                data = tcp_client.recv(1024)
                if data:
                    messages = data.decode('utf-8').strip().split('\r\n')
                    for message in messages:
                        if message.startswith('SET'):
                            set_limit_message()
                        elif message.startswith('{'):
                            handle_tcp_message()
            except Exception as e:
                print(f"Recv error: {e}")
        
        handle_tcp_message()
        set_limit_message()

        lux1_val = calculate_lux(light1_ao)
        lux2_val = calculate_lux(light2_ao)
        temp1_val, hum1_val, alarm1 = check_sensor(dht1, 1)
        temp2_val, hum2_val, alarm2 = check_sensor(dht2, 2)

        try:
            bmp_data1 = BMP1.get()
            if bmp_data1:
                pressure1_val = bmp_data1[1] / 100
                height1_val = BMP1.getAltitude()
            else:
                pressure1_val = None
                height1_val = None
                print("BMP1 读取错误或数据无效。")
        except Exception as e:
            print(f"读取 BMP1 异常: {e}")
            pressure1_val = None
            height1_val = None
        
        try:
            bmp_data2 = BMP2.get()
            if bmp_data2:
                pressure2_val = bmp_data2[1] / 100
                height2_val = BMP2.getAltitude()
            else:
                pressure2_val = None
                height2_val = None
                print("BMP2 读取错误或数据无效。")
        except Exception as e:
            print(f"读取 BMP2 异常: {e}")
            pressure2_val = None
            height2_val = None

#         # 数据记录
#         
# 
#         current_time =time.time()
#         if record_count < MAX_RECORDS and current_time - last_record_time >= RECORD_INTERVAL:
#             save_to_csv()
#             record_count += 1
#             last_record_time = current_time
#             if record_count >= MAX_RECORDS:
#                 print(f"[csv] 已完成 {MAX_RECORDS} 组数据记录，停止记录")
#         if not has_saved:
#             save_to_csv()
#             has_saved = True
        update_leds(temp1_val, temp2_val)
        update_display()

        alarms = []
        if alarm1:
            alarms.extend(alarm1)
        if alarm2:
            alarms.extend(alarm2)
        if lux1_val < LUX_LOWER_LIMIT:
            trigger_alarm("LIGHT_LOW")
            alarms.append("1-光强低")
        elif lux1_val > LUX_UPPER_LIMIT:
            trigger_alarm("LIGHT_HIGH")
            alarms.append("1-光强高")
        if lux2_val < LUX_LOWER_LIMIT:
            trigger_alarm("LIGHT_LOW")
            alarms.append("2-光强低")
        elif lux2_val > LUX_UPPER_LIMIT:
            trigger_alarm("LIGHT_HIGH")
            alarms.append("2-光强高")
        if not alarms and \
           all(v is not None for v in [temp1_val, hum1_val, lux1_val, temp2_val, hum2_val, lux2_val]) and \
           TEMP_LOWER_LIMIT <= temp1_val <= TEMP_UPPER_LIMIT and \
           HUMIDITY_LOWER_LIMIT <= hum1_val <= HUMIDITY_UPPER_LIMIT and \
           LUX_LOWER_LIMIT <= lux1_val <= LUX_UPPER_LIMIT and \
           TEMP_LOWER_LIMIT <= temp2_val <= TEMP_UPPER_LIMIT and \
           HUMIDITY_LOWER_LIMIT <= hum2_val <= HUMIDITY_UPPER_LIMIT and \
           LUX_LOWER_LIMIT <= lux2_val <= LUX_UPPER_LIMIT:
            send_alarm("所有参数正常")
        send_alarm(alarms)

        if time.time() - last_upload > 1:
            data1_upload = [f"{temp1_val:.1f}" if temp1_val is not None else "0",
                            f"{hum1_val:.1f}" if hum1_val is not None else "0",
                            str(int(lux1_val)) if lux1_val is not None else "0",
                            f"{pressure1_val:.1f}" if pressure1_val is not None else "0",
                            f"{height1_val}" if height1_val is not None else "0",
                            '已开启' if tap_status=='on' else '已关闭']
            send_data(TOPIC_TEMP_1, *data1_upload)
            data2_upload = [f"{temp2_val:.1f}" if temp2_val is not None else "0",
                            f"{hum2_val:.1f}" if hum2_val is not None else "0",
                            str(int(lux2_val)) if lux2_val is not None else "0",
                            f"{pressure2_val:.1f}" if pressure2_val is not None else "0",
                            f"{height2_val}" if height2_val is not None else "0",
                            '已开启' if buzzer_on else '已关闭']
            send_data(TOPIC_TEMP_2, *data2_upload)
            threshold_data = [f"{TEMP_UPPER_LIMIT:.1f}", f"{TEMP_LOWER_LIMIT:.1f}",
                              f"{HUMIDITY_UPPER_LIMIT:.1f}", f"{HUMIDITY_LOWER_LIMIT:.1f}",
                              str(int(LUX_UPPER_LIMIT)), str(int(LUX_LOWER_LIMIT))]
            send_data(TOPIC_TEMP_3, *threshold_data)
            last_upload = time.time()

        time.sleep(0.1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        buzzer.duty(0)
        led_g.value(1)
        led_r.value(1)
        status_led.value(1)
        if tcp_client:
            tcp_client.close()
        oled1.fill(0)
        oled2.fill(0)
        oled1.text("System Off", 0, 30)
        oled2.text("System Off", 0, 30)
        oled1.show()
        oled2.show()
