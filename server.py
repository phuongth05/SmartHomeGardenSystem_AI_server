import pandas as pd
import joblib
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import os

# --- CẤU HÌNH AN TOÀN & RÀNG BUỘC ---
MAX_WATER_DURATION = 7.0  # (Giây) Giới hạn tưới tối đa mỗi lần để tránh ngập
COOLDOWN_SECONDS = 300     # (Giây) 5 phút - Không tưới lại nếu vừa mới tưới xong
THRESHOLD_CONFIDENCE = 0.5 # Ngưỡng tự tin (nếu dùng predict_proba, ở đây dùng predict cứng)

# --- KHỞI TẠO APP & LOAD MODEL ---
app = FastAPI(title="Smart Garden API")

# Biến toàn cục lưu thời gian lần tưới cuối cùng
last_water_time = datetime.min

# Kiểm tra và load model
try:
    classifier = joblib.load('water_need_classifier.pkl')
    regressor = joblib.load('water_duration_regressor.pkl')
    print("Đã load thành công 2 models!")
except Exception as e:
    print(f"Lỗi load model: {e}")
    print("Hãy chắc chắn bạn đã chạy notebook và có file .pkl trong cùng thư mục.")

# --- ĐỊNH NGHĨA DỮ LIỆU INPUT ---
class SensorInput(BaseModel):
    humidity: float
    light: float
    temperature: float
    # Hour/Minute có thể gửi từ Node-RED hoặc để Server tự lấy
    hour: int = None 
    minute: int = None

# --- API ENDPOINT ---
@app.post("/predict")
def predict_watering(data: SensorInput):
    global last_water_time
    
    current_time = datetime.now()
    
    # 1. Xử lý thời gian (Feature Engineering)
    # Nếu Node-RED không gửi giờ/phút, lấy giờ hệ thống
    if data.hour is None:
        data.hour = current_time.hour
    if data.minute is None:
        data.minute = current_time.minute
        
    # 2. Tạo DataFrame đúng chuẩn input của model
    # Thứ tự cột PHẢI GIỐNG Y HỆT lúc train: ['humidity', 'light', 'temperature', 'hour', 'minute']
    input_df = pd.DataFrame([{
        'humidity': data.humidity,
        'light': data.light,
        'temperature': data.temperature,
        'hour': data.hour,
        'minute': data.minute
    }])
    
    # 3. Kiểm tra Ràng buộc thời gian (Cooldown)
    # Nếu chưa đủ thời gian nghỉ từ lần tưới trước -> Hủy bỏ
    time_diff = (current_time - last_water_time).total_seconds()
    if time_diff < COOLDOWN_SECONDS:
        return {
            "decision": "SKIP",
            "reason": f"Đang trong thời gian nghỉ (Cooldown). Còn {int(COOLDOWN_SECONDS - time_diff)}s nữa.",
            "water_duration": 0,
            "data_received": data.dict()
        }

    # 4. Dự đoán: CÓ CẦN TƯỚI KHÔNG? (Classification)
    # Model trả về 1 (Tưới) hoặc 0 (Không)
    need_water_pred = classifier.predict(input_df)[0]
    
    if need_water_pred == 0:
        return {
            "decision": "NO_WATER",
            "reason": "Model dự đoán cây chưa cần nước.",
            "water_duration": 0,
            "data_received": data.dict()
        }
    
    # 5. Dự đoán: TƯỚI BAO LÂU? (Regression)
    # Chỉ chạy khi need_water == 1
    duration_pred = regressor.predict(input_df)[0]
    
    # 6. Áp dụng Ràng buộc an toàn (Safety Logic)
    # Không bao giờ tưới quá MAX_WATER_DURATION và không tưới số âm
    final_duration = max(0.0, min(float(duration_pred), MAX_WATER_DURATION))
    
    # Nếu lượng nước quá bé (ví dụ < 1s), coi như không tưới để bảo vệ bơm
    if final_duration < 1.0:
         return {
            "decision": "NO_WATER",
            "reason": "Lượng nước dự đoán quá nhỏ, bỏ qua.",
            "water_duration": 0,
            "raw_prediction": duration_pred
        }

    # 7. Cập nhật trạng thái và trả về kết quả
    last_water_time = current_time # Cập nhật thời gian tưới
    
    return {
        "decision": "WATER",
        "reason": "Cây cần nước.",
        "water_duration": round(final_duration, 2), # Làm tròn 2 số thập phân
        "raw_prediction": round(float(duration_pred), 2)
    }

if __name__ == "__main__":
    # Chạy server ở port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)