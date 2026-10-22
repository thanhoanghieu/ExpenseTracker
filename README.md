# HỆ THỐNG QUẢN LÝ CHI TIÊU – EXPENSE TRACKER

> Đề tài triển khai ứng dụng web quản lý chi tiêu theo hướng DevOps trên máy ảo Ubuntu, sử dụng Docker Compose, PostgreSQL, Nginx, Prometheus, Grafana, Loki và Promtail.

## 1. Giới thiệu

**Expense Tracker** là ứng dụng web hỗ trợ ghi nhận và theo dõi các khoản **thu nhập**, **chi tiêu**, quản lý **danh mục giao dịch** và xem **thống kê/báo cáo**. Dự án được đóng gói thành các container để thuận tiện triển khai, theo dõi trạng thái và vận hành.

### Chức năng chính

- Ghi nhận giao dịch thu/chi và thông tin liên quan.
- Quản lý, phân loại các khoản giao dịch theo danh mục.
- Theo dõi số dư, tổng thu và tổng chi qua giao diện tổng quan.
- Xem báo cáo và dữ liệu giao dịch lưu trong PostgreSQL.
- Kiểm tra sức khỏe ứng dụng và kết nối cơ sở dữ liệu tại `/health`.

## 2. Công nghệ sử dụng

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Giao diện | HTML, CSS, JavaScript | Tương tác với người dùng |
| Backend | Python, Flask, Gunicorn | Xử lý nghiệp vụ và API |
| Cơ sở dữ liệu | PostgreSQL 15 | Lưu dữ liệu thu/chi |
| Công cụ quản trị CSDL | pgAdmin 4 | Truy vấn và quản lý PostgreSQL |
| Reverse proxy | Nginx | Tiếp nhận HTTP và chuyển tiếp đến Flask |
| Đóng gói và triển khai | Docker, Docker Compose | Quản lý các dịch vụ/container |
| Thu thập metrics | Prometheus, cAdvisor, Nginx Exporter, PostgreSQL Exporter | Giám sát ứng dụng và hạ tầng |
| Trực quan hóa metrics | Grafana | Dashboard CPU, RAM, Nginx, PostgreSQL |
| Thu thập và truy vấn logs | Promtail, Loki | Tập trung và phân tích nhật ký Docker |
| Quản lý mã nguồn | Git, GitHub | Lưu trữ mã nguồn và lịch sử thay đổi |

## 3. Kiến trúc hệ thống

```text
                 Người dùng (trình duyệt)
                          |
                       HTTP :80
                          |
                    Nginx Reverse Proxy
                          |
                     frontend-net
                          |
                     Flask / Gunicorn
                          |
                      backend-net
                          |
                      PostgreSQL
                          |
                 (Docker volume: pgdata)

  pgAdmin -------- backend-net -------- PostgreSQL
  PostgreSQL Exporter ------ backend-net + monitor-net
  Nginx Exporter ---------- dùng network namespace của Nginx
  Prometheus ------------- monitor-net ------ các exporter
  Grafana ---------------- monitor-net ------ Prometheus / Loki
  Promtail --------------- monitor-net ------ Loki
  cAdvisor --------------- monitor-net ------ Prometheus
```

### Phân tách mạng Docker

- **`frontend-net`**: Nginx và ứng dụng Flask.
- **`backend-net`**: Flask, PostgreSQL, pgAdmin và PostgreSQL Exporter.
- **`monitor-net`**: Prometheus, Grafana, Loki, Promtail, cAdvisor, PostgreSQL Exporter và Nginx.
- **Nginx Exporter** dùng `network_mode: service:nginx` để lấy số liệu từ Nginx qua `127.0.0.1/nginx_status` bên trong network namespace chung.
- PostgreSQL **không** cùng mạng trực tiếp với Nginx và **không publish** cổng 5432 ra máy chủ.

## 4. Cấu trúc thư mục

```text
ExpenseTracker/
├── app/
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── app.js
│       └── style.css
├── nginx/
│   └── conf.d/
│       └── default.conf
├── prometheus/
│   └── prometheus.yml
├── loki/
│   ├── loki-config.yaml
│   └── promtail-config.yaml
├── docker-compose.yml
├── compose.monitoring.yaml
├── .gitignore
└── README.md
```

