val stableKeystoreFile = System.getenv("AI_WORKBENCH_KEYSTORE_FILE")
val stableKeyAlias = System.getenv("AI_WORKBENCH_KEY_ALIAS")
val stableStorePassword = System.getenv("AI_WORKBENCH_KEYSTORE_PASSWORD")
val stableKeyPassword = System.getenv("AI_WORKBENCH_KEY_PASSWORD")
val stableSigningAvailable = listOf(
    stableKeystoreFile,
    stableKeyAlias,
    stableStorePassword,
    stableKeyPassword,
).all { !it.isNullOrBlank() }

val buildVersionCode =
    System.getenv("AI_WORKBENCH_VERSION_CODE")?.toIntOrNull() ?: 4
val buildVersionName =
    System.getenv("AI_WORKBENCH_VERSION_NAME") ?: "0.4.0-kernel2"

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.xonoxo.aiworkbench"
    compileSdk = 35
    ndkVersion = "28.1.13356709"

    defaultConfig {
        applicationId = "com.xonoxo.aiworkbench.k2"
        minSdk = 28
        targetSdk = 35
        versionCode = buildVersionCode
        versionName = buildVersionName

        ndk {
            abiFilters += listOf("arm64-v8a")
        }

        externalNativeBuild {
            cmake {
                cppFlags += listOf("-std=c++17", "-O3", "-fexceptions", "-frtti")
                arguments += listOf(
                    "-DANDROID_STL=c++_shared",
                    "-DCMAKE_BUILD_TYPE=Release",
                    "-DGGML_NATIVE=OFF",
                    "-DGGML_CPU_KLEIDIAI=ON",
                    "-DGGML_CPU_REPACK=ON",
                    "-DGGML_OPENMP=OFF",
                    "-DGGML_LLAMAFILE=OFF",
                    "-DGGML_BACKEND_DL=OFF",
                    "-DLLAMA_OPENSSL=OFF",
                    "-DLLAMA_BUILD_TESTS=OFF",
                    "-DLLAMA_BUILD_TOOLS=OFF",
                    "-DLLAMA_BUILD_EXAMPLES=OFF",
                    "-DLLAMA_BUILD_SERVER=OFF",
                    "-DLLAMA_BUILD_APP=OFF",
                    "-DLLAMA_BUILD_COMMON=OFF",
                    "-DBUILD_SHARED_LIBS=OFF"
                )
            }
        }
    }

    signingConfigs {
        if (stableSigningAvailable) {
            create("stable") {
                storeFile = file(requireNotNull(stableKeystoreFile))
                storePassword = requireNotNull(stableStorePassword)
                keyAlias = requireNotNull(stableKeyAlias)
                keyPassword = requireNotNull(stableKeyPassword)
                storeType = "PKCS12"
            }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            if (stableSigningAvailable) {
                signingConfig = signingConfigs.getByName("stable")
            }
        }
        release {
            isMinifyEnabled = true
            if (stableSigningAvailable) {
                signingConfig = signingConfigs.getByName("stable")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
}

dependencies {
    implementation("androidx.webkit:webkit:1.17.1")
    implementation("androidx.core:core:1.15.0")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.30.0")
    testImplementation("junit:junit:4.13.2")
}
