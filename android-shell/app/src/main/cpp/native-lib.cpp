#include <jni.h>
#include <android/log.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

#include "llama.h"

#define LOG_TAG "AIWorkbenchNative"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace {
std::mutex g_mutex;
std::atomic_bool g_stop{false};
llama_model * g_model = nullptr;
llama_context * g_context = nullptr;
const llama_vocab * g_vocab = nullptr;
bool g_backend_initialized = false;
int g_context_size = 0;
int g_threads = 0;
std::vector<llama_token> g_cache_tokens;

std::string json_escape(const std::string & value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        switch (c) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\b': out << "\\b"; break;
            case '\f': out << "\\f"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c < 0x20) {
                    const char * hex = "0123456789abcdef";
                    out << "\\u00" << hex[(c >> 4) & 0xF] << hex[c & 0xF];
                } else {
                    out << static_cast<char>(c);
                }
        }
    }
    return out.str();
}

std::string ok_json(const std::string & fields = "") {
    return std::string("{\"ok\":true") + (fields.empty() ? "" : "," + fields) + "}";
}

std::string error_json(const std::string & message) {
    return "{\"ok\":false,\"message\":\"" + json_escape(message) + "\"}";
}

void unload_locked() {
    g_stop.store(true);
    g_cache_tokens.clear();
    if (g_context != nullptr) {
        llama_free(g_context);
        g_context = nullptr;
    }
    if (g_model != nullptr) {
        llama_model_free(g_model);
        g_model = nullptr;
    }
    g_vocab = nullptr;
    g_context_size = 0;
    g_threads = 0;
}

std::vector<llama_token> tokenize(const std::string & text) {
    const int required = -llama_tokenize(
        g_vocab,
        text.data(),
        static_cast<int32_t>(text.size()),
        nullptr,
        0,
        true,
        true
    );
    if (required <= 0) return {};

    std::vector<llama_token> tokens(static_cast<size_t>(required));
    const int count = llama_tokenize(
        g_vocab,
        text.data(),
        static_cast<int32_t>(text.size()),
        tokens.data(),
        static_cast<int32_t>(tokens.size()),
        true,
        true
    );
    if (count < 0) return {};
    tokens.resize(static_cast<size_t>(count));
    return tokens;
}

std::string token_piece(llama_token token) {
    std::vector<char> buffer(256);
    int count = llama_token_to_piece(
        g_vocab,
        token,
        buffer.data(),
        static_cast<int32_t>(buffer.size()),
        0,
        true
    );
    if (count < 0) {
        buffer.resize(static_cast<size_t>(-count));
        count = llama_token_to_piece(
            g_vocab,
            token,
            buffer.data(),
            static_cast<int32_t>(buffer.size()),
            0,
            true
        );
    }
    return count > 0 ? std::string(buffer.data(), static_cast<size_t>(count)) : std::string();
}

bool emit_chunk(JNIEnv * env, jobject self, const std::string & chunk) {
    if (chunk.empty()) return true;
    jclass cls = env->GetObjectClass(self);
    if (cls == nullptr) return false;
    jmethodID callback = env->GetMethodID(cls, "onNativeTokenChunk", "(Ljava/lang/String;)V");
    if (callback == nullptr) {
        env->DeleteLocalRef(cls);
        return false;
    }
    jstring value = env->NewStringUTF(chunk.c_str());
    env->CallVoidMethod(self, callback, value);
    env->DeleteLocalRef(value);
    env->DeleteLocalRef(cls);
    if (env->ExceptionCheck()) {
        env->ExceptionDescribe();
        env->ExceptionClear();
        return false;
    }
    return true;
}

