plugins {
    id("com.android.application")
}

android {
    namespace = "com.xonoxo.localailab"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.xonoxo.localailab"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = System.getenv("LOCALAI_BUILD_VERSION") ?: "0.1.0-dev"
    }

    buildTypes {
        debug {
            isDebuggable = true
        }
        release {
            isMinifyEnabled = false
        }
    }
}