**Không đưa lên GitHub**: `.env`, thư mục `secrets/`, bản sao lưu database, file dữ liệu nội bộ hoặc thông tin đăng nhập thực tế.

## 5. Yêu cầu triển khai

- Ubuntu trên máy ảo VMware (hoặc một máy Linux có Docker và Docker Compose plugin).
- Git, Docker Engine và `docker compose` đã được cài đặt.
- Tài khoản được phép chạy Docker.
- Máy Windows có SSH client để kết nối tới Ubuntu và tạo SSH Tunnel (nếu quản trị từ Windows).
- Các cổng máy chủ: **80** cho website, **22** cho SSH; các giao diện quản trị được giới hạn trên loopback của Ubuntu.

> Lưu ý: Đây là cấu hình môi trường thực hành. Cần bổ sung HTTPS, quản lý bí mật tập trung, phiên bản image cố định và các biện pháp bảo vệ bổ sung trước khi triển khai production.

## 6. Chuẩn bị cấu hình bảo mật

### 6.1. Tạo file `.env`

Tại thư mục gốc dự án, tạo file `.env` với **giá trị tự đặt**:

```dotenv
DB_PASSWORD=THAY_BANG_MAT_KHAU_POSTGRESQL_MANH
PGADMIN_PASSWORD=THAY_BANG_MAT_KHAU_PGADMIN_MANH
```

Sau đó phân quyền:

```bash
chmod 600 .env
```

Không commit file `.env`. **Với PostgreSQL đã có volume dữ liệu**, thay đổi `DB_PASSWORD` trong `.env` **không tự động thay đổi mật khẩu** tài khoản trong database; cần cập nhật mật khẩu PostgreSQL thực tế và đồng bộ môi trường Flask.

### 6.2. Mật khẩu dành riêng cho PostgreSQL Exporter

Cấu hình `compose.monitoring.yaml` đọc mật khẩu của tài khoản `metrics_user` từ:

```text
secrets/postgres_exporter_password
```

Tạo thư mục và file bí mật trên máy triển khai, sau đó phân quyền phù hợp với UID `1000` được cấu hình cho exporter:

```bash
mkdir -p secrets
# Tạo nội dung file bằng trình soạn thảo và không in mật khẩu ra terminal.
nano secrets/postgres_exporter_password
chmod 600 secrets/postgres_exporter_password
```

Tài khoản PostgreSQL `metrics_user` phải được tạo và cấp quyền giám sát cần thiết (ví dụ quyền `pg_monitor`). Mật khẩu trong file phải khớp mật khẩu của tài khoản này. Không commit thư mục `secrets/`.

### 6.3. Tạo volume dữ liệu

Hệ thống sử dụng volume PostgreSQL do Compose quản lý và hai volume external cho Grafana/pgAdmin:

```bash
docker volume create expense_grafana_data
docker volume create expense_pgadmin_data
```

> Với triển khai **mới**, đây là các volume rỗng để ứng dụng khởi tạo dữ liệu. Với máy đã chạy từ trước, phải di chuyển dữ liệu hiện có vào volume trước khi tạo lại các container. Không xóa volume chứa dữ liệu thật.

## 7. Triển khai và vận hành

### 7.1. Lấy mã nguồn

```bash
git clone https://github.com/thanhoanghieu/ExpenseTracker.git
cd ExpenseTracker
```

Chuẩn bị `.env`, file bí mật exporter và volume như Mục 6. Nếu sử dụng repository trên một máy khác, bạn cũng cần chuẩn bị PostgreSQL và các tài khoản phù hợp.

### 7.2. Kiểm tra cấu hình Docker Compose

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.monitoring.yaml \
  config --quiet
```

### 7.3. Khởi động hệ thống

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.monitoring.yaml \
  up -d --build
```

Xem trạng thái:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Xem log một dịch vụ:

```bash
docker compose -f docker-compose.yml -f compose.monitoring.yaml logs --tail=50 web
```

**Không sử dụng `docker compose down -v` khi muốn giữ dữ liệu.** Lệnh này có thể xóa các volume do Compose quản lý, bao gồm dữ liệu PostgreSQL.

## 8. Các địa chỉ truy cập

