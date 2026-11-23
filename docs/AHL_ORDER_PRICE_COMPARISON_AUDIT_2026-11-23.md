# AHL — Rà soát yêu cầu đối chiếu Giá AHL / Giá ANCO

**Ngày:** 2026-11-23  
**Trạng thái:** REVIEW COMPLETE — chưa sửa nghiệp vụ production  
**Nguồn kiểm tra:** Azure DevOps `AnHiepLuc/master` SHA `611b03943449c0396e75c830e9ac3e137cf5adda`; AHL SQL read-only (biến DB hiện trỏ đến bản sao, không khẳng định đồng nhất production); ANCO Trading `ngocnhanvo/ancotrading/master`.

## 1. Yêu cầu nghiệp vụ (theo email và xác nhận khách)

1. Cột **Giá AHL** trở lại nguồn bảng giá bán AHL dành cho khách ANCO Trading.
2. Bổ sung cột **Giá ANCO** lấy giá được chuyển sang cùng đơn hàng ANCO, không thay thế nguyên dữ liệu giá lịch sử.
3. Đối chiếu hai giá theo từng dòng hàng; không có giá hoặc chênh lệch phải cảnh báo màu đỏ.
4. Chặn tiếp nhận/triển khai nếu mã hàng không có đơn giá hoặc đơn giá bằng 0 (cần xác nhận chặn một hay cả hai nguồn giá).
5. **Chênh lệch giá** chỉ cảnh báo; nội dung email không yêu cầu chặn vì giá khác nhau.

## 2. Những gì đã xác nhận trực tiếp từ source / metadata SQL

- AHL có `md_banggia`, `md_giasanpham`, và bảng đồng bộ riêng `md_banggia_ancotrading`, `md_phienbangia_ancotrading`, `md_giasanpham_ancotrading`.
- Bảng `c_dongdsdh` **đã có** `gianhap`, `giachuan`, `giadoichieu`, `chenhlechgia`; chưa được phép kết luận cần ALTER TABLE.
- `eman_ver3/Controller/PublicFunction/API_GuiNhanDonHang.ashx`, method `NhanDonHang` (khoảng dòng 134): tạo dữ liệu `c_dongdsdh`, gán `gianhap` (dòng 223) và `giachuan` (224) từ dữ liệu đầu vào.
- `eman_ver3/Controller/JQGridModify/JQGridMD_00_TatCaDonHangModify.ashx`, `CA01DSAncotradingMD00DSDHJQGS_MD00TatCaDonHang` (dòng 320): mở kết nối `connectString_Anco` (331) và lấy `dddsh.gianhap` (347) trong truy vấn đọc dòng đơn.
- `eman_ver3/Controller/JQGridModify/JQGridMD_01_DDSDHTNJQGSModify.ashx`: ở nhánh tạo dòng, có `pub.getGiaBanSP` với mã sản phẩm/khách hàng (122); gán `giadoichieu` (131), tính `gianhap` từ `giadoichieu` và phí (135); nhánh cập nhật cũng có các phép gán liên quan (223, 227).
- `eman_ver3/Controller/JQGridModify/JQGridMD_00_DSDHJQGSModify.ashx`: truy vấn và gán `giadoichieu` (726–727), kiểm tra giá đối chiếu không dương (728), và tính `chenhlechgia = gianhap - giadoichieu` (746).
- `gianhap` được sử dụng trong các báo cáo doanh thu, công nợ, phiếu in và báo cáo kế hoạch. Tuyệt đối không đổi ý nghĩa dữ liệu hoặc ghi đè hàng loạt mà chưa phân tích hiệu ứng dây chuyền.
- Hai entry points cần rà soát kiểm tra giá trước ghi dữ liệu/hiệu lực: `API_GuiNhanDonHang.ashx` và `JQGridMD_00_TatCaDonHangModify.ashx` (cộng các thao tác tạo/hiệu lực liên quan). Bộ quét chưa tìm được điều kiện chặn đơn giá thiếu/0 trong các method trên; đây **không phải** xác nhận mọi đường đi đều chưa chặn.

