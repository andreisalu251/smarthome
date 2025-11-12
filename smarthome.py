import time
import board
import adafruit_dht
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from gpiozero import LED, Servo
import BlynkLib
import firebase_admin
from firebase_admin import credentials, db, firestore
from datetime import datetime
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

# === BLYNK CONFIG ===
BLYNK_AUTH = "vZdityxsgityg-vdzboal6srzYkm6Q6V"
blynk = BlynkLib.Blynk(BLYNK_AUTH)

# === PIN SETUP ===
DHT_PIN = board.D4          # DHT11 signal pin (GPIO4)
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

# === FIREBASE CONFIG ===
cred = credentials.Certificate("/home/andrei/serviceaccount.json")  # path to key file
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smarthomepi-1c78f.firebaseio.com/'
})

root_ref = db.reference("SmartHome")
fs_db = firestore.client()

def log_to_firebase(sensor, value, event):
    """Log to both Realtime DB and Firestore"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "timestamp": timestamp,
        "sensor": sensor,
        "value": value,
        "event": event
    }
    try:
        # Realtime DB log
        root_ref.child("logs").push(data)
        # Firestore log
        fs_db.collection("logs").add(data)
        print(f"[FIREBASE] Logged: {sensor} - {event}")
    except Exception as e:
        print("[FIREBASE ERROR]", e)

# === VIRTUAL PIN ASSIGNMENT ===
VPIN_TEMP = 1
VPIN_HUM = 2
VPIN_FLAME = 3
VPIN_GAS = 4
VPIN_LED = 5
VPIN_DOOR = 6

# === BLYNK HANDLERS ===
@blynk.on("V5")
def v5_handler(value):
    global led_state
    if int(value[0]) == 1:
        led.on()
        led_state = True
        log_to_firebase("LED", "ON", "Controlled via Blynk")
    else:
        led.off()
        led_state = False
        log_to_firebase("LED", "OFF", "Controlled via Blynk")
    print(f"[BLYNK] LED {'ON' if led_state else 'OFF'}")

@blynk.on("V6")
def v6_handler(value):
    if int(value[0]) == 1:
        open_door()

# === LOCAL FUNCTIONS ===
def toggle_led():
    global led_state
    led_state = not led_state
    led.on() if led_state else led.off()
    blynk.virtual_write(VPIN_LED, 1 if led_state else 0)
    log_to_firebase("Touch", led_state, "Toggled LED")
    print(f"[TOUCH] LED {'ON' if led_state else 'OFF'}")

def open_door():
    print("[DOOR] Opening...")
    servo.max()
    time.sleep(2)
    servo.mid()
    print("[DOOR] Closed.")
    blynk.virtual_write(VPIN_DOOR, 0)
    log_to_firebase("Door", "Opened", "RFID or Blynk")

# === MAIN LOOP ===
print("Smart Home IoT System Started.")
print("Connecting to Blynk and Firebase...")

try:
    while True:
        blynk.run()

        # === Touch sensor ===
        if GPIO.input(TOUCH_PIN) == GPIO.HIGH:
            toggle_led()
            time.sleep(0.5)

        # === RFID ===
        id, text = rfid.read_no_block()
        if id:
            print(f"[RFID] Access by ID: {id}")
            open_door()
            log_to_firebase("RFID", id, "Access Granted")
            time.sleep(1)

        # === DHT11 ===
        try:
            temp = dht_sensor.temperature
            hum = dht_sensor.humidity
            if temp is not None and hum is not None:
                print(f"[DHT] {temp:.1f}°C / {hum:.1f}%")
                blynk.virtual_write(VPIN_TEMP, temp)
                blynk.virtual_write(VPIN_HUM, hum)
                log_to_firebase("DHT11", f"{temp:.1f}°C / {hum:.1f}%", "Read OK")
                # Optional Firestore store
                fs_db.collection("sensor_data").document("dht11").set({
                    "temperature": temp,
                    "humidity": hum,
                    "timestamp": datetime.now()
                })
        except RuntimeError:
            pass
        except Exception as e:
            print("[DHT ERROR]", e)

        # === Flame ===
        if GPIO.input(FLAME_PIN) == 0:
            print("[ALERT] Flame Detected!")
            blynk.virtual_write(VPIN_FLAME, 1)
            log_to_firebase("Flame", "1", "Flame Detected")
        else:
            blynk.virtual_write(VPIN_FLAME, 0)

        # === Gas ===
        if GPIO.input(GAS_PIN) == 0:
            print("[ALERT] Gas Detected!")
            blynk.virtual_write(VPIN_GAS, 1)
            log_to_firebase("Gas", "1", "Gas Detected")
        else:
            blynk.virtual_write(VPIN_GAS, 0)

        time.sleep(2)

except KeyboardInterrupt:
    print("Exiting...")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up.")
