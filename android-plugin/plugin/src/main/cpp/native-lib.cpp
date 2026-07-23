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

#define LOG_TAG "LocalAI-Native"
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

std::string token_piece(llama_token token) {
    std::vector<char> buffer(256);
    int count = llama_token_to_piece(g_vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    if (count < 0) {
        buffer.resize(static_cast<size_t>(-count));
        count = llama_token_to_piece(g_vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    }
    return count > 0 ? std::string(buffer.data(), static_cast<size_t>(count)) : std::string();
}

bool emit_token(JNIEnv * env, jobject self, const std::string & token) {
    jclass cls = env->GetObjectClass(self);
    if (cls == nullptr) return false;
    jmethodID callback = env->GetMethodID(cls, "onNativeToken", "(Ljava/lang/String;)V");
    if (callback == nullptr) {
        env->DeleteLocalRef(cls);
        return false;
    }
    jstring value = env->NewStringUTF(token.c_str());
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

std::vector<llama_token> tokenize(const std::string & prompt) {
    const int required = -llama_tokenize(
        g_vocab,
        prompt.data(),
        static_cast<int32_t>(prompt.size()),
        nullptr,
        0,
        true,
        true
    );
    if (required <= 0) return {};
    std::vector<llama_token> tokens(static_cast<size_t>(required));
    const int count = llama_tokenize(
        g_vocab,
        prompt.data(),
        static_cast<int32_t>(prompt.size()),
        tokens.data(),
        static_cast<int32_t>(tokens.size()),
        true,
        true
    );
    if (count < 0) return {};
    tokens.resize(static_cast<size_t>(count));
    return tokens;
}
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_xonoxo_localai_LocalAIPlugin_nativeLoadModel(
    JNIEnv * env,
    jobject,
    jstring path,
    jint context_size,
    jint threads,
    jint gpu_layers
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
    model_params.n_gpu_layers = std::max(0, static_cast<int>(gpu_layers));
    g_model = llama_model_load_from_file(raw_path, model_params);
    env->ReleaseStringUTFChars(path, raw_path);

    if (g_model == nullptr) {
        return env->NewStringUTF(error_json("llama.cpp could not load this GGUF file").c_str());
    }

    g_vocab = llama_model_get_vocab(g_model);
    g_context_size = std::clamp(static_cast<int>(context_size), 512, 32768);
    g_threads = std::clamp(static_cast<int>(threads), 1, 16);

    llama_context_params context_params = llama_context_default_params();
    context_params.n_ctx = static_cast<uint32_t>(g_context_size);
    context_params.n_batch = static_cast<uint32_t>(std::min(g_context_size, 1024));
    context_params.n_ubatch = static_cast<uint32_t>(std::min(g_context_size, 512));
    context_params.n_threads = g_threads;
    context_params.n_threads_batch = g_threads;
    context_params.no_perf = false;

    g_context = llama_init_from_model(g_model, context_params);
    if (g_context == nullptr) {
        unload_locked();
        return env->NewStringUTF(error_json("Could not allocate the model context; reduce context size").c_str());
    }

    char description[256] = {};
    llama_model_desc(g_model, description, sizeof(description));
    std::ostringstream fields;
    fields << "\"model\":\"" << json_escape(description) << "\""
           << ",\"backend\":\"CPU\""
           << ",\"context\":" << g_context_size
           << ",\"threads\":" << g_threads
           << ",\"model_bytes\":" << llama_model_size(g_model)
           << ",\"parameters\":" << llama_model_n_params(g_model);

    const std::string result = ok_json(fields.str());
    return env->NewStringUTF(result.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_xonoxo_localai_LocalAIPlugin_nativeGenerate(
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
        std::ostringstream message;
        message << "Prompt needs " << prompt_tokens.size()
                << " tokens plus " << predict
                << " generated tokens, exceeding context " << g_context_size;
        return env->NewStringUTF(error_json(message.str()).c_str());
    }

    g_stop.store(false);
    llama_memory_clear(llama_get_memory(g_context), false);

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
    llama_sampler_chain_add(sampler, llama_sampler_init_temp(std::max(0.01f, static_cast<float>(temperature))));
    llama_sampler_chain_add(sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));

    const auto start = std::chrono::steady_clock::now();
    int generated = 0;

    const size_t batch_limit = 1024;
    for (size_t offset = 0; offset < prompt_tokens.size(); offset += batch_limit) {
        const size_t count = std::min(batch_limit, prompt_tokens.size() - offset);
        llama_batch batch = llama_batch_get_one(
            const_cast<llama_token *>(prompt_tokens.data() + offset),
            static_cast<int32_t>(count)
        );
        if (llama_decode(g_context, batch) != 0) {
            llama_sampler_free(sampler);
            return env->NewStringUTF(error_json("Prompt decode failed").c_str());
        }
    }

    for (int i = 0; i < predict && !g_stop.load(); ++i) {
        const llama_token next = llama_sampler_sample(sampler, g_context, -1);
        llama_sampler_accept(sampler, next);
        if (llama_vocab_is_eog(g_vocab, next)) break;

        const std::string piece = token_piece(next);
        if (!piece.empty() && !emit_token(env, self, piece)) {
            llama_sampler_free(sampler);
            return env->NewStringUTF(error_json("Token callback failed").c_str());
        }

        llama_token mutable_next = next;
        llama_batch batch = llama_batch_get_one(&mutable_next, 1);
        if (llama_decode(g_context, batch) != 0) {
            llama_sampler_free(sampler);
            return env->NewStringUTF(error_json("Generation decode failed").c_str());
        }
        generated++;
    }

    llama_sampler_free(sampler);

    const auto end = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(end - start).count();
    const double rate = seconds > 0.0 ? generated / seconds : 0.0;

    std::ostringstream fields;
    fields << "\"tokens\":" << generated
           << ",\"seconds\":" << seconds
           << ",\"tokens_per_second\":" << rate
           << ",\"stopped\":" << (g_stop.load() ? "true" : "false");

    const std::string result = ok_json(fields.str());
    return env->NewStringUTF(result.c_str());
}

extern "C" JNIEXPORT void JNICALL
Java_com_xonoxo_localai_LocalAIPlugin_nativeStop(JNIEnv *, jobject) {
    g_stop.store(true);
}

extern "C" JNIEXPORT void JNICALL
Java_com_xonoxo_localai_LocalAIPlugin_nativeUnload(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    unload_locked();
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_xonoxo_localai_LocalAIPlugin_nativeSystemInfo(JNIEnv * env, jobject) {
    if (!g_backend_initialized) {
        llama_backend_init();
        g_backend_initialized = true;
    }
    const char * info = llama_print_system_info();
    return env->NewStringUTF(info != nullptr ? info : "llama.cpp CPU backend");
}
