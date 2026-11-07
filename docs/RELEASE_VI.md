# Build, phát hành và ghim backend

Backend có version độc lập với addon/bundle Anki và vntext. Lần tách đầu là
`aivoice2api 0.1.0`; đây không phải version mới của engine A.I.VOICE2.

## Build cho dev

Checkout sạch, Python 3.11+ và MinGW x86-64:

```bash
python3 -m unittest discover -s tests -v
python3 tools/build_runtime.py
```

Output mặc định:

```text
dist/
  aivoice2api-0.1.0/
    backend-manifest.json
    runtime/
      server.py, scheduler.py, wav_cache.py
      runtime_config.py, runtime_cli.py, run_auth_probe.py
      voice_registry.json, engine_worker.exe, worker-manifest.json
      engine_worker.c, engine_api.h, auth_probe.c
  aivoice2api-0.1.0.tar.gz
  aivoice2api-0.1.0.tar.gz.sha256
```

Build không đọc bản cài cá nhân hoặc license, không khởi động Wine và không
chép vào runtime khách. Source runtime/build chưa commit sẽ bị từ chối.
Dùng `--output /đường/dẫn/mới` khi đã có output. Cùng commit/compiler tạo
cùng archive: metadata tar/gzip và PE timestamp cố định. Compiler khác có
thể tạo hash khác; artifact phát hành đã kiểm chứng là file dùng phân phối.

## Phát hành trên GitHub private

1. Test, cập nhật VERSION và tài liệu; commit source sạch.
2. Build artifact, ghi lại commit + SHA-256 + toolchain trong manifest.
3. Tag `v<VERSION>` đúng commit đã build và upload archive/checksum vào
   GitHub Release của `aquaplatinumberlitz/aivoice2api`.
4. Trong Anki/vntext, cập nhật cùng `aivoice2api.lock.json`: version,
   source_commit, artifact, artifact_sha256 và release_tag. Không trỏ latest.
5. Cập nhật toàn bộ runtime payload theo Anki INSTALLER, test client WAV/PCM và backup/rollback
   phù hợp. Commit/push lock và tài liệu client sau khi artifact đã có sẵn.

Không thay asset cũ cùng version bằng nội dung khác. Nâng version nếu sửa
runtime. README/API hiện hành theo main; khi debug khách dùng source/tag và
manifest khớp artifact khách thực sự cài.

## Khách và dev nhận artifact

Repo private cần tài khoản được cấp quyền đọc. Dev có gh đã đăng nhập:

```bash
gh release download v0.1.0 --repo aquaplatinumberlitz/aivoice2api   --pattern 'aivoice2api-0.1.0.tar.gz*' --dir ./backend-download
cd backend-download
sha256sum -c aivoice2api-0.1.0.tar.gz.sha256
```

Anki `tools/prepare_setup.py` còn đối chiếu archive với SHA-256 trong lock,
không chỉ tin file checksum tải kèm. Khách không cần tài khoản GitHub nếu
nhà phát hành cung cấp bộ cài Anki đầy đủ; không cần compiler.

## Ranh giới đóng gói

Runtime artifact không mang MSI, engine DLL, Lang, voicebanks, GUI patch,
addon hoặc prefix. Setup Anki lấy GUI/addon từ bundle và backend từ release
này. Anki 0.3.1 đã đóng gói runtime mới mặc định; bản 0.2.0 giữ trong tag
lịch sử, checksum bản Anki hiện hành được tạo riêng bằng tools/build_release.py.

Cài mới chạy start-setup.sh của bộ Anki 0.3.1. Bản đã cài nâng cấp có backup/manifest/receipt
riêng theo [CONNECT_VI.md mục 8](CONNECT_VI.md#8-nâng-cấp-backend-chung-để-có-streamingcache-quota-dev-tùy-chọn).
Đây chưa phải updater crash-safe hoặc cơ chế tự update trên máy khách.
