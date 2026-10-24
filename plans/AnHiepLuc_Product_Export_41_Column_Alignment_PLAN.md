# Kế hoạch điều chỉnh Excel xuất danh sách hàng hóa — AnHiepLuc

**Mẫu gốc chủ sở hữu cung cấp:** `Danh sách hàng hóa-23_10_2026 13_18_02.xls` (không đưa file mẫu/dữ liệu ví dụ vào Git).  
**Ngày kế hoạch:** 2026-10-25  
**Trạng thái:** PLAN ONLY — chưa sửa logic export, chưa xác minh kết quả Excel thực tế trên AnHiepLuc.

## Phạm vi

- Đích mã nguồn: Azure DevOps `vongocnhancd10cntt2/AnHiepLuc/AnHiepLuc`, nhánh production `master` theo quy trình PR.
- GitHub `ngocnhanvo/anhiepluc` chỉ là nơi chạy Actions, không phải nguồn ứng dụng.
- Xuất Excel DHD: module `MD_00_DSHangHoaVG`, case `CA_01_ExportHHVG`.
- Xuất Excel soạn thảo: module `MD_00_DSHangHoa_SOANTHAO`, case `CA01ExportHHVG_MD00DSHangHoaSOANTHAO` — dùng chung cấu trúc cột khi người dùng yêu cầu mẫu áp dụng toàn AnHiepLuc, nhưng giữ khác biệt điều kiện trạng thái.
- Không thay module legacy `MD_00_DSHangHoa` / `CA_01_ExportHH`; nó đã được phục hồi ở PR #9.
- Không thay code ứng dụng trong bước lập kế hoạch; chỉ triển khai khi được giao thực hiện.

## Kết quả đọc trực tiếp workbook mẫu (không suy đoán)

- Định dạng BIFF8 / Excel 97–2003, extension `.xls`, sheet `Sheet1`.
- **41 cột vật lý A:AO**, gồm **37 cột hiển thị** và **4 cột ẩn Z:AC** (`vd`, `vn`, `vl`, `ghichu_vachngan`). Bốn cột ẩn có độ rộng bằng 0, cờ hidden.
- Row 1 là header, cao khoảng 62.4pt. Row dữ liệu cao khoảng 13.8pt. Hai dòng dữ liệu trong mẫu chỉ là ví dụ, không phải dữ liệu hardcode.
- Mẫu **không có `Mã thô`**, nhưng **có `Tổ SX`** trước `Thuế`.
- Bản xuất trước đây làm theo Anco1 có 37 cột **vật lý**, thêm `Mã thô`, bỏ `Tổ SX`, và bỏ cả bốn cột ẩn. Đây là những thay đổi cần đảo lại riêng cho AnHiepLuc.
- So sánh cấu trúc: `37 - 1 (Mã thô) + 4 (cột ẩn) + 1 (Tổ SX) = 41`.

## Đặc tả cột bắt buộc theo đúng thứ tự workbook

| Cột | Tên chính xác từ file .xls | Nguồn dự kiến/cần kiểm tra | Kiểu / Trạng thái |
|---|---|---|---|
| A | Mã hàng | sp.ma_sanpham | Text |
| B | Mô Tả Tiếng Việt | sp.mota_tiengviet | Text |
| C | ĐVT | md_donvitinhsanpham.ten_dvt | Text |
| D | L(cm) | sp.l_cm | Number/blank |
| E | W(cm) | sp.w_cm | Number/blank |
| F | H(cm) | sp.h_cm | Number/blank |
| G | Khối lượng (kg) | sp.trongluong | Number/blank |
| H | Diện Tích | sp.dientich | Number/blank |
| I | Thể Tích | sp.v2 (confirm against AnHiepLuc) | Number/blank |
| J | Tên kiểu dáng | md_kieudang_ancotrading.ten_tv | Text |
| K | Tên chức năng | md_chucnang_ancotrading.ten_tv | Text |
| L | Ghi chú | sp.ghichu | Text |
| M | SL Inner | md_donggoi_ancotrading.sl_inner | Number/blank |
| N | DVT Inner | md_donvitinh.ten_dvt via packaging dvt_inner | Text |
| O | l1 | md_donggoi_ancotrading.l1 | Number/blank |
| P | w1 | md_donggoi_ancotrading.w1 | Number/blank |
| Q | h1 | md_donggoi_ancotrading.h1 | Number/blank |
| R | SL Outer | md_donggoi_ancotrading.sl_outer | Number/blank |
| S | DVT Outer | md_donvitinh.ten_dvt via packaging dvt_outer | Text |
| T | l2 | md_donggoi_ancotrading.l2_mix | Number/blank |
| U | w2 | md_donggoi_ancotrading.w2_mix | Number/blank |
| V | h2 | md_donggoi_ancotrading.h2_mix | Number/blank |
| W | SL Cont 20 | md_donggoi_ancotrading.soluonggoi_ctn_20 | Number/blank |
| X | SL Cont 40 | md_donggoi_ancotrading.soluonggoi_ctn | Number/blank; confirm business meaning |
| Y | SL Cont 40 hc | md_donggoi_ancotrading.soluonggoi_ctn_40hc | Number/blank |
| Z | vd | Verify real source field in AnHiepLuc before mapping | HIDDEN |
| AA | vn | Verify real source field in AnHiepLuc before mapping | HIDDEN |
| AB | vl | Verify real source field in AnHiepLuc before mapping | HIDDEN |
| AC | ghichu_vachngan | Verify real source field in AnHiepLuc before mapping | HIDDEN |
| AD | Ngày xác nhận ĐG | md_donggoi_ancotrading.ngayxacnhan | Excel date/blank |
| AE | trạng thái ĐG | md_donggoi_ancotrading.trangthai | Text |
| AF | Ghi chú ĐG | md_donggoi_ancotrading.mota | Text |
| AG | Định khoản | sp.dinhkhoan | Text |
| AH | Nhóm VTHH | md_chungloai.code_cl using configured product relationship | Text |
| AI | NCC mặc định | md_doitackinhdoanh.ma_dtkd via sp.nhacungung | Text; reconcile orphan/vendor lookup |
| AJ | Kho SX | md_kho.ten_kho via sp.khomacdinh | Text |
| AK | Kho tồn | md_kho.ten_kho via sp.khoton | Text |
| AL | Xưởng SX | ad_department.ten_phongban via sp.phongbanId (confirm) | Text |
| AM | Tổ SX | md_phanxuong_to.ten_to via sp.md_to_id (verify AnHiepLuc schema) | Text |
| AN | Thuế | md_thue_sanpham.ten_thue_sanpham | Text |
| AO | Bán TP | sp.ban_thanhpham as 0/1 | 0/1 |

