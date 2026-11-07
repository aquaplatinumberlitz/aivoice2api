// ABI/auth probe, with optional dictionary loading and PCM/WAV synthesis.
// Never modifies the engine or license.
// Build: x86_64-w64-mingw32-gcc -Wall -Wextra -Werror -O2 auth_probe.c -o build/auth_probe.exe
#include "engine_api.h"

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 3 && argc != 6 && argc != 7) {
        fprintf(stderr, "Usage: auth_probe.exe ABSOLUTE_ENGINE_DLL ABSOLUTE_AITALK_LIC [LANG_PACKAGE VOICE_PACKAGE VOICE_LICENSE [OUTPUT_WAV]]\n"
                        "Environment: AITALK_PRODUCT_NAME, AITALK_LICENSE_CODE (both required)\n");
        return 2;
    }
    const char *product = getenv("AITALK_PRODUCT_NAME");
    const char *code = getenv("AITALK_LICENSE_CODE");
    if (!product || !*product || !code || !*code) {
        fprintf(stderr, "Missing product name or license code; refusing empty auth arguments.\n");
        return 2;
    }
    HMODULE engine = LoadLibraryExA(argv[1], NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!engine) {
        fprintf(stderr, "LoadLibraryEx failed: %lu\n", GetLastError());
        return 3;
    }
    // Windows x64 uses one ABI. FARPROC is converted through void* to avoid
    // GCC's incompatible function pointer cast warning on the imported symbols.
#define RESOLVE(type, var, name) \
    type var = (type)(void *)GetProcAddress(engine, name); \
    if (!var) { fprintf(stderr, "Missing export: %s\n", name); FreeLibrary(engine); return 3; }
    RESOLVE(initialize_fn, initialize, "ai_ttsLibraryInitialize");
    RESOLVE(authenticate_fn, authenticate, "ai_ttsLibraryAuthenticate");
    RESOLVE(new_fn, talker_new, "ai_Talker_new");
    RESOLVE(delete_fn, talker_delete, "ai_Talker_delete");
    RESOLVE(terminate_fn, terminate, "ai_ttsLibraryTerminate");
    RESOLVE(load_lang_fn, load_lang, "ai_Talker_loadLangDic");
    RESOLVE(load_voice_fn, load_voice, "ai_Talker_loadVoiceDic");
    RESOLVE(select_fn, select_lang, "ai_Talker_selectLangDic");
    RESOLVE(select_fn, select_voice, "ai_Talker_selectVoiceDic");
    RESOLVE(talk_fn, talk, "ai_Talker_talk");
    RESOLVE(get_fs_fn, get_fs, "ai_Talker_getVoiceFs");
    RESOLVE(sink_new_fn, sink_new, "ai_TtsCallbackSink_new");
    RESOLVE(delete_fn, sink_delete, "ai_TtsCallbackSink_delete");
    RESOLVE(set_sink_fn, set_sink, "ai_Talker_setSink");
#undef RESOLVE
    printf("engine=%s\nlicense=%s\n", argv[1], argv[2]);
    int result = initialize(NULL);
    printf("initialize=%d\n", result);
    if (result != 0) { FreeLibrary(engine); return 4; }
    // License::authenticate compares arg3 to product (offset 0) and arg2 to
    // license code (offset 32): path, licenseCode, productName.
    result = authenticate(argv[2], code, product);
    printf("authenticate=%d\n", result);
    if (result != 0) {
        terminate();
        FreeLibrary(engine);
        return 5;
    }
    void *talker = talker_new();
    printf("talker=%p\n", talker);
    int ok = talker != NULL;
    if (talker && argc >= 6) {
        result = load_lang(talker, "standard", argv[3], 1);
        printf("loadLangDic=%d\n", result);
        ok = result == 0;
        if (ok) {
            result = select_lang(talker, "standard");
            printf("selectLangDic=%d\n", result);
            ok = result == 0;
        }
        if (ok) {
            result = load_voice(talker, "KotonohaAkane_ns_48", argv[4], 1, argv[5]);
            printf("loadVoiceDic=%d\n", result);
            ok = result == 0;
        }
        if (ok) {
            result = select_voice(talker, "KotonohaAkane_ns_48");
            printf("selectVoiceDic=%d\n", result);
            ok = result == 0;
        }
    }
    if (ok && argc == 7) {
        audio_output *out = calloc(1, sizeof(*out));
        int fs = get_fs(talker);
        printf("sampleRate=%d\n", fs);
        ok = out && fs > 0 && fs <= 192000;
        if (ok) {
            out->file = fopen(argv[6], "wb+");
            ok = out->file && wav_header(out->file, (unsigned)fs, 0);
        }
        void *sink = ok ? sink_new(on_event, out) : NULL;
        ok = ok && sink;
        if (ok) {
            result = set_sink(talker, sink);
            printf("setSink=%d\n", result);
            ok = result == 0;
        }
        if (ok) {
            result = talk(talker, "こんにちは、世界。", 0);
            printf("talk=%d pcmBytes=%u\n", result, out->bytes);
            ok = result == 0 && out->bytes > 0 && !out->failed;
            for (unsigned i = 0; i < 8; i++) printf("event[%u]=%u\n", i, out->events[i]);
        }
        if (sink) { set_sink(talker, NULL); sink_delete(sink); }
        if (out && out->file) {
            if (!wav_header(out->file, (unsigned)fs, out->bytes)) ok = 0;
            if (fclose(out->file) != 0) ok = 0;
        }
        free(out);
        if (!ok) remove(argv[6]);
    }
    if (talker) talker_delete(talker);
    printf("terminate=%d\n", terminate());
    FreeLibrary(engine);
    return ok ? 0 : 6;
}
