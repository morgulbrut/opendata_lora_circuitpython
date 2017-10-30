from simpleio import map_range
from analogio import AnalogIn
from digitalio import *
import busio as io
import board
import adafruit_dht
import time
import math

'''Settings'''
debug = True
cycles = 10
cycletime = 30

counter = 0
temp_av = 0
hum_av = 0
light_av = 0

analogin = AnalogIn(board.LIGHT)
lora_reset_pin = DigitalInOut(board.A2)
lora_reset_pin.direction = Direction.OUTPUT
switch_pin = DigitalInOut(board.SLIDE_SWITCH)
switch_pin.direction = Direction.INPUT
switch_pin.pull = Pull.UP
i2c = io.I2C(board.SCL, board.SDA)
import adafruit_ssd1306
oled = adafruit_ssd1306.SSD1306_I2C(64, 48, i2c)
dht = adafruit_dht.DHT22(board.A3)
uart_lora = io.UART(board.TX, board.RX, baudrate=56700)


def sensor_autodetect():
    i2c.try_lock()
    addresses = i2c.scan()
    i2c.unlock()
    print(addresses)


def read_light():
    peak = analogin.value * 330 // (2 ** 16)
    if debug:
        print('Light: ' + str(analogin.value) + ' => ' + str(int(peak)))
    return int(peak)


def read_temp():
    temp_ready = 0
    while temp_ready <= 20:
        try:
            temperature = dht.temperature
            humidity = dht.humidity
            if debug:
                print(
                    "Temp: {:.1f} *C \t Humidity: {}% ".format(temperature, humidity))
            temp_ready = 20
            return (temperature, humidity)
        except RuntimeError as e:
            temp_ready += 1
            time.sleep(0.05)
            if debug:
                print('ERROR: reading temp')

# LORA stuff....


def send_command(cmd):
    if debug:
        print(cmd)
    uart_lora.write(cmd + '\r\n')
    uart_read(uart_lora)


def uart_read(uart, ok_raise=False):
    msg = ''
    attempts = 10
    while attempts >= 0:
        time.sleep(0.5)
        msg = str(uart.readline())
        if 'ok' or 'RN' in msg:
            if debug:
                print(str(msg))
            break
        attempts -= 1
    if attempts < 0 and ok_raise:
        raise Exception('no OK received!')
    return msg


def lora_reset():
    lora_reset_pin.value = False
    time.sleep(0.5)
    lora_reset_pin.value = True
    send_command('sys get ver')

''' Sets the credentials for OTAA'''


def set_network_settings_ABP(devaddr, nwkskey, appskey):
    send_command('mac set devaddr ' + devaddr)
    send_command('mac set nwkskey ' + nwkskey)
    send_command('mac set appskey ' + appskey)
    send_command('mac save')


def connect(datarate='0', mode='abp', adr='off'):
    send_command('mac set dr ' + datarate)
    send_command('mac set adr ' + adr)
    send_command('mac join ' + mode)


def send_message_raw(message, confirmation='uncnf', port='1'):
    send_command('mac tx ' + confirmation + ' ' + port + ' ' + message)

lora_reset()
#set_network_settings_OTAA('00B6E3800912522F', '70B3D57ED0007DCF', '7E704FAFB81260778AC68A3A6A59274C')
set_network_settings_ABP(
    '26011A75', 'AA58CABBE1B4E286D1185D52C3CC669A', 'A0994B531C0CC69271B6BF472CDD0640')
connect()
time.sleep(2)


while True:
    if debug:
        print('**** measurement ****')
    # sensor_autodetect()

    temp = read_temp()
    light = read_light()
    light_av += light
    temp_av += temp[0]
    hum_av += temp[1]
    counter += 1
    oled.fill(0)
    oled.text('Measure',0,0)
    oled.text('L:' + str(light), 0, 9)
    oled.text('T:' + str(temp[0]), 0, 18)
    oled.text('H:' + str(temp[1]), 0, 27)
    oled.show()

    if(counter == cycles):
        light_av = light_av / cycles  # float yay
        temp_av = temp_av / cycles
        temp_av = math.floor(temp_av*10)/10
        hum_av = hum_av / cycles
        hum_av = math.floor(hum_av*2)/2
        switch = switch_pin.value
        if debug:
            print('**** transmit ****')
            print('Light:   ' + str(light_av))
            print('Temp:    ' + str(temp_av))
            print('Hum:     ' + str(hum_av))
            print('Switch:  ' + str(switch))
        oled.fill(0)
        oled.text('Transmit',0,0)
        oled.text('L:' + str(light_av), 0, 9)
        oled.text('T:' + str(temp_av), 0, 18)
        oled.text('H:' + str(hum_av), 0, 27)
        oled.text('S:' + str(switch), 0, 36)
        oled.show()


        payload = '0067'
        payload += '%04x' % (int(temp_av*10))
        payload += '0168'
        payload += '%02x' % (int(hum_av*2))
        payload += '0265'
        payload += '%04x' % (int(light_av))
        payload += '0300'
        payload += '%02x' % (int(switch))

        if debug:
            print('Payload: ' + payload)

        send_message_raw(payload)

        counter = 0
        temp_av = 0
        hum_av = 0
        light_av = 0
    time.sleep(cycletime)
