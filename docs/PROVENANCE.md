# Provenance của lần tách backend

Ngày 2026-11-07. Nguồn chính từ các commit đã push trước lần tách:

| File đích | Nguồn |
|---|---|
| `runtime/server.py`, `scheduler.py`, `wav_cache.py`, `engine_worker.c`, `engine_api.h` | `aquaplatinumberlitz/vntext` commit `b42293c593800d2301fa68652406d3577e14d28f`, thư mục `integrations/aivoice2/` |
| `runtime/runtime_config.py`, `runtime_cli.py`, `run_auth_probe.py`, `voice_registry.json` | `aquaplatinumberlitz/aivoice2-anki` commit `e0ca50febfb14b60fac8b8ae8150a8840aefa6dd`, thư mục `src/daemon/` |
| `runtime/auth_probe.c` | Cùng commit Anki, `developer-kit/src/daemon/auth_probe.c` |
| `tests/test_tts_backend.py` | Cùng commit vntext, `tests/` |
| `tests/test_runtime_config.py` | Cùng commit Anki, `developer-kit/tests/` |
| `docs/CONNECT_VI.md` | Cùng commit vntext, `docs/AIVOICE2_CONNECT_VI.md`, đã cập nhật đường dẫn và nguồn chính |

Thay đổi khi chuyển: test import support ngay trong repo; auth probe tìm source
C bên cạnh script; lỗi worker dẫn tới journal đúng instance thay vì unit cũ;
build đóng gói source/worker theo version và manifest.
Giao thức native, HTTP và logic chọn giọng được giữ nguyên.

Các ghi chú RE gốc tiếp tục lưu ở Anki `developer-kit/`; chúng phản ánh binary
2.14.1 đã kiểm chứng. Không coi finding đó là bảo đảm cho phiên bản engine khác.
Engine và runtime lic vẫn bị kiểm hash theo baseline hiện tại; lần tách repo
không mở rộng danh sách binary tương thích hoặc thay đổi activation GUI.
