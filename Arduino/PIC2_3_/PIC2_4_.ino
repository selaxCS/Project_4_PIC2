
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

/* --- Network Configuration --- */
const char* ssid     = "DESKTOP-CKHH29C 5537";
const char* password = "i2:092T2";

/* --- MQTT Broker Configuration --- */
// NOTE: Must be the IP address of the Docker host machine.
const char* mqtt_broker_ip = "192.168.137.1"; 
const int mqtt_port = 1883;

/* --- DHT11 Sensor Configuration --- */
#define DHTPIN 2     // Sensor data pin
#define DHTTYPE DHT11   // Sensor type

/* --- Global Instances and Topics --- */
DHT dht(DHTPIN, DHTTYPE);
WiFiClient espClient;
PubSubClient client(espClient);

/* MQTT Publication Topics  */
const char* topic_temp  = "pic2/ESP8266REAL/temperature";
const char* topic_humi  = "pic2/ESP8266REAL/humidity";
const char* topic_error = "pic2/ESP8266REAL/error";

/* Timing Control (milliseconds) */
unsigned long lastMsg = 0;
#define MSG_BUFFER_SIZE  (50)
char msg[MSG_BUFFER_SIZE];
bool error_notificat = false;

/* Helper Function Prototypes */
void setup_wifi();
void reconnect();

void setup() {
  Serial.begin(115200);
  setup_wifi();
  client.setServer(mqtt_broker_ip, mqtt_port);
  dht.begin();
}

void loop() {
  /* Maintain MQTT Connection */
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long now = millis();
  
  /* Periodic Data Transmission (15s interval) */
  if (now - lastMsg > 5000) {
    lastMsg = now;

    /* Acquire Sensor Readings */
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    /* Validate Sensor Data */
    
    if (isnan(h) || isnan(t)) {
      Serial.println(F("DHT11 sensor read failure!"));
      
      
      if (!error_notificat) {
        client.publish(topic_error, "The DHT11 sensor has stopped responding!");
        error_notificat = true;
      }
      return; 
    } else {
      
      if (error_notificat) {
        client.publish(topic_error, "The DHT11 sensor is functioning correctly again.");
        error_notificat = false;
      }
    }

    /* Publish Temperature Payload */
    snprintf (msg, MSG_BUFFER_SIZE, "%.2f", t);
    Serial.print("Publishing temperature: ");
    Serial.println(msg);
    client.publish(topic_temp, msg);

    /* Publish Humidity Payload */
    snprintf (msg, MSG_BUFFER_SIZE, "%.2f", h);
    Serial.print("Publishing humidity: ");
    Serial.println(msg);
    client.publish(topic_humi, msg);
  }
}

/* Helper Function Definitions */

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to station: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  randomSeed(micros());

  Serial.println("");
  Serial.println("WiFi station connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  /* Loop until connection established */
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    
    /* Generate unique Client ID */
    String clientId = "ESP8266Client-";
    clientId += String(random(0xffff), HEX);
    
    /* Attempt MQTT connection */
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds");
      /* Wait 5s before retrying */
      delay(5000);
    }
  }
}