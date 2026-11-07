# aivoice2api

Backend A.I.VOICE2 local dùng chung cho Anki và vntext trên Linux/Wine.
Một engine giữ nóng; Anki nhận WAV, vntext có PCM streaming và chuẩn bị câu.

**[Lần đầu cài cả hệ thống? Làm Quickstart A–Z tại đây](https://github.com/aquaplatinumberlitz/aivoice2-anki/blob/main/docs/QUICKSTART_VI.md).**

Bộ cài [aivoice2-anki 0.3.1](https://github.com/aquaplatinumberlitz/aivoice2-anki/releases/tag/v0.3.1)
đã kèm runtime mới. Người dùng cài bộ đó, không cần clone/build repo này
hoặc cài hai service. MSI 2.14.1/Lang/Voice nhận riêng từ bên bàn giao.
Repo và Release private cần quyền đọc; khách có thể nhận bộ cài trực tiếp.

## Chọn đúng đường đi

| Việc cần làm | Đọc |
|---|---|
| Cài mới, nghe trong Anki/vntext | [Quickstart chung](https://github.com/aquaplatinumberlitz/aivoice2-anki/blob/main/docs/QUICKSTART_VI.md) |
| Backend đã cài nhưng lỗi / cần nâng cấp có backup | [Vận hành và kết nối nâng cao](docs/CONNECT_VI.md) |
| Viết client HTTP, hiểu PCM/prepare/cache | [API](docs/API_VI.md) |
| Dev sửa/build/phát hành backend | [Build và release](docs/RELEASE_VI.md) |
| Hiểu ba repo và nguồn RE | [Kiến trúc](docs/ARCHITECTURE_VI.md), [provenance](docs/PROVENANCE.md) |
| Tìm mọi tài liệu | [Chỉ mục](docs/README.md) |

## Source dành cho dev

```text
runtime/     server, scheduler, cache, config/CLI, worker C và registry nền
tests/       test backend/config bằng fixture
tools/       build artifact đã ghim version/commit/checksum
docs/        API, kiến trúc, vận hành và phát hành
```

Trong checkout này, test không cần Wine hoặc dữ liệu giọng:

```bash
python3 -m unittest discover -s tests -v
```

Build worker cần MinGW/Python 3.11+ theo RELEASE_VI; khách nhận worker đã
build trong bộ cài. Không đưa DLL Editor/engine, MSI, Lang, giọng, activation
cá nhân hoặc prefix vào repo. Source addon/installer/helper nằm ở src của
Anki; source extraction/overlay/player nằm ở vntext. Không phát triển bản
fork backend trong repo client hoặc chỉnh runtime đã cài thay cho source.
