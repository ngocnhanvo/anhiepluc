# AnHiepLuc — Nghiệp vụ kho nội bộ và cập nhật giá nhân công

> Kiểm kê ngày 2026-10-31. Nguồn: mô tả nghiệp vụ của người vận hành và kết quả rà soát **Azure DevOps AnHiepLuc/master**. Đây là tài liệu nghiệp vụ, không phải thay đổi source production.

## 1. Phân biệt ba loại chứng từ

| Bảng SQL | Nghiệp vụ | Vai trò |
|---|---|---|
| `dbo.md_nhapkhonb` | Nhập vào kho xưởng sản xuất | Đầu vào sản xuất |
| `dbo.md_xuatkhonb` | Xuất vật tư cho xưởng; chuyển qua các công đoạn | Mỗi công đoạn có một kho ảo riêng |
| `dbo.md_vanchuyennoibo` | Chuyển từ kho công đoạn sản xuất cuối sang kho thành phẩm | Luân chuyển cuối quy trình, không đồng nhất với `md_xuatkhonb` |

Không suy đoán bảng đích chỉ từ tiền tố số chứng từ hoặc tên màn hình; phải truy vấn DB để xác nhận.

## 2. Chức năng Cập nhật lại giá sản phẩm/nhân công

- Module bảng giá: `MD_01_PhienBangGiaJQGS`.
- Case: `CA_01_CapNhatLaiGSP`.
- Controller Azure: `eman_ver3/Controller/JQGridModify/JQGridMD_01_PhienBangGiaJQGSModify.ashx`.
- Giao diện: `eman_ver3/js/Module_script/MD_01_PhienBangGiaJQGS.js`.
- Bảng chứng từ được tìm thấy trong **nhánh case này**: `db.md_xuatkhonb` và `db.md_vanchuyennoibo`.
- **Chưa thấy `db.md_nhapkhonb` được case xử lý**; không tự suy rộng tính năng này sang phiếu nhập kho xưởng.

Với `md_xuatkhonb`, code gán `phienbangiaNC` từ phiên bảng giá được chọn hoặc phiên mới nhất (`md_phienbangia_id`). Nhánh `md_vanchuyennoibo` cũng có xử lý chứng từ và chi tiết liên quan; cần phân biệt logic ghi phiên và logic tính lại giá dòng.

Các biến/điều kiện quan trọng phải rà khi có phiếu không được cập nhật:
`type` (chế độ), `scts` (danh sách chứng từ), `firstnull`, `doiPBGMoiNhat`, `ngaygoihan`, `md_phienbangia.hoatdong` và `ngay_hieuluc`. Sự hiện diện của những biến này **chưa chứng minh bản ghi cụ thể đáp ứng bộ lọc**.

### 2.1. Ma trận hỗ trợ — đối chiếu trực tiếp code Azure