## 3. Phương án đề xuất

1. Bảo tồn `c_dongdsdh.gianhap` là giá được nhận từ đơn ANCO (nếu kiểm tra payload thực tế xác nhận); dùng tên hiển thị **Giá ANCO**.
2. Dùng `giadoichieu` từ giá bán AHL theo đúng đối tác, mặt hàng, thời điểm hiệu lực làm **Giá AHL**, nhưng cần kiểm tra truy vấn gốc trước khi cố định ánh xạ. Không lấy bảng giá ANCO đồng bộ làm giá AHL.
3. Tận dụng `chenhlechgia` hiện có; xử lý rõ null, 0, rounding, mã hàng không tồn tại, cùng tiền tệ và đơn vị tính. Tô đỏ ở jqGrid chi tiết nếu giá thiếu hoặc hai giá không bằng nhau.
4. Trong backend, kiểm tra **toàn bộ** dòng trước khi thay đổi trạng thái/nhận: nếu giá bắt buộc null hoặc <=0, trả về danh sách mã hàng và thông điệp; không chấp nhận nhận một phần. Thao tác cần transaction/rollback khi lỗi.
5. Không tự chặn đơn giá chênh lệch nếu khách chỉ yêu cầu cảnh báo.
6. Giữ công thức đang phục vụ báo cáo/kế toán, nếu phát sinh đổi nguồn giá tính tiền phải có yêu cầu xác nhận riêng.

## 4. Việc cần xác thực trước khi triển khai

- DB production có cùng schema với DB clone đang cấu hình secrets hay không.
- Payload của ANCO Trading gửi `gianhap` / `giachuan` có phản ánh giá **ngay lúc chuyển đơn** hay không; đối chiếu với 1 phiếu thực tế.
- `giadoichieu` là bảng giá bán AHL của khách ANCO Trading và lựa chọn phiên giá/hiệu lực đúng.
- Cột `Giá AHL` ở màn hình hiện tại liên kết trường database hoặc module metadata nào; xác định cần đổi alias hay bổ sung jqGrid column.
- Điều kiện chặn áp dụng cho ANCO, AHL, hay đồng thời cả hai giá.
- Các phép tính tổng tiền dùng `gianhap` hay `giadoichieu` và các báo cáo chịu ảnh hưởng.

## 5. Ước tính sơ bộ (chưa phải báo giá chốt)

| Công việc | Giờ |
| --- | ---: |
| Đối chiếu dữ liệu thật, xác nhận mapping và ngày hiệu lực giá | 2–3 |
| Sửa/giữ snapshot giá và nguồn đối chiếu phía backend | 2–4 |
| Chặn giá 0/thiếu trước nhận/triển khai, thông báo theo dòng | 3–4 |
| UI jqGrid, thêm cột và cảnh báo lệch giá | 2–3 |
| Kiểm thử phiếu mẫu, hồi quy tính tiền và báo cáo | 3–5 |
| **Tổng** | **12–19** |

Giá tham chiếu bảo trì **250.000 VND/giờ** → **3–4,75 triệu VND**, trước dự phòng phát sinh do dữ liệu production khác bản sao. Nếu cần bổ sung giao tiếp ANCO / schema mới, đánh giá lại.

## 6. Phạm vi thao tác đã thực hiện

- Đã đọc source ANCO qua GitHub và source Azure qua Actions chỉ đọc.
- Đã SELECT metadata schema SQL bản sao, không sửa bản ghi dữ liệu.
- Chỉ bổ sung workflow chẩn đoán và tài liệu vào repo GitHub Actions `ngocnhanvo/anhiepluc/main`, **không push sửa mã nghiệp vụ Azure production**, không chỉnh trực tiếp database.

### Chú ý bảo mật độc lập

Trong repo `ngocnhanvo/ancotrading` public, file `App_Code/Public.cs` đang có chuỗi xác thực dịch vụ được hard-code. Không sao chép giá trị vào báo cáo; cần chuyển sang secret và thu hồi/đổi token cũ.
