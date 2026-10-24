# Kế hoạch điều chỉnh xuất Excel danh sách hàng hóa — AnHiepLuc (37 cột)

**Ngày điều chỉnh:** 2026-10-25  
**File mẫu:** `Danh sách hàng hóa-23_10_2026 13_18_02.xls` (không lưu dữ liệu ví dụ hay file Excel của chủ sở hữu lên GitHub).  
**Trạng thái:** KẾ HOẠCH — chưa chỉnh logic xuất Excel và chưa kiểm thử Excel thực tế trên AnHiepLuc.

## Các quyết định đã chốt

- **Bỏ hẳn 4 cột ẩn của file mẫu**: `vd`, `vn`, `vl`, `ghichu_vachngan`. **Không tạo** các cột này trong workbook xuất, kể cả cột ẩn hoặc cột trống.
- **Bỏ cột `Mã thô`** có trong bản Excel xuất hiện tại dựa trên Anco1.
- **Thêm cột `Tổ SX`** đứng ngay sau `Xưởng SX`, trước `Thuế`.
- **Xưởng SX lấy từ bảng `md_phanxuong`; Tổ SX lấy từ bảng `md_phanxuong_to`**, theo chỉ định rõ của chủ sở hữu AnHiepLuc. Không dùng `ad_department`, `phongbanId` hay cách gán dữ liệu Xưởng/Tổ của bản Excel xuất Anco1.
- Kết quả phải có **đúng 37 cột vật lý A:AK, tất cả hiển thị**. File upload ban đầu có 41 cột vật lý A:AO (4 cột ẩn Z:AC); yêu cầu mới bỏ 4 cột đó → 37 cột A:AK.
- Giữ định dạng **Excel 97–2003 `.xls`**, sheet `Sheet1`, header và kiểu dữ liệu/căn chỉnh/độ rộng theo các **cột được giữ lại** từ mẫu, không copy hai dòng ví dụ làm dữ liệu thật.

## Phạm vi module

- Azure DevOps **`AnHiepLuc/AnHiepLuc`**, nhánh production `master`. GitHub `ngocnhanvo/anhiepluc` chỉ là runner GitHub Actions; không phải repository ứng dụng.
- **`MD_00_DSHangHoaVG` / `CA_01_ExportHHVG`**: xuất dữ liệu DHD, điều kiện `sp.trangthai = 'DHD' AND sp.vattu = 0 AND (sp.sanpham = 1 OR sp.ban_thanhpham = 1)`.
- **`MD_00_DSHangHoa_SOANTHAO` / `CA01ExportHHVG_MD00DSHangHoaSOANTHAO`**: cùng schema 37 cột nhưng chỉ các sản phẩm SOANTHAO theo module/phân quyền.
- **Không thay `MD_00_DSHangHoa` / `CA_01_ExportHH`**: chức năng xuất cũ đã khôi phục qua PR #9.
- Hiện chỉ cập nhật tài liệu kế hoạch, **không triển khai code export**.

## Thứ tự chính xác 37 cột cần xuất

| Cột | Tên cột | Nguồn dữ liệu dự kiến | Kiểu |
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
| Z | Ngày xác nhận ĐG | md_donggoi_ancotrading.ngayxacnhan | Excel date/blank |
| AA | trạng thái ĐG | md_donggoi_ancotrading.trangthai | Text |
| AB | Ghi chú ĐG | md_donggoi_ancotrading.mota | Text |
| AC | Định khoản | sp.dinhkhoan | Text |
| AD | Nhóm VTHH | md_chungloai.code_cl using configured product relationship | Text |
| AE | NCC mặc định | md_doitackinhdoanh.ma_dtkd via sp.nhacungung | Text; reconcile orphan/vendor lookup |
| AF | Kho SX | md_kho.ten_kho via sp.khomacdinh | Text |
| AG | Kho tồn | md_kho.ten_kho via sp.khoton | Text |
| AH | Xưởng SX | md_phanxuong.ten_phanxuong; liên kết dự kiến sp.md_phanxuong_id = md_phanxuong.md_phanxuong_id (xác minh trên Azure/DB) | Text / NULL nếu không gán |
| AI | Tổ SX | md_phanxuong_to.ten_to; liên kết dự kiến sp.md_to_id = md_phanxuong_to.md_to_id (xác minh trên Azure/DB) | Text / NULL nếu không gán |
| AJ | Thuế | md_thue_sanpham.ten_thue_sanpham | Text |
| AK | Bán TP | sp.ban_thanhpham as 0/1 | 0/1 |