| Dịch vụ | Địa chỉ trên Ubuntu | Ghi chú |
|---|---|---|
| Expense Tracker | `http://192.168.77.129` | Nginx public cổng 80 |
| Health Check | `http://192.168.77.129:3000` | Trả JSON trạng thái ứng dụng/database |
| Grafana | `http://192.168.77.129:3000` | Chỉ truy cập từ máy chủ hoặc SSH Tunnel |
| pgAdmin | `http://192.168.77.129:5050` | Chỉ truy cập từ máy chủ hoặc SSH Tunnel |
| Prometheus | `http://192.168.77.129:9090` | Chỉ truy cập từ máy chủ hoặc SSH Tunnel |
| Loki | `http://192.168.77.129:3100/ready` | Chỉ truy cập từ máy chủ hoặc SSH Tunnel |

### SSH Tunnel trên Windows

Chạy lệnh dưới đây trong **CMD Windows**, thay `TAI_KHOAN_UBUNTU` và `IP_MAY_AO` cho phù hợp:

```cmd
ssh -N -L 3000:127.0.0.1:3000 -L 5050:127.0.0.1:5050 -L 9090:127.0.0.1:9090 -L 3100:127.0.0.1:3100 TAI_KHOAN_UBUNTU@IP_MAY_AO
```

Giữ cửa sổ CMD này mở. Sau đó sử dụng trên trình duyệt Windows:

- Grafana: `http://localhost:3000`
- pgAdmin: `http://localhost:5050`
- Prometheus: `http://localhost:9090/targets`
- Loki API: `http://localhost:3100/ready`

Trong pgAdmin, máy chủ PostgreSQL được kết nối qua **hostname `db`**, cổng **5432**, tên database **`expensetracker`** và tài khoản PostgreSQL đã cấu hình.

## 9. Giám sát bằng Prometheus và Grafana

Prometheus thu thập dữ liệu từ bốn scrape job:

1. **prometheus** – trạng thái chính Prometheus.
2. **cadvisor** – số liệu tài nguyên container.
3. **nginx** – trạng thái Nginx qua exporter.
4. **postgres** – trạng thái PostgreSQL qua exporter.

Kiểm tra tại `http://localhost:9090/targets` hoặc bằng lệnh:

```bash
curl -sG http://localhost:9090/api/v1/targets \
  --data-urlencode 'state=active' | python3 -c '
import json,sys
for t in json.load(sys.stdin).get("data",{}).get("activeTargets",[]):
    print(t["labels"].get("job"), t["health"])
'
```

Trong Grafana, tạo Prometheus data source với URL nội bộ **`http://prometheus:9090`**. Dashboard đã triển khai trên môi trường thực hành gồm các panel:

| Panel | Truy vấn PromQL |
|---|---|
| CPU container | `sum(rate(container_cpu_usage_seconds_total{image!=""}[5m]))` |
| RAM container | `sum(container_memory_working_set_bytes{image!=""})` |
| Trạng thái Nginx | `nginx_up` |
| Trạng thái PostgreSQL | `pg_up` |

**Lưu ý:** Dữ liệu dashboard nằm trong volume `expense_grafana_data` của môi trường đang chạy; cấu hình dashboard không tự xuất hiện khi clone repository sang một máy mới nếu chưa export/provision dashboard.

## 10. Logging tập trung bằng Loki và Promtail

Promtail phát hiện các Docker container và đẩy log sang Loki. Trong Grafana, thêm Loki data source với URL:

```text
http://loki:3100
```

Sử dụng **Grafana → Explore → Loki** để chạy các câu LogQL:

**Truy vấn 1 – Xem log ứng dụng Flask**

```logql
{container="/expense_web_app"}
```

**Truy vấn 2 – Lọc request HTTP GET**

```logql
{container="/expense_web_app"} |= "GET"
```

**Truy vấn 3 – Thống kê số dòng log theo container trong 5 phút**

```logql
sum by (container) (
  count_over_time({container=~".+"}[5m])
)
```

Kiểm tra Loki:

```bash
curl -i http://localhost:3100/ready
```

Ngay sau khởi động, Loki có thể tạm thời trả về HTTP 503 với thông báo ingester chưa sẵn sàng; kiểm tra lại khi khởi tạo hoàn tất.

