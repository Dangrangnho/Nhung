#include <Arduino_FreeRTOS.h>
#include <semphr.h>
#include <timers.h> // Thêm thư viện quản lý Software Timer
#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>

#define SS_PIN 10
#define RST_PIN 9
#define SERVO_PIN 5
#define DOOR_OPEN_TIME_MS 3000

MFRC522 rfid(SS_PIN, RST_PIN);
Servo doorServo;

// 1. Khai báo các công cụ đồng bộ của FreeRTOS
SemaphoreHandle_t doorSemaphore;   // Tín hiệu mở cửa
SemaphoreHandle_t facePassedMutex; // Mutex bảo vệ biến facePassed (Chống Race Condition)
TimerHandle_t authTimer;           // Software Timer đếm ngược 10s

// 2. Biến dùng chung (Đã được bảo vệ bằng Mutex)
bool facePassed = false;

const long AUTH_TIMEOUT_MS = 10000;

// ==========================================
// HÀM CALLBACK CỦA SOFTWARE TIMER
// Chạy tự động khi hết 10 giây chờ thẻ
// ==========================================
void vAuthTimerCallback(TimerHandle_t xTimer)
{
    // Hết 10 giây -> Lấy chìa khóa Mutex để reset biến về false
    if (xSemaphoreTake(facePassedMutex, portMAX_DELAY) == pdTRUE)
    {
        facePassed = false;
        xSemaphoreGive(facePassedMutex); // Trả chìa khóa
        Serial.println(F("MSG:Timeout, Face reset"));
    }
}

// ==========================================
// SETUP
// ==========================================
void setup()
{
    Serial.begin(9600);
    SPI.begin();
    rfid.PCD_Init();

    doorServo.attach(SERVO_PIN);
    doorServo.write(0);

    // Khởi tạo các công cụ HĐH
    doorSemaphore = xSemaphoreCreateBinary();
    facePassedMutex = xSemaphoreCreateMutex();

    // Khởi tạo Software Timer (One-shot: đếm 1 lần rồi dừng)
    authTimer = xTimerCreate("AuthTimer", pdMS_TO_TICKS(AUTH_TIMEOUT_MS), pdFALSE, (void *)0, vAuthTimerCallback);

    // Khởi tạo các Task
    xTaskCreate(TaskSerialRead, "Serial", 120, NULL, 2, NULL);
    xTaskCreate(TaskRFID, "RFID", 150, NULL, 2, NULL);
    xTaskCreate(TaskDoorControl, "Door", 80, NULL, 3, NULL);
}

void loop()
{
    // Bỏ trống hoàn toàn, để HĐH FreeRTOS tự quản lý lịch trình
}

// ==========================================
// CÁC LUỒNG THỰC THI (TASKS)
// ==========================================

// Task 1: Nhận lệnh từ Python
void TaskSerialRead(void *pvParameters)
{
    for (;;)
    {
        if (Serial.available() > 0)
        {
            char data = Serial.read();

            if (data == 'F')
            {
                // Phải xin Mutex trước khi ghi đè biến facePassed
                if (xSemaphoreTake(facePassedMutex, portMAX_DELAY) == pdTRUE)
                {
                    facePassed = true;
                    xSemaphoreGive(facePassedMutex); // Ghi xong phải trả Mutex ngay

                    xTimerStart(authTimer, 0); // Bấm giờ đếm ngược 10 giây (Software Timer)
                    Serial.println(F("MSG:Face OK"));
                }
            }
            else if (data == 'O')
            {
                xTimerStop(authTimer, 0);      // Thẻ đúng rồi thì tắt Timer đếm ngược đi
                xSemaphoreGive(doorSemaphore); // Báo cho Task mở cửa
            }
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

// Task 2: Xử lý thẻ RFID (Dùng Polling - Hỏi vòng liên tục)
void TaskRFID(void *pvParameters)
{
    for (;;)
    {
        if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial())
        {

            bool currentFaceStatus = false;

            // Xin Mutex để đọc và sửa biến facePassed một cách an toàn
            if (xSemaphoreTake(facePassedMutex, portMAX_DELAY) == pdTRUE)
            {
                currentFaceStatus = facePassed;
                if (currentFaceStatus)
                {
                    facePassed = false; // Quét 1 lần là mất tác dụng ngay
                }
                xSemaphoreGive(facePassedMutex);
            }

            if (currentFaceStatus)
            {
                // Gửi UID về Python
                Serial.print(F("UID:"));
                for (byte i = 0; i < rfid.uid.size; i++)
                {
                    if (rfid.uid.uidByte[i] < 0x10)
                        Serial.print('0');
                    Serial.print(rfid.uid.uidByte[i], HEX);
                }
                Serial.println();
            }
            else
            {
                Serial.println(F("MSG:Need Face first"));
            }

            rfid.PICC_HaltA();
            rfid.PCD_StopCrypto1();
        }

        // Ngủ 200ms để nhường CPU cho các Task khác, sau đó lặp lại
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

// Task 3: Điều khiển Cửa
void TaskDoorControl(void *pvParameters)
{
    for (;;)
    {
        // Chờ nhận lệnh mở cửa
        if (xSemaphoreTake(doorSemaphore, portMAX_DELAY) == pdPASS)
        {
            Serial.println(F("OK"));
            doorServo.write(120);
            vTaskDelay(pdMS_TO_TICKS(DOOR_OPEN_TIME_MS));
            doorServo.write(0);

            // Dọn dẹp rác trong Serial sau khi cửa đóng
            while (Serial.available())
                Serial.read();
        }
    }
}