Nguồn quét: Azure `master`, SHA `5a9ed179ae95e2e5139297b5e4899a3d89e835d3`,
`JQGridMD_01_PhienBangGiaJQGSModify.ashx` (xem [kết quả kiểm toán code #35](https://github.com/ngocnhanvo/anhiepluc/issues/35)).

| Bảng header | Nhánh cập nhật giá nhân công trong case? | Các bảng detail được xử lý |
|---|---|---|
| `md_nhapkhonb` | **Không** — không có truy cập `db.md_nhapkhonb` trong case | Không thấy trong case |
| `md_xuatkhonb` | **Có**, vùng dòng ~93–160 | `md_xuatkhonb_cdh`; tra `md_giasanpham` |
| `md_vanchuyennoibo` | **Có**, vùng dòng ~162–228 | `md_vanchuyennoibo_cdvc`, `md_vanchuyennoibo_dalayton`; tra `md_giasanpham` |

Bảng `md_nhapkhonb` có nghiệp vụ riêng nhưng **không được case hiện tại cập nhật giá**.

### 2.2. Các nhánh xử lý và điểm khác biệt

- Case đọc `type`, `scts` và `doiPBGMoiNhat`. Khi `type == "2"`, cả hai nhánh đều có đường lọc theo tập số chứng từ `scts`. Ở nhánh còn lại có ràng buộc `ngaytao >= ngaygoihan` (giới hạn ngày tính từ thời điểm chạy).
- `md_xuatkhonb`: nếu `doiPBGMoiNhat == "1"` thì gán `xnb.phienbangiaNC = pbgMoiNhat.md_phienbangia_id`; nếu không và `type == "2"`, gán `xnb.phienbangiaNC = pbg.md_phienbangia_id` (dòng ~103–106).
- `md_vanchuyennoibo`: trong đoạn đã rà, **chỉ thấy** gán `xnb.phienbangiaNC = pbgMoiNhat.md_phienbangia_id` khi `doiPBGMoiNhat == "1"` (dòng ~172–173). **Không có nhánh gán phiên được chọn tương ứng với `type == "2"` như ở `md_xuatkhonb`** trước khi xử lý các dòng chi tiết.
- Vòng lặp chi tiết tìm giá nhân công theo `phienbangiaNC` và cập nhật `gianhancong`, sau đó có `SaveChanges` / transaction. Chỉ thấy phiên tồn tại trong bảng giá chưa đảm bảo giá nhân công sẽ được cập nhật đúng.

**Nguy cơ lỗi nghiệp vụ:** thao tác cập nhật theo danh sách số chứng từ `type == "2"`, nhưng không bật `doiPBGMoiNhat == "1"`, có thể khiến phiếu `md_vanchuyennoibo` vẫn không được gán phiên, trong khi `md_xuatkhonb` có thể gán phiên được chọn. Đây là khác biệt có chứng cứ code; cần kiểm tra chính xác tham số UI và giá trị `phienbangiaNC` đầu vào trước khi khẳng định nguyên nhân cuối cùng của một phiếu cụ thể.

## 3. Trường hợp thực tế đã xác minh bằng SQL (2026-10-31)

- Một phiếu chuyển kho nội bộ được xác nhận hiện diện **1 dòng** trong `md_vanchuyennoibo`, **0 dòng** trong `md_nhapkhonb`.
- Phiếu ở trạng thái `HIEULUC`, có khóa `banggiaNC`, nhưng trường `phienbangiaNC` còn rỗng.
- Bảng giá liên kết có **11 phiên bảng giá** trong `md_phienbangia` (chỉ đếm số phiên, chưa kết luận phiên nào phù hợp).
- Kết quả trên chỉ xác nhận lỗi thiếu phiên; **chưa kết luận** đó là lỗi ngày giới hạn, chế độ `type`, lọc chứng từ, hoạt động phiên hay cách lưu giá dòng.

Chứng cứ kiểm tra (kết quả dữ liệu chi tiết được mã hóa, tránh công khai thông tin kinh doanh):
- [Đối chiếu bảng chứng từ, Issue #28](https://github.com/ngocnhanvo/anhiepluc/issues/28)
- [Đối chiếu bảng giá / phiên bảng giá, Issue #33](https://github.com/ngocnhanvo/anhiepluc/issues/33)
- [Quét backend case, Issue #32](https://github.com/ngocnhanvo/anhiepluc/issues/32)

## 4. Quy trình điều tra trước khi sửa

1. SELECT đúng chứng từ ở bảng kho đích, đọc `md_trangthai_id`, `banggiaNC`, `phienbangiaNC`, ngày chứng từ và loại chuyển.
2. SELECT `md_banggia` qua `banggiaNC`; liệt kê `md_phienbangia` cùng bảng giá, trạng thái và ngày hiệu lực.
3. Đọc từng nhánh `md_xuatkhonb` / `md_vanchuyennoibo` trong `CA_01_CapNhatLaiGSP`; xác minh điều kiện `type`, `scts`, `firstnull`, `doiPBGMoiNhat`, `ngaygoihan`, trạng thái chứng từ và ngày hiệu lực.
4. Tách xác định **phiên bảng giá gắn header** và **tính giá nhân công / giá chi tiết**: sửa một việc chưa chắc đồng nghĩa đã xử lý việc còn lại.
5. Chỉ đề xuất UPDATE hoặc sửa code sau khi tìm nguyên nhân cụ thể, có bảo vệ chống cập nhật nhầm và test đối chứng.

## 5. Giới hạn chứng cứ

Code tham chiếu đến bảng là bằng chứng nhánh case có xử lý bảng đó, **không chứng minh mọi phiếu của bảng đều đủ điều kiện cập nhật**. Danh sách bảng và logic sẽ cập nhật theo từng lần đối chiếu source Azure `master`.