**Các cột cuối sau khi bỏ 4 cột ẩn:** Z = `Ngày xác nhận ĐG`, AA = `trạng thái ĐG`, AB = `Ghi chú ĐG`, AG = `Kho tồn`, AH = `Xưởng SX`, AI = `Tổ SX`, AJ = `Thuế`, AK = `Bán TP`.

### Luồng ánh xạ Xưởng SX / Tổ SX (không theo Anco1)

Lấy **tên hiển thị**, không lấy ID thô trong file Excel:

```sql
-- JOIN dự kiến: kiểm chứng tên khóa bằng schema và cấu hình module thực tế AnHiepLuc.
LEFT JOIN dbo.md_phanxuong AS px
    ON px.md_phanxuong_id = sp.md_phanxuong_id
LEFT JOIN dbo.md_phanxuong_to AS pxt
    ON pxt.md_to_id = sp.md_to_id
-- projection: px.ten_phanxuong AS [Xưởng SX], pxt.ten_to AS [Tổ SX]
```

Chủ sở hữu đã xác nhận **nguồn bảng**, nhưng tên cột, khóa JOIN và mối liên hệ tổ/xưởng cần kiểm tra read-only trong Azure/SQL Server trước khi đưa vào SQL production. Đặc biệt, nếu bảng tổ có khóa tham chiếu xưởng, cần kiểm tra tính nhất quán (`md_phanxuong_to.md_phanxuong_id` với `sp.md_phanxuong_id`) để tránh hiển thị tổ của xưởng khác. Không sử dụng INNER JOIN làm mất sản phẩm chưa gán xưởng/tổ; không tạo trùng dòng dữ liệu.

## Các bước thực hiện

1. **Khảo sát Azure read-only:** xác định nhánh `master`, phiên bản mã hiện tại, PR/runs đang hoạt động; xem cấu hình hai module; kiểm tra schema và dữ liệu mẫu `md_sanpham`, `md_phanxuong`, `md_phanxuong_to` và các bảng đóng gói, NCC, kho, thuế. Với `Xưởng SX` / `Tổ SX`, lấy tên từ hai bảng chủ sở hữu cung cấp.
2. **Đối chiếu mapping:** xác minh foreign key/ID `sp.md_phanxuong_id`, `sp.md_to_id`, hai khóa lookup ở trên và liên hệ tổ–xưởng; đối chiếu `ad_module`, `ad_column`. Kiểm tra thêm mapping các trường `Thể Tích`, `SL Cont 40`, `Nhóm VTHH`, NCC mặc định (trường hợp tham chiếu thiếu).
3. **Sửa riêng export DHD và SOANTHAO:** cố định danh sách 37 headers A:AK; xóa `Mã thô` và 4 cột ẩn khỏi projection/workbook; thêm `Tổ SX` và sửa nguồn `Xưởng SX`. Giữ logic lấy hàng hóa theo phân quyền và bộ lọc jqGrid **mọi trang**, snapshot và POST download; SQL phân trang/batch an toàn, không thay trạng thái hàng hóa.
4. **Tạo Excel theo mẫu:** NPOI `HSSFWorkbook` thực sự cho `.xls`, `Sheet1`, 37 cột không hidden, header chính xác, ngày/số/tên/ô trống giữ đúng kiểu, các cột sau Y dồn trái bốn vị trí. Giữ tiêu đề khoảng 62.4pt, dữ liệu 13.8pt và chiều rộng tương ứng.
5. **Kiểm thử:** kiểm tra cú pháp JS/C#, 37 headers/37 data cells, không có `Mã thô` hay `vd/vn/vl/ghichu_vachngan`, dữ liệu `Xưởng SX/Tổ SX` đúng nguồn; kiểm tra lọc tất cả trang, phân quyền, dữ liệu null, trùng join, 0 dòng và file thực tế mở được trong Excel.
6. **Áp dụng:** commit lên nhánh Azure riêng, kiểm tra diff và Actions, PR/merge theo chế độ code và quyền đã cấp; phân biệt code trên master với deployment hoặc kiểm thử ở ứng dụng thực tế. Không sửa source Anco1.

## Điều kiện nghiệm thu

- File xuất **đúng 37 cột A:AK**, không có bốn cột ẩn hay cột `Mã thô`.
- Cột B là `Mô Tả Tiếng Việt`; cột AH = `Xưởng SX`, AI = `Tổ SX`, AJ = `Thuế`, AK = `Bán TP`.
- `Xưởng SX` được lấy tên từ `md_phanxuong`, `Tổ SX` từ `md_phanxuong_to`, không lấy từ bảng phòng ban.
- Mỗi sản phẩm chỉ xuất một dòng; giữ nguyên bộ lọc, phân quyền và điều kiện DHD/SOANTHAO.
- File `.xls` tải và mở được thực tế, các trường số/ngày/NULL hiển thị đúng.
