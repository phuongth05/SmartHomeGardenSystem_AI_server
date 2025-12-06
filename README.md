# 🌱 Smart Garden AI Controller

Hệ thống điều khiển tưới cây thông minh sử dụng Machine Learning (Random Forest) để quyết định thời điểm tưới và lượng nước cần tưới dựa trên dữ liệu cảm biến môi trường.

## 📂 Cấu trúc dự án

```text
├── modeling.ipynb                 # Notebook huấn luyện model (Data Preprocessing & Training)
├── server.py                      # API Server (FastAPI)
├── water_need_classifier.pkl      # Model phân loại (Có cần tưới không?)
├── water_duration_regressor.pkl   # Model hồi quy (Tưới bao lâu?)
└── README.md                      # Hướng dẫn sử dụng
````

## 🚀 Cài đặt môi trường

Yêu cầu máy tính đã cài đặt **Python 3.8+**.

1.  **Cài đặt các thư viện cần thiết:**
    Mở terminal và chạy lệnh sau:

    ```bash
    pip install fastapi uvicorn scikit-learn pandas joblib
    ```

2.  **Kiểm tra Model:**
    Đảm bảo rằng 2 file `.pkl` (`water_need_classifier.pkl` và `water_duration_regressor.pkl`) nằm cùng thư mục với `server.py`.

## 🏃‍♂️ Khởi chạy Server

Chạy lệnh sau để bật API Server:

```bash
python server.py
```

Khi thấy dòng thông báo sau nghĩa là server đã sẵn sàng:

> `INFO: Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)`

-----

## 📡 Tài liệu API

### Endpoint: Dự đoán tưới cây

Gửi dữ liệu cảm biến lên để nhận quyết định tưới.

  - **URL:** `http://localhost:8000/predict`
  - **Method:** `POST`
  - **Content-Type:** `application/json`

#### 📥 Input (Request Body)

Bạn cần gửi JSON chứa thông số môi trường:

```json
{
  "humidity": 65.5,      // Độ ẩm đất (%)
  "light": 1200,         // Cường độ ánh sáng (Lux)
  "temperature": 32.0,   // Nhiệt độ (°C)
  "hour": 14,            // (Tùy chọn) Giờ hiện tại. Nếu không gửi server tự lấy.
  "minute": 30           // (Tùy chọn) Phút hiện tại.
}
```

#### 📤 Output (Response)

**Trường hợp 1: Cần tưới (WATER)**

```json
{
  "decision": "WATER",
  "reason": "Cây cần nước.",
  "water_duration": 5.25,   // Thời gian bơm bật (giây)
  "raw_prediction": 5.25
}
```

**Trường hợp 2: Không cần tưới (NO\_WATER)**

```json
{
  "decision": "NO_WATER",
  "reason": "Model dự đoán cây chưa cần nước.",
  "water_duration": 0
}
```

**Trường hợp 3: Đang chờ nghỉ (SKIP)**

```json
{
  "decision": "SKIP",
  "reason": "Đang trong thời gian nghỉ (Cooldown). Còn 120s nữa.",
  "water_duration": 0
}
```

-----

## ⚡ Hướng dẫn tích hợp Node-RED

Dưới đây là luồng xử lý (Flow) cơ bản để kết nối Node-RED với AI Server:

1.  **Node MQTT/Serial:** Nhận dữ liệu từ cảm biến (Arduino/ESP32).
2.  **Node Function (Chuẩn bị dữ liệu):**
    Viết code JS để format dữ liệu thành JSON chuẩn:
    ```javascript
    msg.payload = {
        "humidity": Number(msg.payload.hum),
        "light": Number(msg.payload.light),
        "temperature": Number(msg.payload.temp)
    };
    return msg;
    ```
3.  **Node HTTP Request:**
      * **Method:** `POST`
      * **URL:** `http://localhost:8000/predict` (Thay `localhost` bằng IP máy chạy Python nếu khác máy).
      * **Return:** `Parsed JSON object`.
4.  **Node Switch (Điều kiện):**
      * Kiểm tra `msg.payload.decision`:
          * `== "WATER"` -\> Chuyển sang node bật bơm.
          * `!= "WATER"` -\> Kết thúc hoặc log.
5.  **Node Delay/Trigger (Điều khiển bơm):**
      * Dùng giá trị `msg.payload.water_duration` để set thời gian bật relay (ví dụ dùng node *Delay* hoặc *Stoptimer*).

-----

## 🛡️ Cơ chế An toàn (Safety Logic)

Để bảo vệ phần cứng và cây trồng, Server có các ràng buộc cứng sau (có thể sửa trong `server.py`):

1.  **Max Water Duration (7s):** Dù AI dự đoán bao nhiêu, hệ thống không bao giờ bơm quá 15 giây/lần để tránh ngập úng.
2.  **Cooldown (5 phút):** Sau khi vừa tưới xong, hệ thống sẽ **từ chối** mọi lệnh tưới trong vòng 5 phút tiếp theo để chờ nước ngấm vào đất và cảm biến cập nhật giá trị mới.
3.  **Min Duration (1s):** Nếu AI dự đoán lượng nước quá nhỏ (\< 1s), hệ thống sẽ bỏ qua để bảo vệ động cơ bơm.

-----

## 🛠 Troubleshooting (Sửa lỗi thường gặp)

  * **Lỗi `Connection refused`:** Kiểm tra xem bạn đã chạy `python server.py` chưa.
  * **Lỗi `FileNotFoundError`:** Kiểm tra xem 2 file `.pkl` có nằm cùng thư mục với `server.py` không.
  * **Lỗi `422 Unprocessable Entity`:** Kiểm tra lại JSON gửi lên từ Node-RED, tên các trường (`humidity`, `light`, `temperature`) phải viết chính xác, không viết hoa chữ cái đầu.
