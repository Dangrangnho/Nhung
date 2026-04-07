#include <Arduino_FreeRTOS.h>
#include <semphr.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>

#define SS_PIN 10
#define RST_PIN 9
#define SERVO_PIN 5
#define DOOR_OPEN_TIME_MS 3000

MFRC522 rfid(SS_PIN, RST_PIN);
Servo doorServo;
SemaphoreHandle_t doorSemaphore;

// --- Cấu hình UID thẻ (BẠN CẦN THAY UID THỰC TẾ Ở ĐÂY) ---
const byte UID_DUC_ANH[] = {0x86, 0xBE, 0x80, 0x05};
const byte UID_HAI_DANG[] = {0x91, 0x44, 0x5B, 0x98};

// Flags xác thực khuôn mặt
bool facePassed_A = false;
bool facePassed_B = false;
unsigned long timeout_A = 0;
unsigned long timeout_B = 0;
const long AUTH_TIMEOUT = 10000; // 10 giây để quẹt thẻ

void setup()
{
    Serial.begin(9600);
    SPI.begin();
    rfid.PCD_Init();
    doorServo.attach(SERVO_PIN);
    doorServo.write(0);

    doorSemaphore = xSemaphoreCreateBinary();

    // Tạo các Task với độ ưu tiên khác nhau
    xTaskCreate(TaskSerialRead, "Serial", 128, NULL, 2, NULL);
    xTaskCreate(TaskRFID, "RFID", 150, NULL, 2, NULL);
    xTaskCreate(TaskDoorControl, "Door", 100, NULL, 3, NULL);
    xTaskCreate(TaskHeartbeat, "Heart", 64, NULL, 1, NULL);
}

void loop() {}

// Task đọc lệnh từ Python
void TaskSerialRead(void *pvParameters)
{
    for (;;)
    {
        if (Serial.available() > 0)
        {
            char data = Serial.read();
            if (data == 'A')
            {
                facePassed_A = true;
                timeout_A = millis();
                Serial.println(F("MSG:Face A OK"));
            }
            else if (data == 'B')
            {
                facePassed_B = true;
                timeout_B = millis();
                Serial.println(F("MSG:Face B OK"));
            }
        }
        // Xử lý Timeout nếu không quẹt thẻ kịp
        if (facePassed_A && (millis() - timeout_A > AUTH_TIMEOUT))
            facePassed_A = false;
        if (facePassed_B && (millis() - timeout_B > AUTH_TIMEOUT))
            facePassed_B = false;

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

// Task xử lý RFID
void TaskRFID(void *pvParameters)
{
    for (;;)
    {
        if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial())
        {
            if (memcmp(rfid.uid.uidByte, UID_DUC_ANH, 4) == 0)
            {
                if (facePassed_A)
                {
                    facePassed_A = false; // Reset flag
                    xSemaphoreGive(doorSemaphore);
                }
                else
                {
                    Serial.println(F("MSG:Need Face A first"));
                }
            }
            else if (memcmp(rfid.uid.uidByte, UID_HAI_DANG, 4) == 0)
            {
                if (facePassed_B)
                {
                    facePassed_B = false; // Reset flag
                    xSemaphoreGive(doorSemaphore);
                }
                else
                {
                    Serial.println(F("MSG:Need Face B first"));
                }
            }
            rfid.PICC_HaltA();
            rfid.PCD_StopCrypto1();
        }
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

// Task điều khiển Servo và báo về Python
void TaskDoorControl(void *pvParameters)
{
    for (;;)
    {
        if (xSemaphoreTake(doorSemaphore, portMAX_DELAY) == pdPASS)
        {
            // GỬI TÍN HIỆU QUAN TRỌNG NHẤT
            Serial.println("OK");

            doorServo.write(120);
            vTaskDelay(pdMS_TO_TICKS(DOOR_OPEN_TIME_MS));
            doorServo.write(0);

            // Dọn dẹp buffer tránh lệnh thừa
            while (Serial.available())
                Serial.read();
        }
    }
}

void TaskHeartbeat(void *pvParameters)
{
    for (;;)
    {
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}