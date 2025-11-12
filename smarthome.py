import time
import board
import adafruit_dht
import RPi.GPIO as GPIO
from gpiozero import LED, Buzzer
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
DHT_PIN = board.D4       # DHT11 signal pin (GPIO4)
GAS_PIN = 17
TOUCH_PIN = 22
LDR_PIN = 27
LED_PIN = 23
BUZZER_PIN = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(GAS_PIN, GPIO.IN)
GPIO.setup(LDR_PIN, GPIO.IN)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

led = LED(LED_PIN)
buzzer = Buzzer(BUZZER_PIN)
dht_sensor = adafruit_dht.DHT11(DHT_PIN)

led_state = False

# === FIREBASE CONFIG ===
cred = credentials.Certificate("/home/andrei/serviceaccount.json")  # path to your key file
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smarthomepi-1c78f.firebaseio.com/'
})

root_ref = db.reference("SmartHome")
fs_db = firestore.client()

def log_to_firebase(sensor, value, event):
    """Log data to both Realtime Database and Firestore"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "timestamp": timestamp,
        "sensor": sensor,
        "value": value,
        "event": event
    }
    try:
        root_ref.child("logs").push(data)
        fs_db.collection("logs").add(data)
        print(f"[FIREBASE] Logged: {sensor} - {event}")
    except Exception as e:
        print("[FIREBASE ERROR]", e)

# === VIRTUAL PIN ASSIGNMENTS ===
VPIN_TEMP = 1
VPIN_HUM = 2
VPIN_GAS = 3
VPIN_LDR = 4
VPIN_LED = 5
VPIN_BUZZER = 6

# === BLYNK HANDLERS ===
@blynk.on("V5")
def v5_handler(value):
    """LED control via Blynk"""
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
    """Buzzer control via Blynk"""
    if int(value[0]) == 1:
        buzzer.on()
        log_to_firebase("Buzzer", "ON", "Controlled via Blynk")
        print("[BLYNK] Buzzer ON")
    else:
        buzzer.off()
        log_to_firebase("Buzzer", "OFF", "Controlled via Blynk")
        print("[BLYNK] Buzzer OFF")

# === LOCAL FUNCTIONS ===
def toggle_led():
    global led_state
    led_state = not led_state
    led.on() if led_state else led.off()
    blynk.virtual_write(VPIN_LED, 1 if led_state else 0)
    log_to_firebase("Touch", led_state, "Toggled LED")
    print(f"[TOUCH] LED {'ON' if led_state else 'OFF'}")

# === MAIN LOOP ===
print("Smart Home IoT System Started.")
print("Connecting to Blynk and Firebase...")

try:
    while True:
        blynk.run()

        # === Touch Sensor ===
        if GPIO.input(TOUCH_PIN) == GPIO.HIGH:
            toggle_led()
            time.sleep(0.5)

        # === DHT11 Sensor ===
        try:
            temp = dht_sensor.temperature
            hum = dht_sensor.humidity
            if temp is not None and hum is not None:
                print(f"[DHT] {temp:.1f}°C / {hum:.1f}%")
                blynk.virtual_write(VPIN_TEMP, temp)
                blynk.virtual_write(VPIN_HUM, hum)
                log_to_firebase("DHT11", f"{temp:.1f}°C / {hum:.1f}%", "Read OK")
                fs_db.collection("sensor_data").document("dht11").set({
                    "temperature": temp,
                    "humidity": hum,
                    "timestamp": datetime.now()
                })
        except RuntimeError:
            pass
        except Exception as e:
            print("[DHT ERROR]", e)

        # === Gas Sensor ===
        if GPIO.input(GAS_PIN) == 0:
            print("[ALERT] Gas Detected!")
            buzzer.on()
            blynk.virtual_write(VPIN_GAS, 1)
            log_to_firebase("Gas", "1", "Gas Detected")
        else:
            buzzer.off()
            blynk.virtual_write(VPIN_GAS, 0)

        # === LDR (Light Sensor) ===
        if GPIO.input(LDR_PIN) == 0:
            print("[LDR] Dark environment detected")
            blynk.virtual_write(VPIN_LDR, 0)
            log_to_firebase("LDR", "Dark", "Low Light Detected")
        else:
            print("[LDR] Bright environment detected")
            blynk.virtual_write(VPIN_LDR, 1)
            log_to_firebase("LDR", "Bright", "Light Detected")

        time.sleep(2)

except KeyboardInterrupt:
    print("Exiting...")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up.")