size_t common_prefix(const std::vector<llama_token> & a, const std::vector<llama_token> & b) {
    const size_t limit = std::min(a.size(), b.size());
    size_t i = 0;
    while (i < limit && a[i] == b[i]) ++i;
    return i;
}
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_xonoxo_aiworkbench_NativeRuntime_nativeLoadModel(
    JNIEnv * env,
    jobject,
    jstring path,
    jint context_size,
    jint threads
) {
    std::lock_guard<std::mutex> lock(g_mutex);
    unload_locked();
    g_stop.store(false);

    if (!g_backend_initialized) {
        llama_backend_init();
        g_backend_initialized = true;
    }

    const char * raw_path = env->GetStringUTFChars(path, nullptr);
    if (raw_path == nullptr) {
        return env->NewStringUTF(error_json("Invalid model path").c_str());
    }

    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = 0;
    g_model = llama_model_load_from_file(raw_path, model_params);
    env->ReleaseStringUTFChars(path, raw_path);

    if (g_model == nullptr) {
        return env->NewStringUTF(error_json("llama.cpp could not load this GGUF file").c_str());
    }

    g_vocab = llama_model_get_vocab(g_model);
    g_context_size = std::clamp(static_cast<int>(context_size), 512, 32768);
    g_threads = std::clamp(static_cast<int>(threads), 1, 16);

    llama_context_params params = llama_context_default_params();
    params.n_ctx = static_cast<uint32_t>(g_context_size);
    params.n_batch = static_cast<uint32_t>(std::min(g_context_size, 1024));
    params.n_ubatch = static_cast<uint32_t>(std::min(g_context_size, 512));
    params.n_threads = g_threads;
    params.n_threads_batch = g_threads;
    params.no_perf = false;

    g_context = llama_init_from_model(g_model, params);
    if (g_context == nullptr) {
        unload_locked();
        return env->NewStringUTF(error_json("Could not allocate model context").c_str());
    }

    char description[256] = {};
    llama_model_desc(g_model, description, sizeof(description));

    std::ostringstream fields;
    fields << "\"model\":\"" << json_escape(description) << "\""
           << ",\"context\":" << g_context_size
           << ",\"threads\":" << g_threads
           << ",\"model_bytes\":" << llama_model_size(g_model)
           << ",\"parameters\":" << llama_model_n_params(g_model)
           << ",\"system_info\":\"" << json_escape(llama_print_system_info()) << "\"";

    const std::string result = ok_json(fields.str());
    return env->NewStringUTF(result.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_xonoxo_aiworkbench_NativeRuntime_nativeGenerate(
    JNIEnv * env,
    jobject self,
    jstring prompt_value,
    jint max_tokens,
    jfloat temperature,
    jfloat top_p,
    jint top_k,
    jfloat repeat_penalty
) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (g_model == nullptr || g_context == nullptr || g_vocab == nullptr) {
        return env->NewStringUTF(error_json("No model is loaded").c_str());
    }

    const char * raw_prompt = env->GetStringUTFChars(prompt_value, nullptr);
    if (raw_prompt == nullptr) {
        return env->NewStringUTF(error_json("Invalid prompt").c_str());
    }
    std::string prompt(raw_prompt);
    env->ReleaseStringUTFChars(prompt_value, raw_prompt);

    const std::vector<llama_token> prompt_tokens = tokenize(prompt);
    if (prompt_tokens.empty()) {
        return env->NewStringUTF(error_json("Prompt tokenization failed").c_str());
    }

    const int predict = std::clamp(static_cast<int>(max_tokens), 1, 4096);
    if (static_cast<int>(prompt_tokens.size()) + predict >= g_context_size) {
        return env->NewStringUTF(error_json("Prompt and generation exceed context window").c_str());
    }

    g_stop.store(false);
    llama_memory_t memory = llama_get_memory(g_context);

    size_t reused = common_prefix(g_cache_tokens, prompt_tokens);
    if (reused < g_cache_tokens.size()) {
        if (!llama_memory_seq_rm(memory, 0, static_cast<llama_pos>(reused), -1)) {
            llama_memory_clear(memory, false);
            reused = 0;
        }
        g_cache_tokens.resize(reused);
    }

    using clock = std::chrono::steady_clock;
    const auto start = clock::now();

    const size_t batch_limit = 1024;
    for (size_t offset = reused; offset < prompt_tokens.size(); offset += batch_limit) {
        const size_t count = std::min(batch_limit, prompt_tokens.size() - offset);
        llama_batch batch = llama_batch_get_one(
            const_cast<llama_token *>(prompt_tokens.data() + offset),
            static_cast<int32_t>(count)
        );
        if (llama_decode(g_context, batch) != 0) {
            return env->NewStringUTF(error_json("Prompt decode failed").c_str());
        }
        g_cache_tokens.insert(
            g_cache_tokens.end(),
            prompt_tokens.begin() + static_cast<std::ptrdiff_t>(offset),
            prompt_tokens.begin() + static_cast<std::ptrdiff_t>(offset + count)
        );
    }

    const auto prompt_end = clock::now();

    llama_sampler_chain_params chain_params = llama_sampler_chain_default_params();
    chain_params.no_perf = false;
    llama_sampler * sampler = llama_sampler_chain_init(chain_params);
    llama_sampler_chain_add(sampler, llama_sampler_init_penalties(
        std::min(g_context_size, 128),
        std::max(1.0f, static_cast<float>(repeat_penalty)),
        0.0f,
        0.0f
    ));
    llama_sampler_chain_add(sampler, llama_sampler_init_top_k(std::max(0, static_cast<int>(top_k))));
    llama_sampler_chain_add(sampler, llama_sampler_init_top_p(
        std::clamp(static_cast<float>(top_p), 0.01f, 1.0f),
        1
    ));
    llama_sampler_chain_add(sampler, llama_sampler_init_temp(
        std::max(0.01f, static_cast<float>(temperature))
    ));
    llama_sampler_chain_add(sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));

    int generated = 0;
    bool saw_first_token = false;
    auto first_token_time = prompt_end;
    auto last_emit = prompt_end;
    std::string pending;

    for (int i = 0; i < predict && !g_stop.load(); ++i) {
        const llama_token next = llama_sampler_sample(sampler, g_context, -1);
        llama_sampler_accept(sampler, next);
        if (llama_vocab_is_eog(g_vocab, next)) break;

        if (!saw_first_token) {
            first_token_time = clock::now();
            saw_first_token = true;
        }

        pending += token_piece(next);

        llama_token mutable_next = next;
        llama_batch batch = llama_batch_get_one(&mutable_next, 1);
        if (llama_decode(g_context, batch) != 0) {
            llama_sampler_free(sampler);
            return env->NewStringUTF(error_json("Generation decode failed").c_str());
        }

        g_cache_tokens.push_back(next);
        generated++;

        const auto now = clock::now();
        const auto millis = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_emit).count();
        if (pending.size() >= 96 || millis >= 40) {
            if (!emit_chunk(env, self, pending)) {
                llama_sampler_free(sampler);
                return env->NewStringUTF(error_json("Token callback failed").c_str());
            }
            pending.clear();
            last_emit = now;
        }
    }

    if (!pending.empty()) {
        emit_chunk(env, self, pending);
    }

    llama_sampler_free(sampler);

    const auto end = clock::now();
    const double prompt_seconds = std::chrono::duration<double>(prompt_end - start).count();
    const double ttft_seconds = saw_first_token
        ? std::chrono::duration<double>(first_token_time - start).count()
        : prompt_seconds;
    const double generation_seconds = std::chrono::duration<double>(end - prompt_end).count();
    const double total_seconds = std::chrono::duration<double>(end - start).count();
    const double rate = generation_seconds > 0.0 ? generated / generation_seconds : 0.0;

    std::ostringstream fields;
    fields << "\"prompt_tokens\":" << prompt_tokens.size()
           << ",\"cached_prompt_tokens\":" << reused
           << ",\"evaluated_prompt_tokens\":" << (prompt_tokens.size() - reused)
           << ",\"tokens\":" << generated
           << ",\"prompt_seconds\":" << prompt_seconds
           << ",\"ttft_seconds\":" << ttft_seconds
           << ",\"generation_seconds\":" << generation_seconds
           << ",\"total_seconds\":" << total_seconds
           << ",\"tokens_per_second\":" << rate
           << ",\"stopped\":" << (g_stop.load() ? "true" : "false");

    const std::string result = ok_json(fields.str());
    return env->NewStringUTF(result.c_str());
}

extern "C" JNIEXPORT void JNICALL
Java_com_xonoxo_aiworkbench_NativeRuntime_nativeStop(JNIEnv *, jobject) {
    g_stop.store(true);
}

extern "C" JNIEXPORT void JNICALL
Java_com_xonoxo_aiworkbench_NativeRuntime_nativeUnload(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    unload_locked();
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_xonoxo_aiworkbench_NativeRuntime_nativeSystemInfo(JNIEnv * env, jobject) {
    if (!g_backend_initialized) {
        llama_backend_init();
        g_backend_initialized = true;
    }
    const char * info = llama_print_system_info();
    return env->NewStringUTF(info != nullptr ? info : "llama.cpp CPU backend");
}
