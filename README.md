# Blockchain Money Tracer

Demo phục vụ bài tập MIS, minh họa cách truy vết dòng tiền trên đồ thị giao dịch blockchain giả lập và giải thích các tín hiệu cần được xem xét thêm.

## Trạng thái hiện tại

**Giai đoạn 3 — Dashboard tương tác.** Dự án có:
- Kịch bản dữ liệu tĩnh 100 USDT trong `data/simulated_transactions.json`.
- Nhãn ví/thực thể mô phỏng trong `data/entities.json`.
- Đồ thị có hướng, truy vết FIFO xác định và kiểm tra bảo toàn dòng tiền.
- Risk Engine theo quy tắc, giải thích điểm cộng.
- Dashboard dark fintech với **Start Trace**, Reset, đồ thị SVG, chi tiết ví, các điểm cuối và bảng giao dịch có lọc.
- API cục bộ `/api/overview` và `POST /api/trace`.
- Bộ test pytest cho dữ liệu, logic, Risk Score và API.

## Nguyên tắc an toàn và phạm vi

- Chạy cục bộ và chỉ bind vào `127.0.0.1`.
- Không kết nối blockchain thật, Binance, ví điện tử, tài khoản tài chính hoặc API bên ngoài.
- Tất cả các ví, giao dịch, sàn và nhãn rủi ro đều là dữ liệu giả lập.
- Risk Score là điểm ưu tiên xem xét trong demo, không phải xác suất phạm tội hay kết luận pháp lý.
- Phân bổ FIFO là giả định xác định phục vụ bài tập khi tiền hội tụ ở một ví; nó không chứng minh danh tính thực của từng đơn vị token.
- Kịch bản không tính phí và tổng dòng tiền phải bảo toàn 100 USDT.

## Chạy trên Windows

Yêu cầu Python 3.10 trở lên, Flask và pytest. Nếu đã có dependencies trong môi trường hiện tại, không cần cài lại.

```powershell
cd D:\Projects\blockchain-money-tracer
python app.py
```

Mở `http://127.0.0.1:5000`. Nhấn **Start Trace** để tính toán đồ thị, truy vết các đường đi, xem Risk Score và kết quả tại các điểm cuối. Nhấn **Reset** để đưa giao diện về trạng thái ban đầu. Nhấn một ví trên đồ thị để xem thông tin và lọc các giao dịch liên quan.

## API cục bộ

- `GET /health`: trạng thái ứng dụng.
- `GET /api/overview`: thông tin kịch bản cố định.
- `POST /api/trace`: tính toán kết quả truy vết, đồ thị, Risk Score và bảo toàn dòng tiền từ JSON cục bộ.

Không endpoint nào gọi mạng ngoài.

## Kiểm thử

```powershell
python -m pytest -q
```

Các test bao gồm kiểm tra bảo toàn 100 USDT, chống đếm trùng, dữ liệu không hợp lệ, đồ thị, giải thích điểm rủi ro và tích hợp API dashboard.

## Quy tắc Risk Score mô phỏng

| Tín hiệu | Điểm cộng |
|---|---:|
| Thực thể có nhãn rủi ro giả lập | +40 |
| Có mẫu phân tách hoặc hội tụ đáng chú ý | +20 |
| Chuyển tiếp trong ngưỡng thời gian đã cấu hình | +15 |
| Cách nguồn ít nhất 3 bước giao dịch (mặc định) | +10 |

Mỗi loại tín hiệu chỉ được cộng tối đa một lần cho mỗi ví trong một lượt phân tích; tổng điểm bị giới hạn từ 0 đến 100. Nhãn hiển thị mặc định: 0–29 thấp, 30–59 trung bình, 60–100 cao. Đây là luật minh họa do dự án đặt ra, không phải tiêu chuẩn AML chính thức.

## Giới hạn diễn giải

Dấu vết giao dịch và mẫu bất thường có thể hỗ trợ sàng lọc, nhưng không tự chứng minh chủ sở hữu ví, ý định phạm tội hay hành vi rửa tiền. Mọi kết quả chỉ phản ánh dữ liệu tổng hợp được tạo sẵn.