> **Lưu ý vòng đời phần mềm:** Promtail là thành phần cũ, đã kết thúc hỗ trợ. Dự án sử dụng Promtail theo yêu cầu bài thực hành; trong triển khai dài hạn nên đánh giá việc chuyển sang Grafana Alloy hoặc giải pháp thu thập log còn được hỗ trợ.

## 11. Các biện pháp Hardening đã triển khai

- **Non-root container:** ứng dụng Flask chạy với `uid=10001(appuser)`, không chạy dưới tài khoản root.
- **Security Headers ở Nginx:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **Giới hạn cổng quản trị:** Grafana (3000), pgAdmin (5050), Prometheus (9090) và Loki (3100) chỉ bind vào `127.0.0.1` trên Ubuntu; truy cập từ Windows thông qua SSH Tunnel.
- **Network Isolation:** tách `frontend-net`, `backend-net`, `monitor-net`; PostgreSQL không tham gia mạng của Nginx.
- **Quản lý thông tin nhạy cảm:** mật khẩu sử dụng `.env` và file `secrets/` ở máy triển khai, không đẩy lên GitHub.
- **Phân quyền giám sát database:** PostgreSQL Exporter sử dụng tài khoản `metrics_user` dành riêng cho việc giám sát.
- **Dữ liệu bền vững:** PostgreSQL dùng `pgdata`, Grafana dùng `expense_grafana_data`, pgAdmin dùng `expense_pgadmin_data`.

### Giới hạn bảo mật hiện tại

cAdvisor đang sử dụng `privileged: true`; Promtail được cấp quyền đọc Docker socket. Đây là các quyền nhạy cảm có thể ảnh hưởng tới bảo mật máy chủ nếu container bị khai thác. Cấu hình này được sử dụng trong **môi trường lab** và không nên triển khai nguyên trạng lên Internet. Ngoài ra, nên bổ sung HTTPS, quản lý secret an toàn hơn, định phiên bản image cụ thể, kiểm toán quyền container và chính sách sao lưu/khôi phục trước khi vận hành thực tế.

## 12. Kiểm tra hệ thống sau triển khai

```bash
# Website và kết nối database
curl -i http://localhost/health

# Prometheus
curl -s http://localhost:9090/-/healthy

# Loki
curl -i http://localhost:3100/ready

# Kiểm tra người dùng trong container Flask
docker exec expense_web_app id

# Kiểm tra các mạng Docker của PostgreSQL và Nginx
docker inspect postgres_db --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}'
docker inspect nginx_proxy --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}'

# Kiểm tra các cổng được công khai
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

Kết quả triển khai đã được xác minh trên máy ảo thực hành: ứng dụng trả về `database: connected`, Prometheus có **4/4 targets UP**, Loki trả HTTP 200 `ready`, Flask chạy UID 10001, và PostgreSQL/Nginx không nằm chung Docker Network.

## 13. Quản lý mã nguồn và lịch sử commit

Repository: **[thanhoanghieu/ExpenseTracker](https://github.com/thanhoanghieu/ExpenseTracker)**

Các nhóm thay đổi chính:

- `feat: implement Expense Tracker web application` – ứng dụng Flask và giao diện quản lý chi tiêu.
- `build: configure Docker PostgreSQL and Nginx` – cấu hình triển khai và reverse proxy.
- `ops: add monitoring logging and security hardening` – monitoring, logging và phân tách mạng.

Kiểm tra lịch sử:

```bash
git log --oneline -5
```

## 14. Hướng phát triển

- Bổ sung kiểm thử tự động và quy trình CI/CD.
- Thêm HTTPS/TLS và tên miền cho website.
- Triển khai backup PostgreSQL định kỳ, thử nghiệm khôi phục dữ liệu.
- Bổ sung cảnh báo từ Prometheus/Alertmanager.
- Provision Grafana dashboards và data sources bằng file cấu hình.
- Nâng cấp hệ thống thu thập logs từ Promtail sang công cụ còn được hỗ trợ.
- Giảm đặc quyền container và triển khai chính sách bảo mật phù hợp môi trường production.

---

**Phạm vi:** Đề tài thực hành triển khai và giám sát hệ thống quản lý chi tiêu trên Ubuntu/VMware. Tài liệu này mô tả cấu hình đã thực hiện; khi triển khai lên máy mới cần chuẩn bị các biến môi trường, tài khoản và volume theo hướng dẫn.
