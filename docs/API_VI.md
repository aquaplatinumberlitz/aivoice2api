# Hợp đồng API aivoice2api

## Hợp đồng bổ sung

- `/v1/speak` giữ JSON `{text,voice}` và trả WAV như Anki cũ. Server-Timing
  có queue_ms/load_ms/first_pcm_ms/synth_ms/native_ms khi tổng hợp mới.
- `/healthz` thêm capabilities. Client cũ bỏ qua các field mới; client
  vntext tự lùi về WAV nếu backend không có `pcm-stream-v1`.
- `/v1/speak/stream`: JSON như speak, thêm session/revision tùy chọn.
  Trả `application/x-aivoice2-pcm`, prefix `AVS1`, sau đó frame
  `u8 kind + u32le size + payload`. Kind 1: PCM16 little endian mono 48 kHz;
  kind 2: JSON kết thúc thành công (cache/timing); kind 3: JSON lỗi.
  Không nhận kết thúc HTTP làm bằng chứng thành công. Chunk PCM tối đa 64 KiB.
- `/v1/prepare`: session/revision/voice/mode bắt buộc theo hợp đồng client;
  mode `warm` chỉ nạp/chọn Lang và voicebank, không tổng hợp câu giả hoặc
  dùng cache WAV. Mode `text` tổng hợp không phát, giới hạn 160 ký tự.
  Trả 202 accepted; đây là xác nhận xếp việc, chưa phải đã tạo xong audio.
- `/v1/cancel`: session/revision, xóa preparation chưa chạy và foreground
  revision cũ đang chờ của đúng session.
  Revision cũ hơn bị bỏ. Client không được dùng chung session giữa hai phiên.

Một worker native, foreground FIFO có ưu tiên hơn preparation. Tối đa 24
foreground chờ và 24 session preparation, mỗi session chỉ một việc mới
nhất. Preparation hết hạn sau 8 giây chờ. Foreground chờ tối đa 45 giây;
không hứa fairness cho preparation khi foreground liên tục bận.

Cache hit tra theo khóa text/voice/engine/worker/assets và trả ngay ngoài
khóa tổng hợp. WAV được publish bằng rename sau kiểm tra, không trả file
chưa viết xong. Server stream nhận PCM và vẫn tạo cache WAV song song.
Mỗi HTTP stream có bộ đệm tối đa 16 MiB; client chậm/mất kết nối không
chặn native worker. Audio lỗi/truncated có thể đã phát một phần trước khi
được phát hiện; kết quả đó không được client đưa vào cache.

Preparation **đang chạy trong DLL không bị hủy**; có thể làm câu foreground
vừa đến phải chờ phần còn lại. Đó là giới hạn hiện tại, không đánh đồng với
hủy queued job hoặc dừng âm thanh.

## Cache WAV và chuẩn bị trước

Cache backend giới hạn **512 MiB**, loại file ít dùng gần đây nhất khi vượt
quota và dọn WAV không được dùng trong **7 ngày**. Dọn lúc khởi động, sau khi
publish audio mới và mỗi 60 giây khi service chạy. Cache hit cập nhật mtime
để thứ tự sử dụng vẫn đúng trên filesystem `noatime` và sau khi restart.
Chỉ dọn file thường có tên `aivoice2_<64 ký tự hex>.wav` trong cache_dir;
không quét đệ quy, không theo symlink. Temp đang ghi dùng tên khác.

Lease bảo vệ file đang tổng hợp và đang trả WAV/PCM. Nếu file được giữ làm
quota tạm vượt mức, dọn lại khi lease cuối đóng. Cache hit không chờ native
lock; việc dọn cache dùng khóa riêng. `/healthz.wav_cache` báo quota, tuổi
hết hạn, số file/byte ở lần dọn gần nhất, tổng số đã xóa và trạng thái hoãn.
Audio vẫn stream PCM sang vntext trong lúc worker ghi WAV cache song song.

Lookahead, cache RAM và player là chính sách client, không phải API server.
Xem [vntext TTS_CLIENT](https://github.com/aquaplatinumberlitz/vntext/blob/main/docs/TTS_CLIENT_VI.md)
để chỉnh giới hạn phía visual novel. Anki lưu media độc lập với cache backend.

## Giới hạn request và lỗi

- Server chỉ bind 127.0.0.1 theo port config. Đây là API local, không có auth
  HTTP; không expose trực tiếp ra LAN/Internet.
- Body JSON object tối đa 65536 byte. Text synth không rỗng/NUL, tối đa
  4096 ký tự và 16384 byte UTF-8; prepare text tối đa 160 ký tự.
- Voice lấy id từ GET /v1/voices. Bỏ voice thì dùng default còn khả dụng.
- Session ASCII tối đa 96 ký tự, bắt buộc không rỗng với prepare/cancel;
  revision là integer từ 0 đến dưới 2^63. Client nên gửi mode/voice/revision
  rõ ràng dù một số trường có default để giữ tương thích.
- Health 200 khi engine ready, 503 nếu chưa ready. Voices trả catalog và
  default_voice; các path filesystem/license không trả ra catalog.
- Request sai trả 400 JSON error, path không có trả 404; synth/busy/runtime
  lỗi trả 503. Stream đã gửi header 200 thì báo lỗi bằng frame kind 3;
  client phải kiểm frame kết thúc, không chỉ nhìn status 200.

Contract /v1/speak WAV giữ tương thích addon cũ. Không tự thêm tham số tốc
độ/pitch hoặc hàng đợi job/status nếu server chưa triển khai chúng. Đổi API
không tương thích cần version mới và cập nhật test/lock các client.