Các nguồn trong cột mapping là **giả thuyết kỹ thuật dựa trên mã Anco1 và luồng xuất đã làm**, không khẳng định schema/dữ liệu AnHiepLuc giống hoàn toàn. Các cột chưa có nguồn được đánh dấu cần kiểm tra.

## Các bước thực hiện khi triển khai

1. **Kiểm kê source và DB read-only.** Đọc current `master`, 2 cặp JS/ASHX của `SOANTHAO` và `VG`, kiểm tra PR/runs đang mở để không lặp. Đối chiếu cấu hình `ad_module`, `ad_column`, SQL/JOIN, cột thực của `md_sanpham`, `md_phanxuong_to`, `md_donggoi_ancotrading`, `md_donggoisanpham_ancotrading`, `md_donvitinh`, `md_doitackinhdoanh`.
2. **Chốt nguồn riêng cho 4 cột ẩn và Tổ SX.** Không tự đoán `vd/vn/vl/ghichu_vachngan`; nếu database không có thông tin, để trống đúng mẫu nhưng vẫn tạo **4 cột ẩn**. Xác minh `sp.md_to_id` → `md_phanxuong_to.ten_to` trước khi JOIN. Xác minh mã NCC ở trường có orphan, trường `SL Cont 40`, `Thể Tích`, nhãn xưởng/nhóm VTHH.
3. **Tái cấu trúc projection và headers cho 41 cột.** Chỉ sửa export handler của đúng module, tạo mapping tên/giá trị/type riêng biệt (không lấy theo thứ tự cột UI); bỏ `Mã thô`, chèn Z:AC đúng chỗ, thêm `Tổ SX`. Tối ưu dùng schema dùng chung cho hai trạng thái, nhưng không viết lại hạ tầng khác nếu không cần.
4. **Khớp định dạng `.xls` với mẫu.** NPOI `HSSFWorkbook`, sheet `Sheet1`, header chính xác kể cả hoa/thường/dấu, chiều cao 62.4/13.8 pt, độ rộng các cột theo mẫu, `SetColumnHidden(25..28,true)`, cột ẩn vật lý vẫn tồn tại; số là số, ngày là date, ô rỗng để trống, `Bán TP` là 0/1.
5. **Giữ bảo mật và luồng xuất hiện có.** `preview` đếm đủ hàng được phép xem theo bộ lọc jqGrid toàn bộ trang, `download` là POST file Excel trực tiếp, snapshot chống stale export, quyền module/case được kiểm tra server-side, SQL tham số hóa; tuyệt đối không thao tác cập nhật hàng hóa khi export. Giữ điều kiện `VG`: `sp.trangthai = 'DHD' AND sp.vattu = 0 AND (sp.sanpham = 1 OR sp.ban_thanhpham = 1)`. `SOANTHAO` giữ filter trạng thái SOANTHAO.
6. **Kiểm thử.** Dùng GitHub Actions chạy kiểm tra JS, đối chiếu 41 headers/thứ tự/4 flags hidden/kiểu cell và format của workbook thực tế với file mẫu; test bộ lọc, phân quyền, 0 dòng, lượng lớn, tên NCC, sản phẩm có/không BOM hoặc đóng gói, tình huống 1:N; test export qua WebForms thật trước khi báo PASS runtime.
7. **Phát hành.** Commit trên nhánh Azure riêng, tạo PR, đọc diff và log rồi merge `master` khi đủ điều kiện. Không merge trực tiếp qua GitHub. Phân biệt source merged với server deployed và Excel thực tế tải thành công.

## Tiêu chí nghiệm thu

- File tải thực sự mở được trong Excel, đúng `.xls`, đúng `Sheet1`.
- Có 41 cột vật lý A:AO, 37 cột hiển thị; Z:AC ở chế độ hidden, vị trí đúng và không làm lệch dữ liệu sau cột Y.
- Cột B là `Mô Tả Tiếng Việt` (không có `Mã thô`); AM là `Tổ SX`; AN là `Thuế`; AO là `Bán TP`.
- Tên cột, số lượng, thứ tự và các kiểu dữ liệu đúng file mẫu; không sao chép 2 dòng dữ liệu ví dụ vào file xuất.
- Quyền, trạng thái và bộ lọc không thay đổi; mỗi mã hàng không bị nhân dòng do JOIN đóng gói hoặc BOM.
- Test/merge/deploy có bằng chứng riêng và biết commit SHA, PR, Actions run.
