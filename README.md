# aivoice2api

Backend TTS local dùng chung cho addon Anki và vntext trên Linux x86-64/Wine.
Đây là nguồn backend chính; client gọi HTTP, không cần mở Editor hoặc Anki.

- Chỉ mục: [docs/README](docs/README.md).
- Dev mới: [cài đặt và nối hai client](docs/CONNECT_VI.md).
- API WAV, PCM streaming, prepare/cancel và cache: [hợp đồng API](docs/API_VI.md).
- Nguồn chuyển vào và phạm vi binary: [provenance](docs/PROVENANCE.md).
- Build và phân phối cho client: [quy trình phát hành](docs/RELEASE_VI.md).

```bash
python3 -m unittest discover -s tests -v
python3 tools/build_runtime.py
```

Test dùng fixture, không cần Wine, bản cài A.I.VOICE2 hay tài khoản dịch.
Build cần Python 3.11+ và `x86_64-w64-mingw32-gcc`. Release chứa worker đã
build, server và support modules; máy khách không cần MinGW.

Source nằm ở `runtime/`, test ở `tests/`. `tools/build_runtime.py` xuất artifact
có version, commit nguồn, manifest và SHA-256. Anki/vntext ghim phiên bản bằng
`aivoice2api.lock.json`; không tự nâng cấp theo nhánh main hoặc latest.

Repo không chứa DLL Editor/engine, MSI, Lang, voicebanks, activation cá nhân
hoặc Wine prefix. Runtime vẫn cần app và dữ liệu tương thích do bộ cài quản lý.
GUI patch và trình quản lý cài đặt tiếp tục nằm trong repo Anki.

Bản phát hành Anki 0.2.0 giữ snapshot backend WAV lịch sử để checksum cũ còn
kiểm chứng được. Không sửa snapshot đó làm backend mới; mọi phát triển backend
sau khi tách thực hiện tại đây. Runtime đang cài không tự đổi khi clone repo.
