import time
import RPi.GPIO as GPIO
import adafruit_dht
from mfrc522 import SimpleMFRC522
from gpiozero import LED, Servo
import BlynkLib

# === BLYNK CONFIG ===
BLYNK_AUTH = "YOUR_BLYNK_AUTH_TOKEN"

blynk = BlynkLib.Blynk(BLYNK_AUTH)

# === PIN SETUP ===
DHT_PIN = 4
GAS_PIN = 17
FLAME_PIN = 27
TOUCH_PIN = 22
LED_PIN = 23
SERVO_PIN = 18

GPIO.setmode(GPIO.BCM)
GPIO.setup(GAS_PIN, GPIO.IN)
GPIO.setup(FLAME_PIN, GPIO.IN)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

led = LED(LED_PIN)
servo = Servo(SERVO_PIN)
dht_sensor = adafruit_dht.DHT11(DHT_PIN)
rfid = SimpleMFRC522()

led_state = False
door_open = False

# === VIRTUAL PIN ASSIGNMENT ===
VPIN_TEMP = 1
VPIN_HUM = 2
VPIN_FLAME = 3
VPIN_GAS = 4
VPIN_LED = 5
VPIN_DOOR = 6

# === BLYNK HANDLERS ===
@blynk.on("V5")  # LED toggle from app
def v5_handler(value):
    global led_state
    if int(value[0]) == 1:
        led.on()
        led_state = True
    else:
        led.off()
        led_state = False
    print(f"[BLYNK] LED {'ON' if led_state else 'OFF'}")

@blynk.on("V6")  # Door control
def v6_handler(value):
    if int(value[0]) == 1:
        open_door()

def toggle_led():
    global led_state
    led_state = not led_state
    led.on() if led_state else led.off()
    print(f"[TOUCH] LED {'ON' if led_state else 'OFF'}")
    blynk.virtual_write(VPIN_LED, 1 if led_state else 0)

def open_door():
    print("[DOOR] Opening...")
    servo.max()
    time.sleep(2)
    servo.mid()
    print("[DOOR] Closed.")
    blynk.virtual_write(VPIN_DOOR, 0)

print("Smart Home IoT System Started.")
print("Connecting to Blynk...")

try:
    while True:
        blynk.run()

        # === Touch sensor for LED ===
        if GPIO.input(TOUCH_PIN) == GPIO.HIGH:
            toggle_led()
            time.sleep(0.5)

        # === RFID ===
        id, text = rfid.read_no_block()
        if id:
            print(f"[RFID] Access by ID: {id}")
            open_door()
            time.sleep(1)

        # === DHT sensor ===
        try:
            temp = dht_sensor.temperature
            hum = dht_sensor.humidity
            if temp is not None and hum is not None:
                print(f"[DHT] {temp:.1f}°C / {hum:.1f}%")
                blynk.virtual_write(VPIN_TEMP, temp)
                blynk.virtual_write(VPIN_HUM, hum)
        except RuntimeError:
            pass

        # === Flame ===
        if GPIO.input(FLAME_PIN) == 0:
            print("[ALERT] Flame Detected!")
            blynk.virtual_write(VPIN_FLAME, 1)
        else:
            blynk.virtual_write(VPIN_FLAME, 0)

        # === Gas ===
        if GPIO.input(GAS_PIN) == 0:
            print("[ALERT] Gas Detected!")
            blynk.virtual_write(VPIN_GAS, 1)
        else:
            blynk.virtual_write(VPIN_GAS, 0)

        time.sleep(2)

except KeyboardInterrupt:
    print("Exiting...")
finally:
    GPIO.cleanup()
    print("GPIO cleaned up.")
